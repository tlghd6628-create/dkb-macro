import json
import tempfile
import unittest
import sys
import subprocess
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from owner_shop_transaction_candidate import Hold, ShopJournal

class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal.json'
        self.journal = ShopJournal(self.path, clock=lambda: 1000.0)
        self.setting = {'enabled': True, 'shop': 'town', 'name': '책', 'mode': 'quantity', 'quantity': 4}

    def pair(self, **changes):
        row = dict(verified=True, character='캐릭터A', shop='town', week='주기A', item='책',
                   currency='엽전', unit_price=100, remaining=10, balance=1000, captured_at=999.0)
        row.update(changes)
        return dict(row, frame_id='a'), dict(row, frame_id='b')

    def prepare(self, setting=None, reserve=300, **changes):
        return self.journal.prepare(setting or self.setting, reserve, *self.pair(**changes))

    def receipt(self, entry):
        return self.pair(remaining=entry['remaining']-entry['quantity'],
                         balance=entry['balance']-entry['quantity']*entry['unit_price'],
                         purchase_success=True, purchased_quantity=entry['quantity'], captured_at=1000)

    def test_quantity_and_durable_intent(self):
        entry = self.prepare()
        self.assertEqual(entry['quantity'], 4)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['transactions'][0]['state'], 'pending')
        with self.assertRaises(Hold): self.prepare()
        with self.assertRaises(Hold): self.prepare(week='주기B')

    def test_unset_reserve_never_prepares(self):
        with self.assertRaises(Hold): self.prepare(reserve=None)
        self.assertFalse(self.path.exists())

    def test_max_obeys_reserve_and_limit(self):
        setting = dict(self.setting, mode='max')
        self.assertEqual(self.prepare(setting, reserve=350, remaining=8)['quantity'], 6)

    def test_disabled_mismatch_and_unknown_evidence_hold(self):
        for setting, change in [(dict(self.setting, enabled=False), {}),
                                (self.setting, {'item':'다른 책'}),
                                (self.setting, {'currency':''}),
                                (self.setting, {'unit_price':0}),
                                (self.setting, {'remaining':None}),
                                (self.setting, {'verified':False}),
                                (self.setting, {'captured_at':990})]:
            with self.subTest(setting=setting, change=change):
                with self.assertRaises(Hold): self.prepare(setting, **change)

    def test_pair_must_be_distinct_and_agree(self):
        a,b = self.pair(); b['unit_price']=99
        with self.assertRaises(Hold): self.journal.prepare(self.setting, 300, a, b)
        b=dict(a)
        with self.assertRaises(Hold): self.journal.prepare(self.setting, 300, a, b)

    def test_final_check_requires_unchanged_fresh_new_frames(self):
        entry=self.prepare();a,b=self.pair(captured_at=1000)
        with self.assertRaises(Hold): self.journal.revalidate(entry['id'],a,b)
        a['frame_id']='c';b['frame_id']='d';b['balance']=900
        with self.assertRaises(Hold): self.journal.revalidate(entry['id'],a,b)
        b['balance']=1000
        self.assertEqual(self.journal.revalidate(entry['id'],a,b)['id'],entry['id'])

    def test_pending_isolated_by_character_and_shop(self):
        self.prepare()
        other = self.prepare(character='캐릭터B')
        remote = self.prepare(dict(self.setting, shop='remote'), shop='remote')
        self.assertNotEqual(other['id'], remote['id'])

    def test_receipt_must_be_new_and_prove_exact_result(self):
        entry=self.prepare(); a,b=self.receipt(entry)
        with self.assertRaises(Hold): self.journal.confirm(entry['id'], a, b)
        a['frame_id']='c';b['frame_id']='d'; b['balance'] += 1
        with self.assertRaises(Hold): self.journal.confirm(entry['id'], a, b)
        b['balance'] -= 1; a['purchase_success']=False
        with self.assertRaises(Hold): self.journal.confirm(entry['id'], a, b)
        a['purchase_success']=True
        self.assertEqual(self.journal.confirm(entry['id'], a, b)['state'], 'confirmed')
        with self.assertRaises(Hold): self.prepare(remaining=6,balance=600)
        self.assertEqual(self.prepare(week='주기B')['quantity'],4)

    def test_incomplete_receipt_persists_pending_across_process(self):
        entry=self.prepare(); a,b=self.receipt(entry);a['purchase_success']=False
        with self.assertRaises(Hold): self.journal.confirm(entry['id'],a,b)
        new=ShopJournal(self.path,clock=lambda:1000)
        with self.assertRaises(Hold): new.prepare(self.setting,300,*self.pair())

    def test_corrupt_ledger_or_lock_does_not_buy(self):
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(Hold): self.prepare()
        self.path.unlink()
        # An existing lock file is normal; only a held OS lock blocks work.
        self.path.with_name(self.path.name+'.lock').touch()
        fd,_=self.journal._lock()
        try:
            with self.assertRaises(Hold): self.prepare()
        finally:
            import os,msvcrt
            os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_UNLCK,1);os.close(fd)
        self.assertEqual(self.prepare()['state'],'pending')

    def test_process_crash_releases_lock_without_erasing_pending(self):
        entry=self.prepare()
        ready=Path(self.tmp.name)/'child-ready'
        code=("import sys,time; from pathlib import Path; "
              "sys.path.insert(0,sys.argv[3]); from owner_shop_transaction_candidate import ShopJournal; "
              "j=ShopJournal(sys.argv[1]); fd,_=j._lock(); "
              "Path(sys.argv[2]).write_text('ready'); time.sleep(30)")
        child=subprocess.Popen([sys.executable,'-c',code,str(self.path),str(ready),str(Path(__file__).resolve().parent)],
                               cwd=str(Path(__file__).resolve().parent),
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+5
            while not ready.exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists(),'test lock holder did not start')
            with self.assertRaises(Hold):self.prepare(character='캐릭터B')
        finally:
            child.kill();child.wait(timeout=5)
        # A crash releases the lock, but never resolves a pending purchase.
        self.assertEqual(self.journal._read()['transactions'][0]['id'],entry['id'])
        with self.assertRaises(Hold):self.prepare()
        self.assertEqual(self.prepare(character='캐릭터B')['state'],'pending')

if __name__ == '__main__': unittest.main()
