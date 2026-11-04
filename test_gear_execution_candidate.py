"""Offline fake-service tests; no game input or production setup."""
import os,sys,tempfile,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from owner_gear_decision_candidate import Observation
from owner_gear_settings_candidate import Store
from owner_gear_execution_candidate import run_configured_step,reconcile_configured_step
from owner_gear_intent_store_candidate import IntentStore


class Context:
    def __init__(self):self.stop=False
    def checkpoint(self):
        if self.stop:raise RuntimeError('cancelled')

class Service:
    def __init__(self):self.hits=[];self.detector=self
    def check(self):pass
    def capture(self):return 'fake-frame'
    def find(self,name,frame,threshold):return (10,10,(5,5,15,15))
    def click_hit(self,hit):self.hits.append(hit)

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
        self.root=self.temp.name;self.character='server / character';self.context=Context();self.service=Service()
        self.o=Observation(1,100,'char','fan','weapon','희귀',29,0,0,True,True,True)
        self.n=0;self.now=100.9
    def enabled(self):
        s=Store(self.root,self.character);v=s.read();v['grades']['희귀'].update(enabled=True,enhance=30,breakthrough=0,awaken=0);s.write(v)
    def pair(self):
        i=self.n;self.n+=1
        a=replace(self.o,sequence=self.o.sequence+2*i,captured_at=self.o.captured_at+.3*i)
        b=replace(a,sequence=a.sequence+1,captured_at=a.captured_at+.2)
        return dict(first=a,second=b,screen_proof=True,cost_pair_verified=True,currency='엽전',cost=100,balance=1000)
    def run_step(self,verify):
        return run_configured_step(self.service,self.context,self.root,self.character,'enhance',self.pair,verify,clock=lambda:self.now)
    def test_default_returns_existing_path(self):
        self.assertEqual(self.run_step(lambda *a:True),'use_original');self.assertFalse(self.service.hits)
    def test_verified_fake_single_native_click_then_restart_holds(self):
        self.enabled();self.assertEqual(self.run_step(lambda *a:True),'pending_confirmation')
        self.assertEqual(len(self.service.hits),1)
        self.assertEqual(self.run_step(lambda *a:True),'hold_pending');self.assertEqual(len(self.service.hits),1)
        self.o=replace(self.o,sequence=5,captured_at=101,enhancement=30);self.n=0;self.now=101.9
        self.assertEqual(reconcile_configured_step(self.context,self.root,self.character,self.pair,clock=lambda:self.now),'observed_progress')
        self.assertEqual(self.run_step(lambda *a:True),'hold_policy');self.assertEqual(len(self.service.hits),1)
    def test_missing_observer_is_not_original_fallback(self):
        self.enabled();self.assertEqual(run_configured_step(self.service,self.context,self.root,self.character,'enhance',None,None),'hold_missing_observer')
        self.assertFalse(self.service.hits)
    def test_final_screen_unverified_aborts_before_input_and_permits_retry(self):
        self.enabled();self.assertEqual(self.run_step(lambda *a:False),'hold_final_preinput')
        self.assertFalse(self.service.hits)
        self.n=0;self.assertEqual(self.run_step(lambda *a:True),'pending_confirmation')
        self.assertEqual(len(self.service.hits),1)
    def test_unsupported_and_unknown_character(self):
        self.enabled();self.assertEqual(run_configured_step(self.service,self.context,self.root,'','enhance',self.pair,lambda *a:True),'hold_identity')
        self.assertEqual(run_configured_step(self.service,self.context,self.root,self.character,'other',self.pair,lambda *a:True),'hold_unknown_action')
        self.assertFalse(self.service.hits)
    def test_paired_awakening_zero_allows_only_one_then_pending(self):
        store=Store(self.root,self.character);v=store.read()
        v['grades']['희귀'].update(enabled=True,enhance=50,breakthrough=3,awaken=1);store.write(v)
        self.o=replace(self.o,enhancement=None,breakthrough=None,awakening=0,
                       enhance_available=None,breakthrough_available=None,awaken_available=True)
        def awakening_pair():
            d=self.pair();d.update(resource_mode='native_active',action_mode='awaken',
                                    active_pair_verified=True,cost_pair_verified=False)
            return d
        def run():return run_configured_step(self.service,self.context,self.root,self.character,
                        'awaken',awakening_pair,lambda *args:True,clock=lambda:self.now)
        self.assertEqual(run(),'pending_confirmation');self.assertEqual(len(self.service.hits),1)
        self.assertEqual(run(),'hold_pending');self.assertEqual(len(self.service.hits),1)
    def test_restart_reconciles_from_fresh_pair_even_if_clock_and_sequence_reset(self):
        self.enabled();self.o=replace(self.o,sequence=500,captured_at=100.)
        self.assertEqual(self.run_step(lambda *a:True),'pending_confirmation')
        self.o=replace(self.o,sequence=1,captured_at=1.,enhancement=30,slot='growth-slot:12')
        self.n=0;self.now=1.9
        self.assertEqual(reconcile_configured_step(self.context,self.root,self.character,self.pair,clock=lambda:self.now),'observed_progress')
    def test_reconcile_keeps_sent_receipt_if_character_or_settings_changed(self):
        self.enabled();self.assertEqual(self.run_step(lambda *a:True),'pending_confirmation')
        self.o=replace(self.o,sequence=5,captured_at=101,enhancement=30);self.n=0;self.now=101.9
        path=Store(self.root,self.character).path;intent=IntentStore(path.with_name(path.stem+'-intent.json'))
        self.assertEqual(reconcile_configured_step(self.context,self.root,self.character,self.pair,clock=lambda:self.now,before_complete=lambda:False),'hold_identity_or_settings')
        self.assertEqual(intent.pending()['phase'],'sent');self.assertEqual(len(self.service.hits),1)
        self.n=0
        self.assertEqual(reconcile_configured_step(self.context,self.root,self.character,self.pair,clock=lambda:self.now,before_complete=lambda:True),'observed_progress')
        self.assertIsNone(intent.pending())
    def test_click_exception_leaves_sent_intent(self):
        self.enabled()
        def failed(hit):raise RuntimeError('input outcome unknown')
        self.service.click_hit=failed
        with self.assertRaises(RuntimeError):self.run_step(lambda *a:True)
        path=Store(self.root,self.character).path
        pending=IntentStore(path.with_name(path.stem+'-intent.json')).pending()
        self.assertEqual(pending['phase'],'sent')
        self.assertEqual(self.run_step(lambda *a:True),'hold_pending')
    def test_opening_selects_only_native_open_button(self):
        from project_adapter import market_inventory
        self.enabled();self.o=replace(self.o,enhancement=19)
        def opening_pair():
            d=self.pair();d.update(resource_mode='native_active',active_pair_verified=True,
              button_name=market_inventory.GROWTH_EXEC_BUTTONS[1],opening=True,cost_pair_verified=False)
            return d
        seen=[]
        def find(name,frame,threshold):seen.append(name);return (10,10,(5,5,15,15))
        self.service.find=find
        result=run_configured_step(self.service,self.context,self.root,self.character,'enhance',opening_pair,
                                   lambda *args:True,clock=lambda:self.now)
        self.assertEqual(result,'pending_confirmation');self.assertEqual(seen,[market_inventory.GROWTH_EXEC_BUTTONS[1]])
    def test_changed_setting_prevents_input_and_drops_prepared_intent(self):
        self.enabled()
        result=run_configured_step(self.service,self.context,self.root,self.character,'enhance',self.pair,
                                   lambda *args:True,clock=lambda:self.now,settings_check=lambda:False)
        self.assertEqual(result,'hold_final_preinput');self.assertEqual(self.service.hits,[])
        path=Store(self.root,self.character).path
        self.assertIsNone(IntentStore(path.with_name(path.stem+'-intent.json')).pending())
    def test_intent_os_lock_is_released_without_deleting_lockfile(self):
        import msvcrt
        store=IntentStore(Path(self.root)/'intent.json');lock=store.path.with_suffix('.json.lock')
        fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600);os.write(fd,b'0');os.lseek(fd,0,os.SEEK_SET)
        msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        try:
            with self.assertRaises(RuntimeError):store.begin({'kind':'enhance','before':self.o,'second':self.o})
        finally:os.close(fd)
        store.begin({'kind':'enhance','before':self.o,'second':self.o})
        self.assertTrue(store.abort_prepared('test'));self.assertTrue(lock.exists())

if __name__=='__main__':unittest.main()
