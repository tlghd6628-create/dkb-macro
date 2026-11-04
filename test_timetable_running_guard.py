"""Isolated planner/fake-context checks; never game operations."""
from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import copy,threading,unittest,tempfile
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_timetable as t


class Stopped(BaseException):pass


class RunningReceipt(unittest.TestCase):
 def setUp(self):
  self.at=datetime(2026,11,2,12,tzinfo=t.KST)
  self.job=t.BY_KEY['clan_request']
  self.cfg={'version':1,'seed':'isolated-audit','enabled':True,'jitter_seconds':0,'jobs':{}}
  self.p=t.Planner.__new__(t.Planner);self.p.root=Path('not-opened')
  self.p.values={self.job.setting:True};self.p.identity='isolated';self.p.cfg=copy.deepcopy(self.cfg)
  self.p.state={'clan_request':{'period':t.period(self.job,self.at),'config':t.fingerprint(self.cfg,self.job),
   'at':(self.at-timedelta(minutes=5)).isoformat(),'status':'running','attempts':1,
   'budget_minutes':t.budget(self.job,self.p.values),'started_at':(self.at-timedelta(minutes=1)).isoformat()}}
  self.p.data={'version':1,'characters':{'isolated':self.p.state}};self.p.commit=Mock()
  self.patches=patch.multiple(t,config=lambda root:self.cfg,busy_windows=lambda *a,**k:[],boss_signature=lambda *a:())
  self.patches.start();self.addCleanup(self.patches.stop)
 def test_setting_change_cannot_replace_running_receipt(self):
  before=copy.deepcopy(self.p.state['clan_request']);self.cfg['jobs']['clan_request']={'time':'12:03','jitter_seconds':0}
  self.p.build(self.at)
  self.assertEqual(self.p.state['clan_request'],before)
  self.assertTrue(self.p._rebuild_after_running)
 def test_running_receipt_survives_daily_reset(self):
  before=copy.deepcopy(self.p.state['clan_request']);tomorrow=self.at+timedelta(days=1)
  self.p.build(tomorrow)
  self.assertEqual(self.p.state['clan_request'],before)
 def test_end_of_running_occurrence_uses_latest_rule_without_repeat_same_period(self):
  self.cfg['jobs']['clan_request']={'time':'12:03','jitter_seconds':0}
  self.p.build(self.at);self.p.finish('clan_request',True,self.at+timedelta(minutes=2))
  row=self.p.state['clan_request']
  self.assertEqual(row['status'],'processed');self.assertEqual(row['attempts'],1)
  self.assertEqual(row['config'],t.fingerprint(self.cfg,self.job))
  self.assertEqual(self.p.due(self.at+timedelta(minutes=4)),[])
 def test_end_after_reset_builds_new_occurrence_only_after_finish(self):
  tomorrow=self.at+timedelta(days=1);old=copy.deepcopy(self.p.state['clan_request'])
  self.p.build(tomorrow);self.assertEqual(self.p.state['clan_request'],old)
  self.p.finish('clan_request',True,tomorrow+timedelta(minutes=2))
  row=self.p.state['clan_request']
  self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],0)
  self.assertEqual(row['period'],t.period(self.job,tomorrow))
 def test_cold_restart_marks_old_running_interrupted_instead_of_preserving_forever(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as directory:
   root=Path(directory)
   t.save(root/'settings/owner-timetable-state.json',copy.deepcopy(self.p.data))
   with patch.object(t,'identity',return_value='isolated'):
    restarted=t.Planner(root,self.p.values,self.at)
   row=restarted.state['clan_request']
   self.assertEqual(row['status'],'pending');self.assertTrue(row['interrupted'])
   self.assertEqual(row['attempts'],0)
   self.assertEqual(row['startup_previous']['attempts'],1)
   self.assertFalse(getattr(restarted,'_rebuild_after_running',False))


class DispatchOwnership(unittest.TestCase):
 def setUp(self):
  old_job=getattr(t.LOCAL,'job',None);old_native=getattr(t.LOCAL,'native_job',None)
  self.addCleanup(setattr,t.LOCAL,'job',old_job);self.addCleanup(setattr,t.LOCAL,'native_job',old_native)
  t.LOCAL.job=None;t.LOCAL.native_job=None
 def test_idle_does_not_enter_another_job_while_job_owned(self):
  t.LOCAL.job='clan_request'
  with patch.object(t,'planner',side_effect=AssertionError('nested planner')):
   self.assertFalse(t.idle_once(None,None,None))
 def test_idle_does_not_enter_another_job_while_native_owned(self):
  t.LOCAL.native_job='daily24_dungeon'
  with patch.object(t,'planner',side_effect=AssertionError('nested planner')):
   self.assertFalse(t.idle_once(None,None,None))
 def plan(self):
  def begin(key):self.plan_state[key]['attempts']+=1;self.plan_state[key]['status']='running'
  self.plan_state={'clan_request':{'status':'pending','attempts':0}}
  return S(state=self.plan_state,values={'auto_schedule.clan_boss_request.enabled':True},reason=lambda key:None,
   begin=begin,finish=Mock(),commit=Mock())
 def adapter(self):return S(mode='auto_mode',project=S(root=Path('not-opened')))
 def test_zero_argument_timed_closure_preserves_user_stop(self):
  plan=self.plan();context=S(stop=threading.Event());context.stop.set()
  def operation():raise Stopped()
  with patch.object(t,'planner',return_value=plan),patch.object(t,'config',return_value={'jobs':{}}):
   with self.assertRaises(Stopped):
    t.scheduled_call(operation,'문파 보스 신청',(),{},self.adapter(),timed_dispatch=True,run_context=context)
  self.assertEqual(plan.state['clan_request'],{'status':'pending','attempts':0})
  plan.finish.assert_not_called();plan.commit.assert_called_once()
 def test_existing_positional_context_preserves_user_stop(self):
  plan=self.plan();context=S(stop=threading.Event());context.stop.set()
  def operation(ctx):raise Stopped()
  with patch.object(t,'planner',return_value=plan),patch.object(t,'config',return_value={'jobs':{}}):
   with self.assertRaises(Stopped):t.scheduled_call(operation,'문파 보스 신청',(context,),{},self.adapter())
  self.assertEqual(plan.state['clan_request']['attempts'],0);plan.finish.assert_not_called()
 def test_real_exception_still_fails_and_propagates(self):
  plan=self.plan();context=S(stop=threading.Event())
  def operation():raise RuntimeError('genuine failure')
  with patch.object(t,'planner',return_value=plan),patch.object(t,'config',return_value={'jobs':{}}):
   with self.assertRaisesRegex(RuntimeError,'genuine failure'):
    t.scheduled_call(operation,'문파 보스 신청',(),{},self.adapter(),timed_dispatch=True,run_context=context)
  plan.finish.assert_called_once_with('clan_request',False)
 def test_resume_signal_preserves_pending_occurrence_without_failure(self):
  from owner_work_resume import ResumeWork
  plan=self.plan();context=S(stop=threading.Event());signal=ResumeWork('sub_quest')
  def operation():raise signal
  with patch.object(t,'planner',return_value=plan),patch.object(t,'config',return_value={'jobs':{}}):
   with self.assertLogs(t.LOG,level='INFO') as records:
    with self.assertRaises(ResumeWork) as raised:
     t.scheduled_call(operation,'문파 보스 신청',(),{},self.adapter(),timed_dispatch=True,run_context=context)
  self.assertIs(raised.exception,signal)
  self.assertEqual(plan.state['clan_request'],{'status':'pending','attempts':0})
  plan.finish.assert_not_called();plan.commit.assert_called_once()
  self.assertTrue(any('기존 작업 복귀' in row for row in records.output))
  self.assertFalse(any('시간표 실행 오류' in row for row in records.output))
  self.assertIsNone(t.LOCAL.job)
 def test_idle_passes_actual_context_into_timed_closure(self):
  plan=S(values={'auto_schedule.clan_boss_request.enabled':True},state={'clan_request':{'at':'isolated'}},due=lambda:[t.BY_KEY['clan_request']],reason=lambda key:None)
  context=S(checkpoint=lambda:None);adapter=self.adapter();adapter.values={};adapter.exit_sleep_mode=Mock()
  adapter.run_favorite_hunt=Mock(return_value=True)
  with (patch.object(t,'planner',return_value=plan),patch.object(t,'scheduled_call',return_value=True) as call,
       patch('owner_schedule_priority.hold_reason',return_value=None)):
   self.assertTrue(t.idle_once(adapter,context,object()))
  self.assertIs(call.call_args.kwargs['run_context'],context)


if __name__=='__main__':unittest.main()
