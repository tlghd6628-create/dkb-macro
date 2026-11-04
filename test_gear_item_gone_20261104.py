"""A spending record may close only when its item is proved gone. Fake rows, no game."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import json,tempfile,time,unittest
from dataclasses import asdict
import owner_gear_native_install_candidate as g
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_decision_candidate import Observation

NOW=2_000_000_000.
def sent(age=7200,phase='sent'):return {'phase':phase,'sent_at_epoch':NOW-age,'kind':'enhance'}

class Rule(unittest.TestCase):
    def test_old_sent_record_with_no_match_in_a_real_list_is_gone(self):
        self.assertTrue(g.item_gone(sent(),[{'index':0}],[],now=NOW))
    def test_a_match_is_never_gone(self):
        self.assertFalse(g.item_gone(sent(),[{'index':0}],[{'index':0}],now=NOW))
    def test_two_matches_are_not_gone_either(self):
        self.assertFalse(g.item_gone(sent(),[{'index':0},{'index':1}],[{'index':0},{'index':1}],now=NOW))
    def test_an_unread_list_proves_nothing(self):
        self.assertFalse(g.item_gone(sent(),[],[],now=NOW))
    def test_a_recent_record_waits_for_its_result(self):
        self.assertFalse(g.item_gone(sent(age=60),[{'index':0}],[],now=NOW))
    def test_a_record_without_a_send_time_stays(self):
        self.assertFalse(g.item_gone({'phase':'sent','kind':'enhance'},[{'index':0}],[],now=NOW))
    def test_prepared_is_not_this_path(self):
        self.assertFalse(g.item_gone(sent(phase='prepared'),[{'index':0}],[],now=NOW))

class Second(unittest.TestCase):
    """The second look, on real pixel arrays."""
    def setUp(self):
        import numpy as np
        self.np=np;self.frame=np.zeros((479,897,3),np.uint8)
        self.frame[50:90,700:740]=np.random.default_rng(1).integers(0,255,(40,40,3),dtype=np.uint8)
        self.row={'slot':{'cell_x':702,'cell_y':52}}
        self.icon=self.frame[60:78,710:728].copy()
    def before(self,item='icon:other'):
        from types import SimpleNamespace as S
        return S(item=item)
    def test_the_same_item_is_seen(self):
        import hashlib
        item='icon:'+hashlib.sha256(self.icon.tobytes()).hexdigest()
        self.assertTrue(g._row_shows(self.frame,self.row,self.before(item),None))
    def test_a_similar_icon_is_seen(self):
        self.assertTrue(g._row_shows(self.frame,self.row,self.before(),self.icon.copy()))
    def test_a_different_item_is_not(self):
        other=self.np.random.default_rng(2).integers(0,255,(18,18,3),dtype=self.np.uint8)
        self.assertFalse(g._row_shows(self.frame,self.row,self.before(),other))
    def test_an_unreadable_cell_counts_as_seen_so_nothing_closes(self):
        self.assertTrue(g._row_shows(self.frame,{'slot':{}},self.before(),None))

class Store(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
        self.store=IntentStore(Path(self.tmp.name)/'intent.json')
        fields=Observation.__dataclass_fields__
        ob=Observation(**{k:None for k in fields})
        self.store.begin({'kind':'enhance','before':ob,'second':ob,'item_icon':'abc'})
    def test_prepared_cannot_be_closed_this_way(self):
        self.assertFalse(self.store.close_absent('x'));self.assertIsNotNone(self.store.pending())
    def test_sent_closes_and_keeps_the_record(self):
        self.store.mark_sent();self.assertTrue(self.store.close_absent('장비 없음'))
        self.assertIsNone(self.store.pending())
        data=json.loads(self.store.path.read_text(encoding='utf-8'))
        self.assertEqual(data['last_result'],'item_gone');self.assertEqual(len(data['closed_absent']),1)
        self.assertEqual(data['closed_absent'][0]['kind'],'enhance');self.assertNotIn('item_icon',data['closed_absent'][0])
    def test_a_new_record_can_begin_after_closing(self):
        self.store.mark_sent();self.store.close_absent('장비 없음')
        fields=Observation.__dataclass_fields__;ob=Observation(**{k:None for k in fields})
        self.store.begin({'kind':'enhance','before':ob,'second':ob})
        self.assertEqual(self.store.pending()['phase'],'prepared')
    def test_the_history_stays_bounded(self):
        for _ in range(14):
            self.store.mark_sent();self.store.close_absent('x')
            fields=Observation.__dataclass_fields__;ob=Observation(**{k:None for k in fields})
            self.store.begin({'kind':'enhance','before':ob,'second':ob})
        self.assertEqual(len(json.loads(self.store.path.read_text(encoding='utf-8'))['closed_absent']),10)

if __name__=='__main__':unittest.main()
