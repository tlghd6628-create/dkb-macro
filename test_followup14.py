"""Saved frames and isolated/fake callers only; not live game acceptance."""
import bootstrap
import copy,tempfile,unittest,threading
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_timetable as t
import owner_program_runtime as runtime
import owner_task_flow as task
from owner_chore_transition import ChoreYield,dialogue_pair

class Gates(unittest.TestCase):
 def wrap(self):
  native=S(run_growth_entry=lambda *a,**kw:True)
  runtime.install_identity_preflight(native,'run_growth_entry',())
  return native.run_growth_entry
 def test_all_off_has_no_identity_capture_or_input(self):
  run=self.wrap()
  with patch.object(runtime,'fresh_growth_identity',side_effect=AssertionError('unexpected check')):
   self.assertTrue(run(S(values={}),None,None))
 def test_other_growth_does_not_open_equipment_tooltip(self):
  run=self.wrap()
  with patch.object(runtime,'fresh_growth_identity',return_value=True),patch('owner_worn_stats.inspect_equipped',side_effect=AssertionError('equipment disabled')):
   self.assertTrue(run(S(values={'auto_growth.taoist.enabled':True}),None,None))
 def test_equipment_display_yield_cannot_starve_guarded_growth(self):
  calls=[];native=S(run_growth_entry=lambda *a,**kw:calls.append('guarded-growth') or True)
  runtime.install_identity_preflight(native,'run_growth_entry',())
  def display(*a,**kw):calls.append('display');raise ChoreYield('팔찌')
  with patch.object(runtime,'fresh_growth_identity',return_value=True),patch('owner_worn_stats.inspect_equipped',side_effect=display):
   self.assertTrue(native.run_growth_entry(S(values={'auto_growth.equipment.enabled':True}),None,None))
  self.assertEqual(calls,['guarded-growth','display'])
 def test_pending_resource_result_never_opens_optional_display(self):
  run=self.wrap();adapter=S(values={'auto_growth.equipment.enabled':True},_owner_growth_pending_hold=True)
  with patch.object(runtime,'fresh_growth_identity',return_value=True),patch('owner_worn_stats.inspect_equipped') as display:
   self.assertTrue(run(adapter,None,None));display.assert_not_called()
 def test_stale_pending_disabled_job_is_discarded(self):
  context=S(stop=threading.Event(),checkpoint=lambda:None)
  adapter=S(values={'auto_rewards.inventory_use.enabled':False},mode='auto_mode',
   _owner_pending_services={'context':context,'keys':{'auto_rewards.inventory_use.enabled'},'inputs':None})
  with patch('owner_schedule_priority.hold_reason',return_value=None):
   self.assertTrue(task.dispatch(adapter,context,Mock(side_effect=AssertionError('disabled job called'))))
  self.assertIsNone(adapter._owner_pending_services)

class Startup(unittest.TestCase):
 def setUp(self):
  self.at=datetime(2026,11,3,18,tzinfo=t.KST)
  self.p=t.Planner.__new__(t.Planner);self.p.root=Path('never-opened');self.p.cfg={'enabled':True,'jobs':{}}
  self.p.values={j.setting:True for j in t.JOBS};self.p.state={};self.p.commit=Mock()
  self.patch=patch.object(t,'busy_windows',return_value=[]);self.patch.start();self.addCleanup(self.patch.stop)
 def row(self,key,status='processed',**extra):
  row={'status':status,'period':t.period(t.BY_KEY[key],self.at),'at':(self.at-timedelta(hours=8)).isoformat(),'attempts':2}
  row.update(extra);self.p.state[key]=row;return row
 def test_daily_dungeon_missed_today_is_due_now(self):
  row=self.row('daily_dungeon','failed');self.p.startup_recheck(self.at)
  self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],0)
  self.assertLess(t.parse_at(row['at']),self.at+timedelta(minutes=1))
 def test_verified_done_not_reopened(self):
  row=self.row('daily_dungeon',last_outcome='done',result_unverified=False)
  self.p.startup_recheck(self.at);self.assertEqual(row['status'],'processed')
 def test_attempt_without_verification_is_rechecked(self):
  row=self.row('daily_dungeon');self.p.startup_recheck(self.at);self.assertEqual(row['status'],'pending')
 def test_disabled_never_reenabled(self):
  row=self.row('daily_dungeon','failed');self.p.values[t.BY_KEY['daily_dungeon'].setting]=False
  self.p.startup_recheck(self.at);self.assertEqual(row['status'],'failed')
 def test_future_appointment_is_preserved(self):
  self.p.cfg['jobs']['daily_dungeon']={'time':'19:00'}
  row=self.row('daily_dungeon','pending',at=(self.at+timedelta(hours=1)).isoformat());before=copy.deepcopy(row)
  self.p.startup_recheck(self.at);self.assertEqual(row,before)
 def test_result_only_intent_is_not_converted_to_new_input(self):
  row=self.row('gear','failed',last_outcome='sent_unconfirmed')
  self.p.startup_recheck(self.at);self.assertEqual(row['retry_mode'],'reconcile')
 def test_once_and_other_character_period_preserved(self):
  row=self.row('treasure','held');self.p.startup_recheck(self.at);self.assertEqual(row['status'],'held')
 def test_selected_weekday_respected(self):
  row=self.row('weekly_dungeon','failed');self.p.cfg['jobs']['weekly_dungeon']={'weekdays':[0]}
  self.p.startup_recheck(self.at);self.assertEqual(row['status'],'failed')

class Dialogue(unittest.TestCase):
 def test_actual_failure_frame_is_known_dialogue(self):
  from PIL import Image
  import numpy as np
  root=bootstrap.A
  frame=np.asarray(Image.open(root/'logs/quest-incidents/20261102T145840Z-8605c5b8/screen.png').convert('RGB'))
  adapter=S(mode='sub_quest',project=S(root=root,code='DKB'))
  service=S(adapter=adapter,check=lambda:None,capture=lambda:frame)
  self.assertTrue(dialogue_pair(service,S(checkpoint=lambda:None,wait=lambda _:None),None))
  service.capture=lambda:np.zeros_like(frame)
  self.assertFalse(dialogue_pair(service,S(checkpoint=lambda:None,wait=lambda _:None),None))

if __name__=='__main__':unittest.main()
