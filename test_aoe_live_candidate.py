"""Offline AOE bridge checks only; no game process or actual input."""
import copy,time,unittest,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
import owner_skill_ui as module
from owner_skill_goal import Pending
from owner_aoe_preset_candidate import SLOTS,ORDER
from owner_aoe_skill_bridge_candidate import attempt_live_candidate

HERE=Path(__file__).parent
def frame(name):
    return np.asarray(Image.open(HERE/'live_fixtures'/name).convert('RGB'))[31:510,1:898].copy()

class FakeUI:
    def __init__(self):self.public=module.catalog();self.actions=[];self.slots=[None]*8;self.missing=False
    def scan_owned(self):self.actions.append('scan');return set(SLOTS)|{65} if not self.missing else set()
    def select_preset(self,n):self.actions.append(('preset',n))
    def unlocked(self):return set(range(8))
    def _click_chain59_paired(self,*a):pass
    def find_skill(self,sid):self.actions.append(('find',sid))
    def equip(self,sid,i):self.actions.append(('equip',sid,i));self.slots[i]=sid
    def set_order(self,o):self.actions.append(('order',tuple(o)))
    def current_slots(self,u):return self.slots
class Ledger:
    character='A'
    def __init__(self):self.items=[]
    def preset_receipt(self,*a,**kw):self.items.append((a,kw))

class Candidate(unittest.TestCase):
    def setUp(self):self.ui=FakeUI();self.ledger=Ledger()
    def run_bridge(self):return attempt_live_candidate(module,self.ui,self.ledger,character='A',checkpoint=lambda:None)
    def test_only_preset_one_exact_order(self):
        self.assertTrue(self.run_bridge())
        self.assertEqual([a for a in self.ui.actions if isinstance(a,tuple) and a[0]=='preset'],[('preset',1)])
        self.assertIn(('order',ORDER),self.ui.actions)
        self.assertEqual(self.ledger.items[0][0],('aoe',list(SLOTS),list(ORDER)))
    def test_missing_and_wrong_character_hold(self):
        self.ui.missing=True
        with self.assertRaises(Pending):self.run_bridge()
        self.assertEqual(self.ui.actions,['scan']);self.assertEqual(self.ledger.items,[])
        self.ui=FakeUI();self.ledger.character='B'
        with self.assertRaises(Pending):self.run_bridge()
        self.assertEqual(self.ui.actions,[])
    def test_no_receipt_on_order_failure(self):
        def stop(_):raise Pending('unrecognized')
        self.ui.set_order=stop
        with self.assertRaises(Pending):self.run_bridge()
        self.assertEqual(self.ledger.items,[])
    def test_saved_frames_existing_full_catalog_classifier(self):
        for name,first in [('skill_list_20261101_a.jpg',130),('skill_list_20261101_b.jpg',130),('skill_chain_selected_20261101.jpg',130),('skill_chain_scrolled_20261101.jpg',121)]:
            img=frame(name)
            for i in range(1,10):
                box=(695,round(first+(i-1)*45.5-31)-20,40,40)
                actual=module.identify_icon(img,box)
                with self.subTest(file=name,row=i):
                    if i==4:self.assertEqual(actual,59)
                    else:self.assertNotEqual(actual,59)
    def test_exact_pair_and_input_boundary(self):
        a=frame('skill_list_20261101_a.jpg');b=frame('skill_chain_selected_20261101.jpg')
        # Stored frame and synthetic OCR coordinates: no OCR accuracy claim.
        row={'text':'연쇄 번개','score':.99,'x':756,'y':236,'bounds':(735,225,790,243)}
        ui=object.__new__(module.SkillUI);calls=[]
        ui._owner_last_rows_pair=([a,b],[time.monotonic(),time.monotonic()],[[row.copy()],[row.copy()]])
        ui.click=lambda x,y,proof: calls.append(proof(b))
        ui._click_chain59_paired(row)
        self.assertEqual(calls,[True])
        ui._owner_last_rows_pair=([a,b],[time.monotonic()-4,time.monotonic()],[[row.copy()],[row.copy()]])
        with self.assertRaises(Pending):ui._click_chain59_paired(row)
        bad=copy.deepcopy(row);bad['text']='번개 폭풍'
        ui._owner_last_rows_pair=([a,b],[time.monotonic(),time.monotonic()],[[row.copy()],[bad]])
        with self.assertRaises(Pending):ui._click_chain59_paired(row)
        self.assertEqual(calls,[True])

if __name__=='__main__':unittest.main(verbosity=2)
