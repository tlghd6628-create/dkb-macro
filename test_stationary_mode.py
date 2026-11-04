exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest,tempfile,json,logging
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_mission_controller as m
from owner_hunt_rules_candidate import ConfiguredHuntRules
from project_adapter._entry import Adapter
from project_adapter.main_quest import BoundedMainQuestRunner
class Tests(unittest.TestCase):
 def identity(self,root):
  path=Path(root)/'settings/manager_identity.json';path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps({'server_name':'테스트','character_name':'검증'},ensure_ascii=False),encoding='utf-8')
 def test_auto_mode_disables_quest_catalog_and_fixes_slot(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.identity(root);ConfiguredHuntRules(root).store([],2)
   seen=[]
   def original(a,c,i):seen.append((a._owner_catalog_enabled,a._owner_requested_quest_mode,a._owner_stationary_mode));return 'ok'
   def prior(*args):return True
   gui=NS(logger=logging.Logger('stationary-test'),root=NS(bind=lambda *a,**k:None));a=NS(mode='auto_mode',project=NS(root=root),run_favorite_hunt=prior,get_due_schedules=lambda:[],server_scheduler=None);ctx=NS(checkpoint=lambda:None)
   with patch.object(Adapter,'run',original),patch.object(BoundedMainQuestRunner,'handle_progress',lambda *a,**k:None),patch.object(BoundedMainQuestRunner,'request_next_mode',lambda *a,**k:None),patch('owner_quest_clicks.install'):
    m.install(gui);self.assertEqual(Adapter.run(a,ctx,None),'ok')
   self.assertEqual(seen,[(False,None,True)]);self.assertIs(a.run_favorite_hunt,prior);self.assertFalse(a._owner_stationary_mode)
 def test_slot_must_be_set_before_run(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   self.identity(root)
   gui=NS(logger=logging.Logger('stationary-test'),root=NS(bind=lambda *a,**k:None));a=NS(mode='auto_mode',project=NS(root=root),run_favorite_hunt=lambda *a:True,get_due_schedules=lambda:[])
   with patch.object(Adapter,'run',lambda *a:None),patch.object(BoundedMainQuestRunner,'handle_progress',lambda *a:None),patch.object(BoundedMainQuestRunner,'request_next_mode',lambda *a:None),patch('owner_quest_clicks.install'):
    m.install(gui)
    with self.assertRaisesRegex(RuntimeError,'저장 위치'):Adapter.run(a,object(),None)
if __name__=='__main__':unittest.main()
