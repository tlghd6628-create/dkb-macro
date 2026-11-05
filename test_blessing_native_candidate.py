"""Stored screenshots + fake input only; no in-game changes."""
import os,sys,time,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native
import owner_blessing_native_candidate as blessing

class Context:
    def checkpoint(self):pass
    def wait(self,n):time.sleep(n)
class Service:
    def __init__(self,frames):
        self.frames=iter(frames);self.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_BLESSING_NAMES))
        self.context=Context();self.adapter=SimpleNamespace(project=SimpleNamespace(root=bootstrap.A));self.actions=[]
    def capture(self):return next(self.frames).copy()
    def check(self):pass
    def click_hit(self,hit):self.actions.append(hit)
class Tests(unittest.TestCase):
    def frame(self,name):
        return np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/name).convert('RGB').crop((1,31,898,510))).copy()
    def test_real_worn_badges_agree_and_unworn_excluded(self):
        a=self.frame('blessing_list_1.jpg');b=self.frame('blessing_list_2.jpg');s=Service([a,b])
        self.assertEqual([r['index'] for r in blessing.worn_candidates(native,s.detector,a)],[1,2,3,4,5])
        self.assertEqual([r['index'] for r in blessing.worn_candidates(native,s.detector,b)],[1,2,3,4,5])
    def test_native_png_badges_use_existing_detector_result(self):
        path=Path(__file__).parent/'live_fixtures';a=np.asarray(Image.open(path/'blessing_list_native_1.png').convert('RGB')).copy()
        b=np.asarray(Image.open(path/'blessing_list_native_2.png').convert('RGB')).copy();s=Service([a,b])
        self.assertEqual([r['index'] for r in blessing.worn_candidates(native,s.detector,a)],[1,2,3,4,5])
        self.assertEqual([r['index'] for r in blessing.worn_candidates(native,s.detector,b)],[1,2,3,4,5])
    def test_actual_selected_icon_matches_2_and_other_slot_does_not(self):
        a=self.frame('blessing_list_1.jpg');b=self.frame('blessing_rabbit_slot1_1.jpg');s=Service([a])
        rows=native.inspect_growth_equipment(s.detector,a,blessing=True)
        self.assertTrue(blessing.selected_matches(native,s.detector,a,rows,2,b))
        self.assertFalse(blessing.selected_matches(native,s.detector,a,rows,1,b))
        changed=a.copy();one,two=rows[0]['slot'],rows[1]['slot']
        x,y=one['cell_x']+8,one['cell_y']+8;u,v=two['cell_x']+8,two['cell_y']+8
        changed[y:y+18,x:x+18]=changed[v:v+18,u:u+18]
        # An identical twin is separable only by the game's selected-tile mark.
        with patch.object(native,'_growth_selected_slot',return_value=1):
            self.assertFalse(blessing.selected_matches(native,s.detector,changed,rows,2,b))
        with patch.object(native,'_growth_selected_slot',return_value=2):
            self.assertTrue(blessing.selected_matches(native,s.detector,changed,rows,2,b))
    def test_fake_selection_then_real_insufficient_screen_does_not_upgrade(self):
        a=self.frame('blessing_list_1.jpg');b=self.frame('blessing_list_2.jpg')
        c=self.frame('blessing_rabbit_slot1_1.jpg');d=self.frame('blessing_rabbit_slot1_2.jpg')
        s=Service([a,b,c,d]);original=s.detector;identity='fake-blessing-test';blessing._cursor[identity]=1
        targets={'1번':{'enabled':True,'enhance':49,'breakthrough':0}}
        only=[row for row in native.inspect_growth_equipment(s.detector,a,blessing=True) if row['index']==2]
        with patch.object(blessing,'worn_candidates',return_value=only),patch.dict(sys.modules,{'owner_growth_current':SimpleNamespace(observe_value=lambda *a,**k:None)}),patch.object(native,'read_growth_equipment_detail',return_value={'enhancement':25,'materials':'재료 부족'}):
            self.assertFalse(blessing.run_blessing(s,s.context,identity,targets,slot_reader=lambda root,frame:1))
        self.assertEqual(len(s.actions),1);self.assertIs(s.detector,original)
    def test_fake_sufficient_selected_slot_invokes_once_and_reconciles(self):
        from owner_gear_intent_store_candidate import IntentStore
        from owner_gear_settings_candidate import Store
        a=self.frame('blessing_list_1.jpg');b=self.frame('blessing_list_2.jpg')
        c=self.frame('blessing_rabbit_slot1_1.jpg');d=self.frame('blessing_rabbit_slot1_2.jpg')
        s=Service([a,a,b,c,d,c,d,c,c,c,d,c,d]);original=s.detector;identity='fake-blessing-allow';blessing._cursor[identity]=1
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            root=Path(temp);config=root/'profiles/DKB/ocr_regions.json';config.parent.mkdir(parents=True)
            config.write_bytes((bootstrap.A/'profiles/DKB/ocr_regions.json').read_bytes());s.adapter.project.root=root
            detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_BLESSING_NAMES))
            active=native.GROWTH_BLESSING_EXEC_BUTTONS[0];detector.templates[active]=c[1:10,1:10].copy()
            real_find=detector.find
            def find(name,frame,**kw):
                if name==active:return (5,5,(1,1,10,10))
                if name in native.GROWTH_BLESSING_EXEC_BUTTONS:return None
                return real_find(name,frame,**kw)
            detector.find=find
            def detail(*args,**kwargs):return {'enhancement':26 if len(s.actions)>1 else 25,'materials':'재료 충분'}
            targets={'1번':{'enabled':True,'enhance':26,'breakthrough':0}}
            only=[row for row in native.inspect_growth_equipment(detector,a,blessing=True) if row['index']==2]
            with patch.object(blessing,'worn_candidates',return_value=only),patch('roi_runtime.RoiDetector',return_value=detector),patch.object(native,'read_growth_equipment_detail',side_effect=detail):
                self.assertFalse(blessing.run_blessing(s,s.context,identity,targets,slot_reader=lambda root,frame:1))
            self.assertEqual(len(s.actions),2);self.assertIs(s.detector,original)
            path=Store(root,identity).path
            self.assertIsNone(IntentStore(path.with_name(path.stem+'-intent.json')).pending())

if __name__=='__main__':unittest.main()
