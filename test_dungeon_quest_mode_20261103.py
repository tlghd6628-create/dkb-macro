"""Scheduled dungeons during quests: real native dispatcher with fake entries, never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from biol_base.session import Context
import owner_timetable as timetable
from owner_timetable import BY_KEY,DUNGEON_JOBS,idle_once,invoke
from owner_work_resume import ResumeWork
import project_adapter.secret_folktale as folktale,project_adapter.secret_exploration as exploration
from project_adapter._entry import Adapter as Native

ROOT=bootstrap.T/'test_scratch/no-test-reservations'

def context(ran=None):
 c=Context(threading.Event(),threading.Event())
 c.run_action=lambda key,operation:((ran.append(key) if ran is not None else None),operation())[1]
 return c

def real(values,mode,order):
 class Real:
  _run_auto_features=Native._run_auto_features
  project=S(app_id='DKB',code='DKB',root=ROOT)
  def get_due_schedules(self):return []
  def run_town_return(self,*a,**k):order.append('town');return True
  def run_favorite_hunt(self,*a,**k):order.append('hunt');return True
  def __getattr__(self,name):raise AttributeError('fixture has no '+name)
 adapter=Real();adapter.values=values;adapter.mode=mode
 return adapter

class Enter(unittest.TestCase):
 CASES=(('daily_dungeon','auto_challenge.secret_exploration.enabled',exploration,'run_secret_exploration',lambda kw:kw.get('variant') is None),
        ('weekly_dungeon','auto_challenge.secret_folktale_5h.enabled',folktale,'run_folktale_exploration',lambda kw:kw=={'kind':'5h'}),
        ('daily24_dungeon','auto_challenge.secret_exploration_always.enabled',exploration,'run_secret_exploration',lambda kw:kw.get('variant')=='daily24h'))
 def test_every_scheduled_dungeon_enters_from_either_quest_mode(self):
  for mode in ('main_quest','sub_quest','auto_mode'):
   for key,setting,module,name,expected in self.CASES:
    with self.subTest(mode=mode,job=key):
     order=[];seen=[]
     def entry(adapter,c,i,**kw):seen.append(adapter.mode);order.append(kw);return True
     adapter=real({setting:True,'auto_rewards.mail.enabled':True},mode,order)
     with patch.object(module,name,entry):invoke(adapter,BY_KEY[key],context(),Mock())
     self.assertEqual(order[0],'town');self.assertEqual(len(order),2,order);self.assertTrue(expected(order[1]),order)
     self.assertEqual(seen,['auto_mode']);self.assertEqual(adapter.mode,mode)
 def test_mode_comes_back_when_the_dungeon_fails(self):
  adapter=real({'auto_challenge.secret_folktale_5h.enabled':True},'sub_quest',[])
  with patch.object(folktale,'run_folktale_exploration',side_effect=RuntimeError('fixture')),self.assertRaisesRegex(RuntimeError,'fixture'):
   invoke(adapter,BY_KEY['weekly_dungeon'],context(),Mock())
  self.assertEqual(adapter.mode,'sub_quest')
 def test_a_switched_off_dungeon_still_enters_nothing(self):
  adapter=real({'auto_challenge.secret_folktale_5h.enabled':False},'sub_quest',order:=[])
  with patch.object(folktale,'run_folktale_exploration') as entry:invoke(adapter,BY_KEY['weekly_dungeon'],context(),Mock())
  entry.assert_not_called()
 def test_other_jobs_keep_their_mode(self):
  seen=[]
  adapter=real({},'sub_quest',[])
  adapter._run_auto_features=None
  with patch.object(type(adapter),'_run_auto_features',lambda self,c,i,**k:seen.append(self.mode) or True):
   invoke(adapter,BY_KEY['blessing'],context(),Mock())
  self.assertEqual(seen,['sub_quest'])

class Return(unittest.TestCase):
 def run_once(self,mode,key):
  job=BY_KEY[key];plan=S(values={},due=lambda:[job],reason=lambda k:None,state={key:{'at':'2026-11-03T09:00:00+09:00'}})
  adapter=S(mode=mode,values={},project=S(root=ROOT),exit_sleep_mode=Mock(),run_favorite_hunt=Mock(return_value=True))
  called=[]
  def scheduled(fn,label,args,kwargs,a,**kw):called.append(label);return True
  with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'character_mismatch',return_value=False),\
       patch.object(timetable,'scheduled_call',scheduled),patch('owner_schedule_priority.hold_reason',return_value=None),\
       patch('owner_chore_transition.ancillary_field_ready',return_value=True):
   try:result=idle_once(adapter,context(),Mock())
   except ResumeWork as resume:result=resume
  self.assertEqual(called,[job.label])
  return result,adapter
 def test_quest_mode_resumes_the_same_quest_after_a_dungeon(self):
  for mode in ('main_quest','sub_quest'):
   for key in DUNGEON_JOBS:
    result,adapter=self.run_once(mode,key)
    self.assertIsInstance(result,ResumeWork);self.assertEqual(result.mode,mode);self.assertFalse(result.allow_growth)
    adapter.run_favorite_hunt.assert_not_called()
 def test_hunting_still_returns_to_its_hunt_spot(self):
  result,adapter=self.run_once('auto_mode','weekly_dungeon')
  self.assertIs(result,True);adapter.run_favorite_hunt.assert_called_once()
 def test_other_jobs_do_not_restart_the_quest(self):
  result,adapter=self.run_once('sub_quest','blessing')
  self.assertIs(result,True);adapter.run_favorite_hunt.assert_not_called()

class Boundary(unittest.TestCase):
 def test_the_quest_controller_and_route_loop_catch_the_resume(self):
  for name in ('owner_mission_controller.py','owner_routes.py'):
   self.assertIn('except ResumeWork',(bootstrap.T/name).read_text(encoding='utf-8-sig'))

if __name__=='__main__':unittest.main()
