"""Read-only isolated review of optional support wiring with fake GUI/modules."""
import sys, threading, types, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import owner_support

INSTALL_MODULES=('owner_controls','owner_incidents','owner_main','owner_performance',
 'owner_task_flow','owner_inventory','owner_coupons','owner_rewards','owner_progression',
 'owner_routes','owner_hunt','owner_work_resume','owner_town_return','owner_treasure',
 'owner_reconnect','owner_quest_tracker','owner_equipment_boxes','owner_startup_stage',
 'owner_diagnostic_repairs','owner_scene_archive','owner_quest_watchdog','owner_schedule_priority',
 'owner_timetable','owner_restart_memory','owner_skill_goal','owner_schedule_ui','owner_membership',
 'owner_mission_controller','owner_dialogue','owner_hunt_settings_candidate',
 'owner_feature_check_live_candidate','owner_feature_check_ui_candidate','owner_album_disabled','owner_program_runtime')

class Root:
    def __init__(self,fail_bind=False):self.name='';self.bindings=[];self.fail_bind=fail_bind
    def winfo_children(self):return []
    def cget(self,name):return ''
    def title(self,value=None):
        if value is not None:self.name=value
        return self.name
    def bind(self,name,callback,add=None):
        if self.fail_bind:raise RuntimeError('binding failed')
        self.bindings.append(callback)

class Collector:
    instances=[]
    def __init__(self,path):self.path=path;self.closed=False;self.events=[];self.fail=False;self.instances.append(self)
    def mark(self):return 0.0
    def record(self,*args,**kwargs):
        if self.fail:raise RuntimeError('collection failed')
        self.events.append(args)
    def close(self,timeout=0):self.closed=True

class Review(unittest.TestCase):
    def setUp(self):
        self.UI=type('UI',(),{'frame':lambda self:'frame','rows':lambda self:[],
            'open':lambda self:'open','wheel':lambda self:'wheel','selected':lambda self:'selected'})
        self.mission=types.ModuleType('owner_mission_ui');self.mission.MissionUI=self.UI;self.mission.markers=lambda f,n:[]
        self.modules={n:types.SimpleNamespace(install=lambda gui:None) for n in INSTALL_MODULES}
        self.modules['owner_mission_schedule_bridge_candidate']=types.SimpleNamespace(install=lambda:None)
        self.modules['owner_mission_ui']=self.mission
        self.modules['owner_image_perf_candidate']=types.SimpleNamespace(ImagePerf=Collector)
        self.patch=patch.dict(sys.modules,self.modules);self.patch.start();self.addCleanup(self.patch.stop)
        self.messages=[]
        self.gui=types.SimpleNamespace(root=Root(),closed=threading.Event(),
            project=types.SimpleNamespace(root='.'),logger=types.SimpleNamespace(exception=self.messages.append))
        self.addCleanup(lambda: getattr(self.gui,'_owner_image_perf',types.SimpleNamespace(close=lambda:None)).close())

    def test_normal_start_and_destroy(self):
        owner_support.finish_local_ui(self.gui)
        self.assertEqual(self.UI().frame(),'frame')
        collector=Collector.instances[-1];self.assertEqual(collector.events[0][0],'capture')
        self.gui.root.bindings[-1](types.SimpleNamespace(widget=object()));self.assertFalse(collector.closed)
        self.gui.root.bindings[-1](types.SimpleNamespace(widget=self.gui.root));self.assertTrue(collector.closed)
        self.assertFalse(getattr(self.UI.frame,'_owner_mission_perf_wrapper',False))

    def test_collector_failure_preserves_user_operation(self):
        owner_support.finish_local_ui(self.gui);Collector.instances[-1].fail=True
        self.assertEqual(self.UI().frame(),'frame');self.assertEqual(self.UI().open(),'open')

    def test_install_failure_still_finishes_ui(self):
        fake=types.SimpleNamespace(install=lambda *a: (_ for _ in ()).throw(RuntimeError('install')))
        with patch.dict(sys.modules,{'owner_mission_perf_adapter_candidate':fake}):owner_support.finish_local_ui(self.gui)
        self.assertTrue(Collector.instances[-1].closed);self.assertTrue(self.messages)
        self.assertEqual(self.UI().frame(),'frame')

    def test_bind_failure_rolls_back_and_retry_succeeds(self):
        self.gui.root.fail_bind=True;owner_support.finish_local_ui(self.gui)
        self.assertTrue(Collector.instances[-1].closed);self.assertTrue(self.messages)
        self.assertFalse(getattr(self.UI.frame,'_owner_mission_perf_wrapper',False))
        self.assertEqual(self.UI().frame(),'frame')
        self.gui.root.fail_bind=False
        owner_support.finish_local_ui(self.gui)
        self.assertTrue(getattr(self.UI.frame,'_owner_mission_perf_wrapper',False))
        self.assertFalse(Collector.instances[-1].closed)
        self.assertEqual(self.UI().frame(),'frame')

if __name__=='__main__':unittest.main()
