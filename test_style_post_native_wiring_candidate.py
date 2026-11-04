"""Fake worker wiring checks; no live game interaction or resource input."""
import sys,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
import owner_timetable as timetable
import owner_task_flow as flow
import owner_skill_growth_candidate as style

class Context:
 def __init__(self):self.stop=threading.Event()
 def checkpoint(self):
  if self.stop.is_set():raise RuntimeError('stopped')

class Adapter:
 def __init__(self,result=True):
  self.values={'auto_growth.equipment.enabled':True,'auto_growth.blessing.enabled':False,'auto_growth.taoist.enabled':True}
  self.events=[];self.result=result;self.mode='auto_mode'
 def get_due_schedules(self):return []
 def exit_sleep_mode(self,*args):pass
 def _run_auto_features(self,context,inputs,**kwargs):
  self.events.extend(['native-entry','native-equipment','native-field-return'])
  return self.result

class Wiring(unittest.TestCase):
 def test_schedule_runs_once_after_outer_return_on_same_worker(self):
  adapter=Adapter();old=adapter.values;ctx=Context();tid=threading.get_ident()
  def run(a,c,i):
   self.assertEqual(threading.get_ident(),tid)
   self.assertEqual(a.events[-1],'native-field-return');a.events.append('style')
   return []
  with patch.object(style,'run_after_native',side_effect=run):
   self.assertTrue(timetable.invoke(adapter,timetable.BY_KEY['gear'],ctx,object()))
  self.assertEqual(adapter.events,['native-entry','native-equipment','native-field-return','style'])
  self.assertIs(adapter.values,old)
 def test_schedule_native_failure_never_runs_style(self):
  adapter=Adapter(False);old=adapter.values
  with patch.object(style,'run_after_native',side_effect=AssertionError('must not run')):
   self.assertFalse(timetable.invoke(adapter,timetable.BY_KEY['gear'],Context(),object()))
  self.assertIs(adapter.values,old)
 def test_quest_worker_runs_style_after_outer_return_and_restores_values(self):
  adapter=Adapter();old=adapter.values;ctx=Context();inputs=object()
  adapter._owner_pending_services={'context':ctx,'inputs':inputs,'keys':{'auto_growth.taoist.enabled'}}
  def ordinary(a,c,i,**kw):a.events.extend(['native-entry','native-field-return']);return True
  def run(a,c,i):
   self.assertEqual(a.events[-1],'native-field-return');self.assertIs(c,ctx);self.assertIs(i,inputs)
   a.events.append('style');return []
  with patch('owner_schedule_priority.hold_reason',return_value=None),patch.object(timetable,'scheduled_call',side_effect=lambda fn,label,args,kwargs,adapter:fn(*args,**kwargs)),patch.object(style,'run_after_native',side_effect=run):
   self.assertTrue(flow.dispatch(adapter,ctx,ordinary))
  self.assertEqual(adapter.events,['native-entry','native-field-return','style']);self.assertIs(adapter.values,old)
 def test_quest_native_failure_does_not_run_style(self):
  adapter=Adapter();ctx=Context();adapter._owner_pending_services={'context':ctx,'inputs':object(),'keys':{'auto_growth.taoist.enabled'}}
  with patch('owner_schedule_priority.hold_reason',return_value=None),patch.object(style,'run_after_native',side_effect=AssertionError('must not run')):
   flow.dispatch(adapter,ctx,lambda *a,**k:False)
 def test_cancel_or_unexpected_navigation_failure_propagates(self):
  adapter=Adapter()
  with patch.object(style,'run_after_native',side_effect=RuntimeError('navigation failed')):
   with self.assertRaisesRegex(RuntimeError,'navigation failed'):style.dispatch_after_native(adapter,Context(),object())
 def test_quest_respects_scheduled_hold(self):
  adapter=Adapter();ctx=Context();adapter._owner_pending_services={'context':ctx,'inputs':object(),'keys':{'auto_growth.taoist.enabled'}}
  with patch('owner_schedule_priority.hold_reason',return_value=None),patch.object(timetable,'scheduled_call',return_value=True),patch.object(style,'run_after_native',side_effect=AssertionError('held job')):
   self.assertTrue(flow.dispatch(adapter,ctx,lambda *a,**k:True))

if __name__=='__main__':unittest.main(verbosity=2)
