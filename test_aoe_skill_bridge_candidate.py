"""No game process: candidate SkillUI assets plus in-memory fake UI."""
import copy, unittest
from pathlib import Path
import bootstrap
import owner_skill_ui as module
from owner_skill_goal import Pending
from owner_aoe_preset_candidate import SLOTS,ORDER
from owner_aoe_skill_bridge_candidate import attempt,checked_backend

class UI:
    def __init__(self,data):self.public=data;self.actions=[];self.slots=[None]*8
    def scan_owned(self):self.actions.append('scan');return set(SLOTS)
    def select_preset(self,n):self.actions.append(('preset',n))
    def unlocked(self):return set(range(8))
    def equip(self,sid,i):self.actions.append(('equip',sid,i));self.slots[i]=sid
    def set_order(self,o):self.actions.append(('order',tuple(o)))
    def current_slots(self,u):return self.slots
class Ledger:
    def __init__(self):self.items=[]
    def preset_receipt(self,*a,**kw):self.items.append((a,kw))

class Bridge(unittest.TestCase):
    def setUp(self):
        self.catalog=module.catalog();self.original=copy.deepcopy(self.catalog['candidate_notes'])
        self.addCleanup(lambda: self.catalog.__setitem__('candidate_notes',self.original))
        self.ui=UI(self.catalog);self.ledger=Ledger()
        self.proof={'character':'A','source':'game-screen','skill_id':59,'name':'연쇄 번개',
          'frames':[{'id':'a','captured_monotonic':9.,'name_verified':True,'icon_verified':True},
                    {'id':'b','captured_monotonic':9.5,'name_verified':True,'icon_verified':True}]}
    def go(self):return attempt(module,self.ui,self.ledger,character='A',
        read_icon_evidence=lambda:self.proof,clock=lambda:10.,checkpoint=lambda:None)
    def test_unverified_actual_candidate_does_not_even_scan(self):
        with self.assertRaises(Pending):self.go()
        self.assertEqual(self.ui.actions,[]);self.assertEqual(self.ledger.items,[])
    def test_existing_candidate_backend_reuses_hashed_icon_loader(self):
        self.assertTrue(checked_backend(module,self.ui,self.catalog))
    def test_synthetic_only_success_never_touches_single(self):
        self.catalog['candidate_notes']['icon_59_game_match_verified']=True
        self.assertTrue(self.go())
        self.assertIn(('preset',1),self.ui.actions)
        self.assertNotIn(('preset',2),self.ui.actions)
        self.assertIn(('order',ORDER),self.ui.actions)
        self.assertEqual(len(self.ledger.items),1)
    def test_backend_mismatch_stops_before_scan(self):
        self.catalog['candidate_notes']['icon_59_game_match_verified']=True
        self.ui.public={'different':True}
        with self.assertRaises(Pending):self.go()
        self.assertEqual(self.ui.actions,[])
    def test_real_archived_life_capture_remains_life_not_lightning(self):
        from PIL import Image
        import numpy as np
        path=Path(r'C:\Users\홍이\Downloads\FC_프로그램\도깨비의세계\보관\개발이력_20261101_120213\owner\shop_skill_20261101\fixtures\skill-life-restored-window.png')
        frame=np.asarray(Image.open(path).convert('RGB').crop((1,30,898,509)))
        self.assertEqual(module.identify_icon(frame,(694,76,41,45),[84,59]),84)

if __name__=='__main__':unittest.main()
