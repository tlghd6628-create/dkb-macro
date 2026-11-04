exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest,json,copy
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_main
from gui_settings import SettingsModel
class Cases(unittest.TestCase):
 def test_three_modes_and_schema_remains_valid(self):
  schema=json.loads((A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8-sig'))
  model=SettingsModel(schema,capabilities=lambda k:True)
  gui=NS(load_settings_model=lambda:model,root=NS(title=lambda *a:'r20'),_settings_schema_revision=0)
  with patch.object(owner_main,'MainPanel',return_value=object()):owner_main.install(gui)
  self.assertEqual([x['id'] for x in gui._live_schema['modes']],['main_quest','sub_quest','auto_mode'])
  SettingsModel(gui._live_schema,capabilities=lambda k:True)
 def test_mode_changes_are_rejected_while_running(self):
  gui=NS(session=NS(snapshot=lambda:{'status':'running','worker_alive':True}),set_execution_mode=lambda mode:self.fail('must not change'))
  self.assertFalse(owner_main.choose(gui,'auto_mode'))
 def test_mode_can_be_selected_stopped(self):
  gui=NS(session=NS(snapshot=lambda:{'status':'stopped','worker_alive':False}),set_execution_mode=lambda mode:mode=='auto_mode')
  self.assertTrue(owner_main.choose(gui,'auto_mode'))
if __name__=='__main__':unittest.main()
