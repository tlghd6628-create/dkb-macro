from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import threading, unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_task_flow as f

class Tests(unittest.TestCase):
 def fixture(self,mode,due):
  ctx=NS(stop=threading.Event(),checkpoint=lambda:None)
  calls=[];progress=NS(due=lambda:due,attempted=lambda m:calls.append(('attempted',m)))
  adapter=NS(mode=mode,values={'auto_growth.equipment.enabled':True},
   _owner_progression=progress,exit_sleep_mode=lambda *a:calls.append('wake'))
  adapter._owner_pending_services={'context':ctx,'inputs':NS(),'keys':{'auto_growth.equipment.enabled'}}
  return adapter,ctx,calls
 def test_completed_milestones_do_not_reopen_gear_on_story_or_main(self):
  for mode in ('main_quest','sub_quest'):
   a,c,calls=self.fixture(mode,None)
   with patch('owner_schedule_priority.hold_reason',return_value=None):
    self.assertTrue(f.dispatch(a,c,lambda *args,**kw:calls.append('native')))
   self.assertEqual(calls,[])
 def test_due_milestone_marker_is_scoped_and_recorded_after_native_return(self):
  a,c,calls=self.fixture('sub_quest',45)
  def native(adapter,*args,**kw):calls.append(('native',adapter._owner_growth_milestone))
  with patch('owner_schedule_priority.hold_reason',return_value=None):f.dispatch(a,c,native)
  self.assertEqual(calls,['wake',('native',45),('attempted',45)])
  self.assertIsNone(a._owner_growth_milestone)
 def test_interrupted_milestone_is_not_recorded_and_marker_restores(self):
  a,c,calls=self.fixture('sub_quest',40);a._owner_growth_milestone=20
  def interrupted(*args,**kw):raise RuntimeError('interrupted')
  with patch('owner_schedule_priority.hold_reason',return_value=None),self.assertRaises(RuntimeError):
   f.dispatch(a,c,interrupted)
  self.assertEqual(calls,['wake']);self.assertEqual(a._owner_growth_milestone,20)

if __name__=='__main__':unittest.main()
