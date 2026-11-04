"""Actual saved menu frames and fake service; no game input."""
import sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native, growth_equipment_extra as extra
from owner_gear_awaken_observer_candidate import AwakeningObserver,find_awaken_list_item,native_extra_readers_factory

class Context:
    def checkpoint(self):pass
    def wait(self,value):time.sleep(value)
class Service:
    def __init__(self,frames):
        self.frames=iter(frames);self.detector=RoiDetector(bootstrap.A/'profiles/DKB',
          [*native.GROWTH_EQUIPMENT_NAMES,native.GROWTH_MATERIAL_RANGE,extra.AWAKE_BUTTON])
    def capture(self):return next(self.frames).copy()
    def check(self):pass
class Tests(unittest.TestCase):
    def image(self,name):return np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/name).convert('RGB').crop((1,31,898,510))).copy()
    def test_real_hat_identity_and_shortage_stay_non_executable(self):
        pre=self.image('gear_awaken_list_20261101.jpg')
        first=self.image('gear_awaken_hat_1.jpg');second=self.image('gear_awaken_hat_2.jpg')
        service=Service([first,second]);rows=native.inspect_growth_equipment(service.detector,pre)
        source=SimpleNamespace(service=service,context=Context(),native=native,character='test',sequence=0,
            ticket={'index':1,'grade':'일반','identity':'hat'},identity_reader=SimpleNamespace(pre=pre,pre_rows=rows))
        observer=AwakeningObserver(source)
        with patch('owner_gear_awaken_observer_candidate.read_zero_to_one',return_value={'current':0}):out=observer.read_pair()
        self.assertTrue(out['screen_proof']);self.assertEqual(out['first'].awakening,0)
        self.assertFalse(out['first'].awaken_available);self.assertFalse(out['active_pair_verified'])
        self.assertFalse(observer.verify_final(first,out,'awaken'))
    def test_wrong_item_never_proves_identity(self):
        pre=self.image('gear_awaken_list_20261101.jpg');frame=self.image('gear_awaken_hat_1.jpg')
        service=Service([frame]);rows=native.inspect_growth_equipment(service.detector,pre)
        source=SimpleNamespace(service=service,context=Context(),native=native,character='test',sequence=0,
            ticket={'index':2,'grade':'일반','identity':'other'},identity_reader=SimpleNamespace(pre=pre,pre_rows=rows))
        self.assertFalse(AwakeningObserver(source)._same_item(frame))
    def test_list_icon_match_and_ambiguous_duplicate_hold(self):
        pre=self.image('gear_awaken_list_20261101.jpg');service=Service([pre])
        rows=native.inspect_growth_equipment(service.detector,pre)
        source=SimpleNamespace(native=native,ticket={'index':1},identity_reader=SimpleNamespace(pre=pre,pre_rows=rows))
        self.assertEqual(find_awaken_list_item(source,pre,service.detector)['index'],1)
        changed=pre.copy();s=rows[0]['slot'];t=rows[1]['slot']
        x,y=s['cell_x']+8,s['cell_y']+8;u,v=t['cell_x']+8,t['cell_y']+8
        changed[v:v+18,u:u+18]=changed[y:y+18,x:x+18]
        self.assertIsNone(find_awaken_list_item(source,changed,service.detector))
    def test_existing_item_navigation_select_and_shortage_hold(self):
        pre=self.image('gear_awaken_list_20261101.jpg');hat1=self.image('gear_awaken_hat_1.jpg');hat2=self.image('gear_awaken_hat_2.jpg')
        service=Service([hat1,pre,pre,hat1,hat2]);original=service.detector
        context=Context();service.context=context;service.adapter=SimpleNamespace(project=SimpleNamespace(root=bootstrap.A))
        rows=native.inspect_growth_equipment(service.detector,pre)
        class Identity:
            pre_rows=rows
            def __init__(self):self.pre=pre
            def __call__(self,frame,index,selected):return 'hat'
        source=SimpleNamespace(service=service,context=context,native=native,character='test',sequence=0,
            ticket={'index':1,'grade':'일반','identity':'hat'},identity_reader=Identity())
        service.adapter._owner_growth_observer=source
        service.adapter._owner_gear_awaken_result_reader=lambda frame:None
        actions=[];service.button=lambda name,**kw:actions.append(('tab',name))
        service.click_hit=lambda hit:actions.append(('select',hit))
        with patch('owner_gear_awaken_observer_candidate.AWAKEN_RESULT_READER_VERIFIED',True):
            factory=native_extra_readers_factory(service,context,'test',{'일반':{'awaken':1}},'awaken')
        self.assertEqual(len(factory),4)
        with patch('owner_gear_awaken_observer_candidate.read_zero_to_one',return_value={'current':0}):out=factory[0]()
        self.assertTrue(out['screen_proof']);self.assertFalse(out['first'].awaken_available)
        self.assertEqual([a[0] for a in actions],['tab','select'])
        factory[2]();self.assertIs(service.detector,original)
    def test_default_factory_blocks_until_actual_post_result_reader_verified(self):
        self.assertIsNone(native_extra_readers_factory(None,None,'test',{},'awaken'))
        service=SimpleNamespace(adapter=SimpleNamespace())
        with patch('owner_gear_awaken_observer_candidate.AWAKEN_RESULT_READER_VERIFIED',True):
            self.assertIsNone(native_extra_readers_factory(service,None,'test',{},'awaken'))
    def test_post_reader_is_independent_and_never_guesses_without_validator(self):
        pre=self.image('gear_awaken_list_20261101.jpg');first=self.image('gear_awaken_hat_1.jpg');second=self.image('gear_awaken_hat_2.jpg')
        rows=native.inspect_growth_equipment(Service([pre]).detector,pre)
        def source(service):return SimpleNamespace(service=service,context=Context(),native=native,character='test',sequence=0,
            ticket={'index':1,'grade':'일반','identity':'hat'},identity_reader=SimpleNamespace(pre=pre,pre_rows=rows))
        service=Service([first,second]);self.assertFalse(AwakeningObserver(source(service)).read_result_pair()['screen_proof'])
        service=Service([first,second]);observer=AwakeningObserver(source(service),result_reader=lambda frame:{'current':1})
        result=observer.read_result_pair();self.assertTrue(result['screen_proof'])
        self.assertEqual((result['first'].awakening,result['second'].awakening),(1,1))
        # The stage is simulated; the real screenshots do not establish it.

if __name__=='__main__':unittest.main()
