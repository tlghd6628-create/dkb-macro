"""Fake existing-worker scheduling. Never actual wake/resource input."""
import bootstrap,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_timetable as t

class SleepResume(unittest.TestCase):
 def trial(self,after,due=True):
  calls=[];context=S(checkpoint=lambda:None);inputs=S(held=());frame=['sleep']
  plan=S(values={'auto_growth.equipment.enabled':True},due=lambda:[t.BY_KEY['gear']] if due else [],
   state={'gear':{'at':'test','growth_recheck':True}},reason=lambda k:None)
  def wake(*a):calls.append('wake');frame[0]=after
  adapter=S(project=S(root=Path('never')),values=plan.values,mode='auto_mode',exit_sleep_mode=wake,
   run_favorite_hunt=lambda *a:True)
  adapter._owner_mission_ui=S(context=context,inputs=inputs,frame=lambda:frame[0],normal_frame=lambda f:f=='field')
  def scheduled(original,*a,**kw):calls.append('dispatch');return original()
  with patch('owner_schedule_priority.hold_reason',return_value=None),patch('owner_emote_dispatch.navigation_open',return_value=False),\
       patch.object(t,'character_mismatch',return_value=False),patch.object(t,'planner',return_value=plan),\
       patch.object(t,'scheduled_call',side_effect=scheduled),patch.object(t,'invoke',return_value=True),\
       patch.object(t,'post_equip_growth',return_value=False):
   result=t.idle_once(adapter,context,inputs)
  return result,calls
 def test_sleep_wakes_before_field_proof_and_due_growth(self):
  self.assertEqual(self.trial('field'),(True,['wake','dispatch']))
 def test_black_after_wake_does_not_begin_job(self):
  self.assertEqual(self.trial('black'),(False,['wake']))
 def test_no_due_work_does_not_wake_for_nothing(self):
  self.assertEqual(self.trial('field',False),(False,[]))

if __name__=='__main__':unittest.main()
