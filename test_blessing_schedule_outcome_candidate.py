import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
import owner_timetable as timetable

class Planner:
 def __init__(self):self.state={'blessing':{}};self.values={};self.finished=[]
 def reason(self,key):return None
 def begin(self,key):pass
 def finish(self,key,ok,*,unverified=False):self.finished.append((key,ok,unverified))

class Tests(unittest.TestCase):
 def run_case(self,state,result=True):
  plan=Planner();adapter=SimpleNamespace(project=SimpleNamespace(root='unused'),mode='auto_mode')
  def original():adapter._owner_blessing_policy_outcome={'state':state};return result
  with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'config',return_value={}),patch.object(timetable,'enabled',return_value=True):
   self.assertEqual(timetable.scheduled_call(original,'가호',(),{},adapter,timed_dispatch=True),result)
  return plan.finished
 def test_unverified_policy_not_reported_as_proven_equip(self):
  self.assertEqual(self.run_case('processed_unverified'),[('blessing',True,True)])
  self.assertEqual(self.run_case('hold_identity'),[('blessing',True,True)])
 def test_policy_disabled_preserves_native_reward_success(self):
  self.assertEqual(self.run_case('disabled'),[('blessing',True,False)])
 def test_native_failure_preserves_failure(self):
  self.assertEqual(self.run_case('native_unconfirmed',False),[('blessing',False,False)])
 def test_style_hold_and_unverified_are_not_claimed_complete(self):
  for state in ('held','processed_unverified'):
   plan=Planner();plan.state['gear']={};adapter=SimpleNamespace(project=SimpleNamespace(root='unused'),mode='auto_mode')
   def original():adapter._owner_style_growth_outcome={'state':state};return True
   with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'config',return_value={}),patch.object(timetable,'enabled',return_value=True):
    self.assertTrue(timetable.scheduled_call(original,'성장 장비·가호',(),{},adapter,timed_dispatch=True))
   self.assertEqual(plan.finished,[('gear',True,True)])
if __name__=='__main__':unittest.main()
