"""Native growth entry + saved real tab frames with fake input. No game, no resource input."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_gear_native_install_candidate as gear
import owner_gear_extra_runtime_candidate as extras
from project_adapter import market_inventory as native,growth_equipment_extra as native_extra
from roi_runtime import RoiDetector
from owner_native_contracts import region_names

LIVE=Path(__file__).resolve().parent/'image_scope_20261104/live'
def frame(name):return np.array(Image.open(LIVE/name).convert('RGB'))
TARGETS={'일반':{'enabled':True,'awaken':1,'breakthrough':3},'희귀':{'enabled':True,'awaken':1,'breakthrough':3},'영웅':{'enabled':False,'awaken':1,'breakthrough':2}}

class Service:
    def __init__(self,frames):
        self.frames=frames;self.clicks=[];self.buttons=[];self.logs=[]
        import time
        self.adapter=S(project=S(root=bootstrap.A));self.context=S(checkpoint=lambda:None,wait=lambda s:time.sleep(.02))
        self.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(region_names('gear_extra')))
    def check(self):pass
    def capture(self):return self.frames[0].copy()
    def click_hit(self,hit):self.clicks.append(hit)
    def button(self,name,**k):self.buttons.append(name)

class Install(unittest.TestCase):
    def fake_module(self,result=False):
        calls=[];module=S(run_growth_equipment=lambda service,*,blessing=False:calls.append(('route',blessing)) or result)
        return module,calls
    def test_extras_run_after_the_enhance_route_on_the_same_call(self):
        module,calls=self.fake_module();extra=S(run_equipment_extras=Mock())
        factory=Mock(return_value=None)
        def enhance(service,*,blessing=False):calls.append('enhance');return False
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir()
            from owner_gear_settings_candidate import Store
            store=Store(root,'c');document=store.read();document['grades']['희귀'].update(enabled=True,awaken=1);store.write(document)
            fn=gear.wrap_extras_decorator(lambda route:route,lambda s:'c',factory)(enhance)
            service=S(context=S(checkpoint=lambda:None,wait=lambda s:None),check=lambda:None,adapter=S(project=S(root=root)),log=lambda m:calls.append(m))
            self.assertFalse(fn(service))
        self.assertEqual(calls[0],'enhance');self.assertTrue(factory.called);extra.run_equipment_extras.assert_not_called()
    def test_install_replaces_the_route_and_leaves_native_extras_alone(self):
        module,_=self.fake_module();native_fn=Mock();extra=S(run_equipment_extras=native_fn)
        gear.install(module,lambda s:'c',Mock(),extra_module=extra,extra_readers_factory=Mock())
        self.assertIs(extra.run_equipment_extras,native_fn)
        self.assertTrue(module.run_growth_equipment._owner_gear_native_candidate)
    def test_blessing_pass_never_reaches_extras(self):
        factory=Mock();route=Mock(return_value=True)
        fn=gear.wrap_extras_decorator(lambda r:r,lambda s:'c',factory)(route)
        self.assertTrue(fn(S(),blessing=True));factory.assert_not_called()
    def test_a_pending_input_stops_the_next_item(self):
        factory=Mock(return_value=(lambda:None,lambda *a:False,lambda:None,lambda:None))
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir()
            from owner_gear_settings_candidate import Store
            store=Store(root,'c');document=store.read();document['grades']['희귀'].update(enabled=True,awaken=1);store.write(document)
            fn=gear.wrap_extras_decorator(lambda r:r,lambda s:'c',factory)(lambda *a,**k:False)
            service=S(context=S(checkpoint=lambda:None,wait=lambda s:None),check=lambda:None,adapter=S(project=S(root=root)),log=lambda m:None)
            with patch.object(gear,'run_configured_step',return_value='hold_pending'),patch('owner_growth_reading.breakthrough_allowed',return_value=True):fn(service)
        self.assertEqual(factory.call_count,1)
    def test_every_listed_item_gets_a_turn_then_stops(self):
        cleanup=Mock();seen=iter([(lambda:None,lambda *a:False,cleanup,lambda:None)]*3+[None]*9)
        factory=Mock(side_effect=lambda *a:next(seen))
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir()
            from owner_gear_settings_candidate import Store
            store=Store(root,'c');document=store.read();document['grades']['희귀'].update(enabled=True,awaken=1);store.write(document)
            fn=gear.wrap_extras_decorator(lambda r:r,lambda s:'c',factory)(lambda *a,**k:False)
            service=S(context=S(checkpoint=lambda:None,wait=lambda s:None),check=lambda:None,adapter=S(project=S(root=root)),log=lambda m:None)
            with patch.object(gear,'run_configured_step',return_value='hold_policy'),patch('owner_growth_reading.breakthrough_allowed',return_value=False):fn(service)
        self.assertEqual(factory.call_count,4);self.assertEqual(cleanup.call_count,3)

class RealTabs(unittest.TestCase):
    def source(self,name,kind,targets=TARGETS):
        service=Service([frame(name)])
        extras_tab=native_extra.AWAKE_TAB if kind=='awaken' else native_extra.BREAK_TAB
        return service,extras.tab_source(service,service.context,'c',targets,kind,extras_tab)
    def test_saved_awaken_tab_selects_one_worn_item_only(self):
        service,source=self.source('tab_awaken.png','awaken')
        self.assertIsNotNone(source);self.assertEqual(len(service.clicks),1);self.assertEqual(service.buttons,[])
        self.assertEqual(source.ticket['grade'] in ('일반','희귀'),True)
    def test_each_pass_visits_a_different_item(self):
        service,_=self.source('tab_awaken.png','awaken')
        tab=native_extra.AWAKE_TAB;seen=set()
        service._owner_extra_tried={}
        for _ in range(10):
            source=extras.tab_source(service,service.context,'c',TARGETS,'awaken',tab)
            if source is None:break
            self.assertNotIn(source.ticket['index'],seen);seen.add(source.ticket['index'])
        self.assertGreaterEqual(len(seen),3)
    def test_saved_empty_breakthrough_tab_has_no_target_and_no_click(self):
        service,source=self.source('tab_break.png','breakthrough')
        self.assertIsNone(source);self.assertEqual(service.clicks,[])
    def test_goal_zero_grade_is_never_selected(self):
        none={k:dict(v,awaken=0) for k,v in TARGETS.items()}
        service,source=self.source('tab_awaken.png','awaken',none)
        self.assertIsNone(source);self.assertEqual(service.clicks,[])
    def test_real_selected_screen_is_the_same_item_and_short_of_material(self):
        shot=Path(__file__).resolve().parent/'fixtures_image_scope/extra_awaken_selected.png'
        pre=frame('tab_awaken.png');post=np.array(Image.open(shot).convert('RGB'))
        service=Service([post]);service.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(region_names('gear_extra')))
        rows=native.inspect_growth_equipment(service.detector,pre)
        source=S(service=service,context=service.context,native=native,character='c',sequence=0,last_frames=[post],
                 ticket={'index':1,'grade':'희귀','identity':'x'},identity_reader=S(pre=pre,pre_rows=rows))
        observer=extras.ExtraObserver(source,'awaken')
        self.assertTrue(observer._same_item(post))
        state=observer._state(post)
        self.assertEqual((state['current'],state['next'],state['active']),(0,1,False))
        other=dict(source.ticket,index=2);source.ticket=other
        self.assertFalse(extras.ExtraObserver(source,'awaken')._same_item(post))
    def test_enhance_tab_presses_the_tab_instead(self):
        service=Service([frame('tab_enhance.png')])
        from unittest.mock import patch
        with patch.object(extras,'read_tabs',return_value=True):
            self.assertIsNone(extras.tab_source(service,service.context,'c',TARGETS,'awaken',native_extra.AWAKE_TAB))
        top=extras.TABS['awaken']
        self.assertEqual(service.buttons,[]);self.assertEqual(service.clicks,[(43,top+10,(14,top,73,top+20))])

if __name__=='__main__':unittest.main()
