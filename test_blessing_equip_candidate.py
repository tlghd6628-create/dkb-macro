"""Saved compare screenshots and explicitly simulated OCR/input."""
import os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from owner_blessing_equip_candidate import equip_selected,reconcile,equip_hit,compare_worn_mark,same_compare_appearance,parse_title,selected_filter,scan_filtered,_scan_cursor

class Context:
    def checkpoint(self):pass
    def wait(self,n):pass
class Service:
    def __init__(self,frame,root):self.frame=frame;self.adapter=SimpleNamespace(project=SimpleNamespace(root=root));self.actions=[]
    def capture(self):return self.frame.copy()
    def check(self):pass
    def click_hit(self,hit):self.actions.append(hit)
class Tests(unittest.TestCase):
    def setUp(self):
        p=Path(__file__).parent/'live_fixtures'
        self.a=np.asarray(Image.open(p/'blessing_compare_rare_normal_native_1.png').convert('RGB')).copy()
        self.b=np.asarray(Image.open(p/'blessing_compare_rare_normal_native_2.png').convert('RGB')).copy()
        self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
        self.service=Service(self.a,self.temp.name);self.context=Context()
    def row(self,grade,pattern='토끼',slot=1):return {'grade':grade,'pattern':pattern,'slot':slot,'verified':True}
    def test_actual_compare_buttons_and_pair_similarity(self):
        self.assertIsNotNone(equip_hit(self.a));self.assertTrue(compare_worn_mark(self.a))
        self.assertTrue(same_compare_appearance(self.a,self.b))
        changed=self.b.copy();changed[100:110,300:400]=0
        self.assertFalse(same_compare_appearance(self.a,changed))
    def test_lower_grade_is_not_equipped(self):
        reader=lambda root,frame:(self.row('희귀'),self.row('일반'))
        self.assertEqual(equip_selected(self.service,self.context,'s/c',[],settings_check=lambda:True,reader=reader),'hold_policy')
        self.assertEqual(self.service.actions,[])
    def test_simulated_higher_grade_executes_once_and_requires_reconcile(self):
        # OCR rows and future worn result are simulated; real frames show the reverse.
        candidate=self.row('희귀');reader=lambda root,frame:(self.row('일반'),candidate)
        run=lambda:equip_selected(self.service,self.context,'s/c',[],settings_check=lambda:True,reader=reader)
        self.assertEqual(run(),'pending_confirmation');self.assertEqual(len(self.service.actions),1)
        self.assertEqual(run(),'hold_pending');self.assertEqual(len(self.service.actions),1)
        self.assertEqual(reconcile(self.service,self.context,'s/c',lambda frame:self.row('일반')),'hold_result_unknown')
        self.assertEqual(reconcile(self.service,self.context,'s/c',lambda frame:candidate),'observed_equipped')
    def test_title_parsing_requires_actual_slot(self):
        self.assertEqual(parse_title('토끼 가호 장식1(귀속)')['slot'],1)
        self.assertIsNone(parse_title('토끼 가호 장식(귀속)'))
        self.assertIsNone(parse_title('토끼 가호 장식6(귀속)'))
    def test_actual_filtered_pngs_reevaluate_visible_comparison(self):
        from roi_runtime import RoiDetector
        from project_adapter import achievement_rewards as native
        folder=Path(__file__).parent/'live_fixtures'
        load=lambda n:np.asarray(Image.open(folder/n).convert('RGB')).copy()
        first,second=load('blessing_slot1_native_1.png'),load('blessing_slot1_native_2.png')
        self.assertEqual((selected_filter(first),selected_filter(second)),(1,1))
        self.assertIsNone(selected_filter(load('blessing_menu_native_1.png')))
        self.service.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.BLESSING_NAMES))
        frames=iter((first,second,self.a,self.b));self.service.capture=lambda:next(frames).copy()
        identity='slot-scan';_scan_cursor[(identity,1)]=3
        self.addCleanup(lambda:_scan_cursor.pop((identity,1),None))
        # Time separation is needed by the normal fresh-frame check.
        import time
        self.context.wait=lambda n:time.sleep(.02)
        reader=lambda root,frame:(self.row('희귀'),self.row('일반'))
        result=scan_filtered(self.service,self.context,identity,1,[],settings_check=lambda:True,reader=reader)
        self.assertEqual(result,'hold_policy');self.assertEqual(len(self.service.actions),1)
    def test_list_icon_mismatch_does_not_override_verified_comparison_policy(self):
        import json
        from owner_blessing_equip_candidate import _intent_path
        candidate=self.row('희귀');reader=lambda root,frame:(self.row('일반'),candidate)
        icon=np.zeros((18,18,3),dtype=np.uint8)
        status=equip_selected(self.service,self.context,'s/c',[],settings_check=lambda:True,reader=reader,
                              candidate_icon=icon,candidate_check=lambda frame:False,expected_category=1)
        self.assertEqual(status,'pending_confirmation');self.assertEqual(len(self.service.actions),1)
        data=json.loads(_intent_path(self.temp.name,'s/c').read_text(encoding='utf8'))
        self.assertIsNone(data['pending']['icon'])
    def test_filtered_reconciliation_requires_candidate_worn_mark_in_both_frames(self):
        import base64,time
        from roi_runtime import RoiDetector
        from project_adapter import achievement_rewards as reward,market_inventory as native
        from owner_blessing_equip_candidate import _intent_path,_save,reconcile_filtered
        folder=Path(__file__).parent/'live_fixtures'
        frame=np.asarray(Image.open(folder/'blessing_slot1_native_1.png').convert('RGB')).copy()
        self.service.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(reward.BLESSING_NAMES))
        rows=native.inspect_growth_equipment(self.service.detector,frame,reward_slots=True)
        src,dst=rows[0]['slot'],rows[1]['slot'];x,y=dst['cell_x']+8,dst['cell_y']+8
        icon=base64.b64encode(frame[y:y+18,x:x+18].tobytes()).decode('ascii')
        path=_intent_path(self.temp.name,'s/c');candidate=self.row('희귀',pattern='연꽃')
        _save(path,{'version':1,'pending':{'phase':'sent','candidate':candidate,'icon':icon}})
        self.service.frame=frame;self.context.wait=lambda n:time.sleep(.02)
        self.assertEqual(reconcile_filtered(self.service,self.context,'s/c',1),'hold_result_unknown')
        # Synthetic E badge on the same candidate proves only the mock path.
        changed=frame.copy();sx,sy=src['x']-3,src['y']-3;dx,dy=dst['x']-3,dst['y']-3
        changed[dy:dy+13,dx:dx+11]=frame[sy:sy+13,sx:sx+11]
        self.service.frame=changed
        self.assertEqual(reconcile_filtered(self.service,self.context,'s/c',1),'observed_equipped')
    def test_worn_detail_reconciles_without_second_equip_input(self):
        import time
        from roi_runtime import RoiDetector
        from project_adapter import achievement_rewards as reward
        from owner_blessing_equip_candidate import _intent_path,_save,reconcile_worn_detail
        folder=Path(__file__).parent/'live_fixtures';load=lambda n:np.asarray(Image.open(folder/n).convert('RGB')).copy()
        first,second=load('blessing_slot1_native_1.png'),load('blessing_slot1_native_2.png')
        detail1,detail2=load('blessing_worn_filter1_native_1.png'),load('blessing_worn_filter1_native_2.png')
        self.service.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(reward.BLESSING_NAMES))
        frames=iter((first,second,detail1,detail2,detail2,first,second));self.service.capture=lambda:next(frames).copy()
        self.context.wait=lambda n:time.sleep(.02);candidate=self.row('희귀')
        path=_intent_path(self.temp.name,'s/c');_save(path,{'version':1,'pending':{'phase':'sent','candidate':candidate,'icon':None}})
        status=reconcile_worn_detail(self.service,self.context,'s/c',1,settings_check=lambda:True,reader=lambda root,frame:candidate)
        self.assertEqual(status,'observed_equipped');self.assertEqual(len(self.service.actions),2)
        self.assertLess(self.service.actions[1][0],520) # Only detail-close X, never the equip/unequip button.
    def test_worn_detail_mismatch_preserves_pending(self):
        import json,time
        from roi_runtime import RoiDetector
        from project_adapter import achievement_rewards as reward
        from owner_blessing_equip_candidate import _intent_path,_save,reconcile_worn_detail
        folder=Path(__file__).parent/'live_fixtures';load=lambda n:np.asarray(Image.open(folder/n).convert('RGB')).copy()
        first,second=load('blessing_slot1_native_1.png'),load('blessing_slot1_native_2.png')
        detail1,detail2=load('blessing_worn_filter1_native_1.png'),load('blessing_worn_filter1_native_2.png')
        self.service.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(reward.BLESSING_NAMES))
        frames=iter((first,second,detail1,detail2,detail2,first,second));self.service.capture=lambda:next(frames).copy()
        self.context.wait=lambda n:time.sleep(.02);path=_intent_path(self.temp.name,'s/c')
        _save(path,{'version':1,'pending':{'phase':'sent','candidate':self.row('희귀','연꽃'),'icon':None}})
        status=reconcile_worn_detail(self.service,self.context,'s/c',1,settings_check=lambda:True,reader=lambda root,frame:self.row('희귀','토끼'))
        self.assertEqual(status,'hold_result_unknown');self.assertEqual(json.loads(path.read_text(encoding='utf8'))['pending']['phase'],'sent')

if __name__=='__main__':unittest.main()
