"""Trial routing only, fake handlers. No live input in this test."""
import bootstrap,tempfile,unittest,threading
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch,Mock
import owner_live_component_trial_20261103 as trial
class Trial(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
  self.adapter=S(mode='sub_quest',values={'auto_growth.equipment.enabled':True},project=S(root=Path(self.tmp.name)))
  self.context=S(checkpoint=lambda:None,stop=threading.Event())
 def routing(self,kind,field=True):
  return (patch('owner_schedule_priority.hold_reason',return_value=None),patch('owner_mission_controller.prepare'),
   patch('owner_mission_ui.MissionUI',return_value=S(normal=lambda:field)))
 def test_gear_calls_existing_job_with_unchanged_targets(self):
  a,b,c=self.routing('gear');before=dict(self.adapter.values)
  with a,b,c,patch('owner_timetable.invoke',return_value=False) as invoke:
   self.assertTrue(trial.run(self.adapter,self.context,None,'gear'))
  self.assertEqual(invoke.call_args.args[1].key,'gear');self.assertEqual(self.adapter.values,before)
 def test_equipment_calls_only_equipment_component_not_general_inventory(self):
  a,b,c=self.routing('equipment')
  with a,b,c,patch('owner_equip_runtime_install_candidate._run',return_value='confirmed') as equip,patch('owner_timetable.invoke',side_effect=AssertionError('no general job')):
   self.assertTrue(trial.run(self.adapter,self.context,None,'equipment'))
  equip.assert_called_once_with(self.adapter,self.context,None)
 def test_unknown_field_and_disabled_growth_never_call_action(self):
  a,b,c=self.routing('gear',False)
  with a,b,c,patch('owner_timetable.invoke') as invoke:
   with self.assertRaises(RuntimeError):trial.run(self.adapter,self.context,None,'gear')
   invoke.assert_not_called()
  self.adapter.values['auto_growth.equipment.enabled']=False
  with patch('owner_schedule_priority.hold_reason',return_value=None),patch('owner_mission_controller.prepare') as prep:
   with self.assertRaises(RuntimeError):trial.run(self.adapter,self.context,None,'gear')
   prep.assert_not_called()
if __name__=='__main__':unittest.main()
