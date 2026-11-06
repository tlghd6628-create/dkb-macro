"""Three-hour ledger and dungeon admission tests. No live game/consumption."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
import json,tempfile,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from biol_base.session import Context
import owner_reward_cycle as cycle
from owner_reward_context import decision,admit,JOBS,DUNGEONS
from owner_reward_action_test import prepare
from owner_startup_stage import parse_timer

GUIDE='auto_rewards.guide.enabled'


class LedgerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def test_first_run_then_exact_three_hours_after_restart(self):
  book=cycle.Ledger(self.root,'a');self.assertTrue(book.due(GUIDE,1000));book.record(GUIDE,'processed_unverified',1000)
  book=cycle.Ledger(self.root,'a');self.assertFalse(book.due(GUIDE,11799));self.assertTrue(book.due(GUIDE,11800))
 def test_character_scope_and_crash_running_record(self):
  cycle.Ledger(self.root,'a').record(GUIDE,'running',1000)
  self.assertFalse(cycle.Ledger(self.root,'a').due(GUIDE,1001));self.assertTrue(cycle.Ledger(self.root,'b').due(GUIDE,1001))
 def test_malformed_records_are_not_silently_cleared(self):
  path=self.root/'settings/owner-reward-cycle.json';path.parent.mkdir();path.write_text('invalid',encoding='utf-8')
  with self.assertRaises(ValueError):cycle.Ledger(self.root,'a')
  self.assertEqual(path.read_text(),'invalid')
 def test_period_gate_and_manual_test_use_same_entry(self):
  context=Context(threading.Event(),threading.Event());adapter=S(values={GUIDE:True},project=S(root=self.root));action=Mock(return_value=True)
  wrapped=cycle.wrap(action,GUIDE)
  with patch.object(cycle,'ledger',return_value=cycle.Ledger(self.root,'a')),patch.object(cycle,'admit',return_value=decision(False,None)),patch('owner_character_binding.mismatch',return_value=False),patch.object(cycle.time,'time',return_value=1000):
   self.assertTrue(wrapped(adapter,context,Mock()));self.assertTrue(wrapped(adapter,context,Mock()));self.assertEqual(action.call_count,1)
   cycle.LOCAL.manual=True
   try:self.assertTrue(wrapped(adapter,context,Mock()))
   finally:cycle.LOCAL.manual=False
  self.assertEqual(action.call_count,2)
 def test_ten_minute_hold_sends_no_action_and_does_not_use_period(self):
  context=Context(threading.Event(),threading.Event());adapter=S(values={GUIDE:True},project=S(root=self.root));action=Mock()
  book=cycle.Ledger(self.root,'a')
  with patch.object(cycle,'ledger',return_value=book),patch.object(cycle,'admit',return_value=decision(True,600)),patch('owner_character_binding.mismatch',return_value=False):
   self.assertTrue(cycle.wrap(action,GUIDE)(adapter,context,Mock()))
  action.assert_not_called();self.assertTrue(book.due(GUIDE,1000));self.assertFalse(book.path.exists())
 def test_off_does_not_read_clock_or_create_ledger(self):
  adapter=S(values={GUIDE:False});action=Mock()
  with patch.object(cycle,'admit') as admission,patch.object(cycle,'ledger') as book:
   self.assertTrue(cycle.wrap(action,GUIDE)(adapter,Mock(),Mock()))
  action.assert_not_called();admission.assert_not_called();book.assert_not_called()
 def test_inner_preinput_hold_restores_old_due_record(self):
  c=Context(threading.Event(),threading.Event());adapter=S(values={GUIDE:True});book=cycle.Ledger(self.root,'a')
  def held(*args):adapter._owner_reward_cycle_hold='비경 종료까지 10분 이하';return True
  with patch.object(cycle,'ledger',return_value=book),patch.object(cycle,'admit',return_value=decision(True,601)),patch('owner_character_binding.mismatch',return_value=False):
   cycle.wrap(held,GUIDE)(adapter,c,Mock())
  self.assertTrue(cycle.Ledger(self.root,'a').due(GUIDE,10000))
 def test_automatic_tick_uses_the_same_entry_and_does_not_advance_a_held_job(self):
  c=Context(threading.Event(),threading.Event());adapter=S(values={GUIDE:True},project=S(root=self.root),exit_sleep_mode=Mock(),_owner_initial_context=c)
  from owner_schedule_priority import LOCAL as priority
  previous=getattr(priority,'combat',None);priority.combat='비경·던전'
  try:
   for seconds,expected in ((1800,True),(600,False)):
    with patch('owner_schedule_priority.reservation_hold',return_value=None),patch.object(cycle,'ledger',return_value=cycle.Ledger(self.root,'a')),patch.object(cycle,'admit',return_value=decision(True,seconds)),patch('owner_reward_action_test.prepare') as prepare,patch('owner_reward_action_test.execute') as execute:
     self.assertIs(cycle.tick(adapter,c,S(held=())),expected)
     if expected:execute.assert_called_once();self.assertIs(execute.call_args.kwargs['manual'],False)
     else:execute.assert_not_called();prepare.assert_not_called()
  finally:priority.combat=previous
 def test_a_hold_in_the_entry_waits_and_an_unrun_step_is_recorded(self):
  # 20:36-20:37: 도사 수행록 was skipped as 미구현 every 7 s, then a boss-window hold stopped the whole program.
  c=Context(threading.Event(),threading.Event());adapter=S(values={GUIDE:True},project=S(root=self.root),exit_sleep_mode=Mock(),_owner_initial_context=c)
  from owner_schedule_priority import LOCAL as priority
  previous=getattr(priority,'combat',None);priority.combat='비경·던전'
  try:
   book=cycle.Ledger(self.root,'a')
   with patch('owner_schedule_priority.reservation_hold',return_value=None),patch.object(cycle,'ledger',return_value=book),patch.object(cycle,'admit',return_value=decision(True,1800)),patch('owner_reward_action_test.prepare'),        patch('owner_reward_action_test.execute',side_effect=RuntimeError('TEST 보류 · 필드 보스 예약 보호 (20:52)')):
    self.assertIs(cycle.tick(adapter,c,S(held=())),False)
   adapter._owner_reward_cycle_recheck=0
   with patch('owner_schedule_priority.reservation_hold',return_value=None),patch.object(cycle,'ledger',return_value=book),patch.object(cycle,'admit',return_value=decision(True,1800)),patch('owner_reward_action_test.prepare'),        patch('owner_reward_action_test.execute'),patch.object(cycle.time,'time',return_value=5000):
    self.assertIs(cycle.tick(adapter,c,S(held=())),True)
   self.assertEqual(book.rows[GUIDE]['state'],'skipped');self.assertFalse(book.due(GUIDE,5001))
   from biol_base.session import Cancelled
   with patch('owner_schedule_priority.reservation_hold',return_value=None),patch.object(cycle,'ledger',return_value=cycle.Ledger(self.root,'b')),patch.object(cycle,'admit',return_value=decision(True,1800)),patch('owner_reward_action_test.prepare'),        patch('owner_reward_action_test.execute',side_effect=Cancelled()):
    with self.assertRaises(Cancelled):cycle.tick(adapter,c,S(held=()))
  finally:priority.combat=previous

class AdmissionTests(unittest.TestCase):
 def context(self):
  c=Context(threading.Event(),threading.Event());c.wait=lambda s:c.checkpoint();return c
 def service(self,c,marker):
  return S(context=c,check=Mock(),capture=Mock(return_value=np.full((479,897,3),30,np.uint8)),detector=S(find=Mock(return_value=(1,1,(0,0,2,2)) if marker else None)))
 def test_threshold(self):
  self.assertTrue(decision(True,601)['allowed']);self.assertFalse(decision(True,600)['allowed']);self.assertFalse(decision(True,0)['allowed'])
  self.assertFalse(decision(True,None)['allowed']);self.assertTrue(decision(False,None)['allowed'])
 def test_dungeon_is_allowed_when_timer_has_more_than_ten_minutes(self):
  c=self.context();adapter=S();service=self.service(c,True)
  with patch('owner_reward_context.read_remaining',return_value=1800):self.assertTrue(admit(adapter,c,Mock(),service=service)['allowed'])
 def test_remaining_time_unknown_has_accurate_reason(self):
  c=self.context();adapter=S();service=self.service(c,True)
  with patch('owner_reward_context.read_remaining',return_value=None):
   result=admit(adapter,c,Mock(),service=service)
  self.assertFalse(result['allowed']);self.assertIn('남은 시간 판독 필요',result['reason'])
 def test_field_does_not_require_a_dungeon_timer(self):
  c=self.context();service=self.service(c,False)
  with patch('owner_reward_context.read_remaining') as timer:self.assertTrue(admit(S(),c,Mock(),service=service)['allowed'])
  timer.assert_not_called()
 def test_old_context_clock_is_not_reused(self):
  c=self.context();adapter=S(_owner_reward_dungeon_clock={'context':self.context(),'at':100,'seconds':2000});service=self.service(c,True)
  with patch('owner_reward_context.read_remaining',return_value=300) as timer:
   self.assertFalse(admit(adapter,c,Mock(),service=service)['allowed'])
  timer.assert_called_once()
 def test_preparation_has_no_blanket_dungeon_rejection(self):
  from project_adapter import town_services
  c=self.context();service=self.service(c,True);adapter=S(exit_sleep_mode=Mock())
  with patch.object(town_services,'TownServices',return_value=service),patch('owner_start_menu.normalize'),patch('owner_progression.inventory_parts',return_value=(False,False)),patch('owner_reward_context.admit',return_value=decision(True,1800)):
   prepare(adapter,c,Mock())
 def test_twenty_four_hour_timer_uses_existing_reader(self):
  pages=lambda t:[{'rec_texts':[t],'rec_scores':[1.]}]
  self.assertEqual(parse_timer(pages('23:59:59')),86399);self.assertEqual(parse_timer(pages('24:00:00')),86400)
  self.assertIsNone(parse_timer(pages('24:00:01')));self.assertIsNone(parse_timer(pages('25:00:00')))
 def test_priority_allows_rewards_but_not_growth_in_dungeon(self):
  from owner_schedule_priority import LOCAL,hold_reason
  previous=getattr(LOCAL,'combat',None);LOCAL.combat='비경·던전'
  try:
   with patch('owner_schedule_priority.reservation_hold',return_value=None):
    adapter=S(project=S(root=Path('.')),values={})
    self.assertIsNone(hold_reason(adapter,label='우편'));self.assertIn('진행 중',hold_reason(adapter,label='성장 장비·가호'))
  finally:LOCAL.combat=previous


class ScheduleTests(unittest.TestCase):
 def test_install_reuses_existing_adapter_methods_and_restores_wait(self):
  from project_adapter import _entry,market_inventory
  from owner_reward_action_test import PATHS
  class Adapter:
   def run(self,context,inputs):context.wait(0)
  for path in PATHS.values():
   if path is not None and path[0]=='adapter':setattr(Adapter,path[1],lambda *args:True)
  context=Context(threading.Event(),threading.Event());original=Mock();context.wait=original
  with patch.object(_entry,'Adapter',Adapter),patch.object(market_inventory,'run_equipment_disassembly',lambda *a:True),patch.object(cycle,'tick',return_value=False) as tick,patch.object(cycle.time,'monotonic',return_value=10):
   cycle.install(S());Adapter().run(context,S(held=()))
   tick.assert_called_once();self.assertIs(context.wait,original)
   for path in PATHS.values():
    if path is not None and path[0]=='adapter':self.assertIs(getattr(Adapter,path[1])._owner_reward_cycle,True)
 def test_rewards_no_longer_use_timetable_or_appear_in_time_editor(self):
  import owner_timetable as t
  from owner_schedule_settings import rows
  for job in t.JOBS:
   if job.key in JOBS:self.assertFalse(t.enabled(job,{job.setting:True}))
  self.assertFalse(set(row[0] for row in rows({'jobs':{}}))&JOBS)
 def test_rewards_are_removed_from_shared_pc_and_telegram_projection(self):
  import owner_schedule as s
  with patch.object(s,'next_plan',return_value='later'),patch('owner_schedule_priority.reservation_hold',return_value=None):
   result=s.project(S(get=lambda *a:{}),'test',Path('.'),{'values':{}},'stopped')
  self.assertFalse(set(row['id'] for row in result['rows'])&JOBS)
  self.assertIn('weekly_dungeon',{row['id'] for row in result['rows']})


if __name__=='__main__':unittest.main()
