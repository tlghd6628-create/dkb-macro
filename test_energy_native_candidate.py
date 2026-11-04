"""Stored frames and fake worker only; no game input."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
from project_adapter import achievement_rewards as native
from owner_energy_native_candidate import EnergyObserver,visible_stage,run_energy

class Context:
    def checkpoint(self):pass
    def wait(self,n):time.sleep(n)
class Service:
    def __init__(self,frame,root):
        self.frame=frame;self.adapter=SimpleNamespace(project=SimpleNamespace(root=root));self.actions=[]
        self.detector=RoiDetector(bootstrap.A/'profiles/DKB',[native.ENERGY_ACTIVE,native.ENERGY_BREAKTHROUGH,*native.ENERGY_TABS])
    def capture(self):return self.frame.copy()
    def check(self):pass
    def button(self,name,**kwargs):self.actions.append(('tab',name))
    def click_hit(self,hit):self.actions.append(('action',hit))
class Tests(unittest.TestCase):
    def frame(self,name):return np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/name).convert('RGB').crop((1,31,898,510))).copy()
    def test_highest_selected_stage_actual_images(self):
        for name,expected in [('energy_life_stage2_level3',2),('energy_dawn_stage5_level0',5),('energy_dream_stage2_level2',2),('energy_crimson_stage2_level1',2)]:
            for n in (1,2):self.assertEqual(visible_stage(self.frame(f'{name}_{n}.jpg')),expected)
    def test_stage_mark_missing_is_unknown(self):
        frame=self.frame('energy_life_stage2_level3_1.jpg');frame[82:102,864:884]=0
        self.assertIsNone(visible_stage(frame))
    def test_actual_material_shortage_never_runs_action(self):
        frame=self.frame('energy_life_stage2_level3_1.jpg');context=Context()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            service=Service(frame,temp);reader=lambda root,frame:{'name':'생명','stage':2,'level':3}
            obs=EnergyObserver(service,context,'test','생명',3,text_reader=reader)
            self.assertFalse(obs.state(frame)['active'])
            self.assertFalse(run_energy(service,context,'test',{'생명':{'enabled':True,'stage':3}},text_reader=reader))
            self.assertEqual(service.actions,[])
    def test_goal_already_reached_never_runs_action(self):
        frame=self.frame('energy_dawn_stage5_level0_1.jpg');context=Context()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            service=Service(frame,temp);reader=lambda root,frame:{'name':'여명','stage':5,'level':0}
            self.assertFalse(run_energy(service,context,'test',{'여명':{'enabled':True,'stage':5}},text_reader=reader))
            self.assertEqual(service.actions,[])
    def test_fake_active_action_is_one_and_result_reconciled(self):
        from owner_gear_intent_store_candidate import IntentStore
        from owner_gear_settings_candidate import Store
        frame=self.frame('energy_life_stage2_level3_1.jpg');frame[411:437,730:790]=0;context=Context()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            service=Service(frame,temp);name=native.ENERGY_ACTIVE
            service.detector.templates[name]=frame[1:10,1:10].copy()
            real=service.detector.find
            service.detector.find=lambda key,f,**kw: (5,5,(1,1,10,10)) if key==name else None if key==native.ENERGY_BREAKTHROUGH else real(key,f,**kw)
            reader=lambda root,frame:({'name':'생명','stage':3,'level':0} if any(x[0]=='action' for x in service.actions) else {'name':'생명','stage':2,'level':3})
            self.assertFalse(run_energy(service,context,'test',{'생명':{'enabled':True,'stage':3}},text_reader=reader))
            self.assertEqual([x[0] for x in service.actions],['action'])
            path=Store(temp,'test').path;self.assertIsNone(IntentStore(path.with_name(path.stem+'-energy-intent.json')).pending())
    def test_settings_change_prevents_fake_resource_action(self):
        from owner_gear_intent_store_candidate import IntentStore
        from owner_gear_settings_candidate import Store
        frame=self.frame('energy_life_stage2_level3_1.jpg');frame[411:437,730:790]=0;context=Context()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            service=Service(frame,temp);name=native.ENERGY_ACTIVE
            service.detector.templates[name]=frame[1:10,1:10].copy();real=service.detector.find
            service.detector.find=lambda key,f,**kw: (5,5,(1,1,10,10)) if key==name else None if key==native.ENERGY_BREAKTHROUGH else real(key,f,**kw)
            reader=lambda root,frame:{'name':'생명','stage':2,'level':3}
            with self.assertRaisesRegex(RuntimeError,'설정'):
                run_energy(service,context,'test',{'생명':{'enabled':True,'stage':3}},text_reader=reader,settings_check=lambda:False)
            self.assertEqual(service.actions,[])
            path=Store(temp,'test').path;self.assertIsNone(IntentStore(path.with_name(path.stem+'-energy-intent.json')).pending())
    def test_disabled_goals_continue_native_worker_without_game_input(self):
        from owner_energy_native_candidate import install
        from owner_gear_settings_candidate import Store
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
            Store(temp,'test').write(Store(temp,'test').read())
            calls=[];module=SimpleNamespace(run_energy_entry=lambda *args,**kw:calls.append('original'))
            adapter=SimpleNamespace(project=SimpleNamespace(root=temp));install(module,lambda a:'test')
            result=module.run_energy_entry(adapter,Context(),object(),process=True)
            self.assertIs(result,True);self.assertEqual(calls,[])
            self.assertEqual(adapter._owner_energy_outcome,'목표 미설정 · 실행 건너뜀')
    def test_unknown_character_continues_with_explicit_hold(self):
        from owner_energy_native_candidate import install
        module=SimpleNamespace(run_energy_entry=lambda *args,**kw:False)
        adapter=SimpleNamespace(project=SimpleNamespace(root='unused'));install(module,lambda a:None)
        self.assertIs(module.run_energy_entry(adapter,Context(),object(),process=True),True)
        self.assertEqual(adapter._owner_energy_outcome,'캐릭터 확인 필요')

if __name__=='__main__':unittest.main()
