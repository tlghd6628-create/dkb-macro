"""Remaining-time recheck on an isolated schedule, and the timer second look with a fake reader. Never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import logging,tempfile,threading,unittest
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from biol_base.session import Context,Cancelled
import tools.time_ocr as time_ocr
import owner_timetable as t
import owner_dungeon_time as d

KST=t.KST;KEY='auto_challenge.secret_folktale_5h.enabled'
TUESDAY=datetime(2026,11,3,9,0,10,tzinfo=KST)
LOG=logging.getLogger('project_gui.DKB')

class Base(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  # The program logs at INFO; without this the native lines never reach the handler.
  self.addCleanup(LOG.setLevel,LOG.level);LOG.setLevel(logging.INFO)
  self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text('{"server_name":"s","character_name":"c"}',encoding='utf-8')
  self.only(KEY)
 def only(self,setting):
  # One job on, so no other due job holds it back as "앞 일정".
  self.values={setting:True}
  self.plan=t.Planner(self.root,self.values,TUESDAY-timedelta(hours=1))
  self.adapter=S(project=S(root=self.root),values=self.values,mode='sub_quest',_owner_timetable=self.plan,_owner_preparing_gears=False)
 def run_job(self,key,at,native):
  row=self.plan.state[key];row.update(status='pending',at=(at-timedelta(minutes=1)).isoformat(),attempts=0)
  def body():
   native();return True
  with patch.object(t,'now',return_value=at),patch.object(t,'character_mismatch',return_value=False):
   t.scheduled_call(body,t.BY_KEY[key].label,(),{},self.adapter,timed_dispatch=True,run_context=S(stop=threading.Event()),run_inputs=Mock())
  return self.plan.state[key]

class StartLate(Base):
 """Started after a checked job's time: it runs first. Fake input, never a game test."""
 def start(self,at,invoke=None,**hold):
  self.adapter.exit_sleep_mode=lambda *a:None;self.adapter._owner_timetable=self.plan
  context=S(stop=threading.Event(),checkpoint=lambda:None);self.invoke=invoke or Mock(return_value=True)
  with patch.object(t,'now',return_value=at),patch.object(t,'character_mismatch',return_value=False),\
       patch('owner_schedule_priority.hold_reason',return_value=hold.get('hold')),patch.object(t,'invoke',self.invoke):
   return t.catch_up_overdue(self.adapter,context,Mock())
 def daily(self,at):
  self.values={'auto_challenge.secret_exploration.enabled':True}
  self.plan=t.Planner(self.root,self.values,at)
  self.adapter=S(project=S(root=self.root),values=self.values,mode='sub_quest',_owner_timetable=self.plan,_owner_preparing_gears=False)
 def test_a_start_after_the_time_runs_it_first(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at)
  self.assertEqual(self.start(at),['daily_dungeon']);self.invoke.assert_called_once()
  self.assertEqual(self.invoke.call_args[0][1].key,'daily_dungeon')
 def test_a_start_before_the_time_waits_for_it(self):
  at=datetime(2026,11,4,6,0,tzinfo=KST);self.daily(at)
  self.assertEqual(self.start(at),[]);self.invoke.assert_not_called()
 def test_finished_today_is_not_run_again(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at);self.plan.state['daily_dungeon']['status']='processed'
  self.assertEqual(self.start(at),[]);self.invoke.assert_not_called()
 def test_unchecked_job_never_runs(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at);self.plan.values['auto_challenge.secret_exploration.enabled']=False
  self.assertEqual(self.start(at),[]);self.invoke.assert_not_called()
 def test_a_boss_window_holds_the_catch_up(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at)
  self.assertEqual(self.start(at,hold='보스 예약'),[]);self.invoke.assert_not_called()
 def test_a_failure_does_not_stop_the_start_and_stays_due_for_retry(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at)
  self.assertEqual(self.start(at,Mock(side_effect=RuntimeError('화면 미확인'))),['daily_dungeon'])
  row=self.plan.state['daily_dungeon'];self.assertEqual(row['status'],'pending');self.assertEqual(t.parse_at(row['at']),at+timedelta(minutes=2))
 def test_user_stop_still_ends_it(self):
  at=datetime(2026,11,4,16,29,tzinfo=KST);self.daily(at)
  self.adapter.exit_sleep_mode=lambda *a:None
  def checkpoint():raise Cancelled()
  context=S(stop=threading.Event(),checkpoint=checkpoint)
  with patch.object(t,'now',return_value=at),patch.object(t,'character_mismatch',return_value=False),patch('owner_schedule_priority.hold_reason',return_value=None),patch.object(t,'invoke') as invoke:
   with self.assertRaises(Cancelled):t.catch_up_overdue(self.adapter,context,Mock())
  invoke.assert_not_called()

class Recheck(Base):
 def test_time_left_unknown_requires_immediate_recheck(self):
  row=self.run_job('weekly_dungeon',TUESDAY,lambda:LOG.info('비경탐험 완료 · 시간 만료·퇴장 확인'))
  self.assertEqual(row['status'],'pending');self.assertTrue(row['dungeon_recheck']);self.assertEqual(row['attempts'],0)
  self.assertEqual(t.parse_at(row['at']),TUESDAY)
 def test_it_becomes_due_without_a_three_hour_detour(self):
  self.run_job('weekly_dungeon',TUESDAY,lambda:None)
  self.assertIn('weekly_dungeon',[j.key for j in self.plan.due(TUESDAY+timedelta(seconds=1))])
 def test_the_native_zero_read_finishes_the_week(self):
  for text in ('자동 기능 건너뜀 · 비경탐험 · 비경 이용 시간 0초 · 입장 생략','전래동화-5시간 · 원님 고개 · 남은 기본시간 00:00:00'):
   row=self.run_job('weekly_dungeon',TUESDAY,lambda:LOG.info(text))
   self.assertEqual(row['status'],'processed');self.assertNotIn('dungeon_recheck',row);self.assertNotIn('result_unverified',row)
   self.assertIn('no_time_left_at',row)
 def test_time_still_left_keeps_rechecking(self):
  row=self.run_job('weekly_dungeon',TUESDAY,lambda:LOG.info('전래동화-5시간 · 원님 고개 · 남은 기본시간 04:03:37'))
  self.assertTrue(row['dungeon_recheck'])
  later=TUESDAY+timedelta(minutes=181)
  row=self.run_job('weekly_dungeon',later,lambda:LOG.info('비경탐험 미완료 · 전래동화-5시간 기본시간 OCR 실패'))
  self.assertEqual(t.parse_at(row['at']),later)
 def test_unknown_quota_never_completes_on_a_different_weekday(self):
  late=datetime(2026,11,4,3,0,tzinfo=KST)
  row=self.run_job('weekly_dungeon',late,lambda:None)
  self.assertEqual(row['status'],'pending');self.assertTrue(row['result_unverified']);self.assertTrue(row['dungeon_recheck'])
 def test_failure_keeps_trying_with_no_cap_and_no_long_cooldown(self):
  self.only('auto_challenge.secret_exploration.enabled')
  at=datetime(2026,11,3,7,10,tzinfo=KST);seen=[]
  def fail():LOG.info('자동 기능 부분 완료 · 비경탐험 · 시간 미확인')
  for _ in range(7):
   row=self.run_job('daily_dungeon',at,fail)
   self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],0);self.assertTrue(row['dungeon_recheck'])
   next_at=t.parse_at(row['at']);seen.append(int((next_at-at).total_seconds()//60))
   self.assertIn('daily_dungeon',[j.key for j in self.plan.due(next_at)]);at=next_at
  self.assertEqual(seen,[2,4,8,10,10,10,10])
 def test_a_later_success_clears_the_failure_count(self):
  self.only('auto_challenge.secret_exploration.enabled')
  at=datetime(2026,11,3,7,10,tzinfo=KST)
  self.run_job('daily_dungeon',at,lambda:LOG.info('자동 기능 부분 완료 · 비경탐험 · 시간 미확인'))
  row=self.run_job('daily_dungeon',at+timedelta(minutes=2),lambda:LOG.info('비경 잔여시간 소진 확인 · daily · 원본 입장 시간 0초'))
  self.assertEqual(row['status'],'processed');self.assertNotIn('dungeon_failures',row)
 def test_daily24_failure_retries_but_its_chosen_hours_still_end_it(self):
  self.only('auto_challenge.secret_exploration_always.enabled')
  at=datetime(2026,11,3,10,30,tzinfo=KST);label=t.BY_KEY['daily24_dungeon'].label
  row=self.run_job('daily24_dungeon',at,lambda:LOG.info('자동 기능 부분 완료 · '+label+' · 시간 미확인'))
  self.assertEqual(row['status'],'pending');self.assertNotIn('dungeon_recheck',row);self.assertEqual(t.parse_at(row['at']),at+timedelta(minutes=2))
  row=self.run_job('daily24_dungeon',at+timedelta(minutes=2),lambda:None)
  self.assertEqual(row['status'],'processed');self.assertNotIn('dungeon_recheck',row)
 def test_other_jobs_keep_their_retry_cap(self):
  self.only('auto_challenge.ascension_tower.enabled')
  at=datetime(2026,11,3,15,0,tzinfo=KST);row=self.plan.state['tower'];row.update(status='running',attempts=1)
  self.plan.finish('tower',False,at)
  self.assertEqual(self.plan.state['tower']['status'],'failed');self.assertEqual(t.parse_at(self.plan.state['tower']['at']),at+timedelta(minutes=10))
 def test_daily_dungeon_rechecks_too(self):
  self.only('auto_challenge.secret_exploration.enabled')
  at=datetime(2026,11,3,7,10,tzinfo=KST)
  row=self.run_job('daily_dungeon',at,lambda:None)
  self.assertTrue(row['dungeon_recheck']);self.assertEqual(t.parse_at(row['at']),at)
 def test_restart_keeps_the_entry_check_immediate_instead_of_three_hours(self):
  self.run_job('weekly_dungeon',TUESDAY,lambda:None)
  before=self.plan.state['weekly_dungeon']['at']
  again=t.Planner(self.root,self.values,TUESDAY+timedelta(minutes=30))
  self.assertLessEqual(t.parse_at(again.state['weekly_dungeon']['at']),TUESDAY+timedelta(minutes=31))
  self.assertEqual(again.state['weekly_dungeon']['entry_recheck_policy'],'immediate-v1')
 def test_legacy_three_hour_hold_moves_to_immediate_check_once(self):
  row=self.run_job('weekly_dungeon',TUESDAY,lambda:None)
  row.pop('entry_recheck_policy',None);row['at']=(TUESDAY+timedelta(hours=3)).isoformat();self.plan.commit()
  again=t.Planner(self.root,self.values,TUESDAY+timedelta(minutes=1))
  self.assertEqual(t.parse_at(again.state['weekly_dungeon']['at']),TUESDAY+timedelta(minutes=1))
  self.assertEqual(again.state['weekly_dungeon']['entry_recheck_policy'],'immediate-v1')
 def test_daily24_is_left_alone(self):
  self.assertNotIn('daily24_dungeon',t.RECHECK_JOBS)
 def test_a_stop_during_the_run_is_not_a_recheck(self):
  row=self.plan.state['weekly_dungeon'];row.update(status='pending',at=(TUESDAY-timedelta(minutes=1)).isoformat(),attempts=0)
  stop=threading.Event();stop.set()
  def body():raise Cancelled()
  with patch.object(t,'now',return_value=TUESDAY),patch.object(t,'character_mismatch',return_value=False),self.assertRaises(Cancelled):
   t.scheduled_call(body,t.BY_KEY['weekly_dungeon'].label,(),{},self.adapter,timed_dispatch=True,run_context=S(stop=stop),run_inputs=Mock())
  self.assertNotIn('dungeon_recheck',self.plan.state['weekly_dungeon'])

class Reader:
 """Fake engine: the page text is decided by how many reads came before."""
 def __init__(self,texts):self.texts=list(texts)
 def page(self,*a):
  text=self.texts.pop(0);return [{'rec_texts':[text],'rec_scores':[.99]}] if text else []

class SecondLook(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.context=Context(threading.Event(),threading.Event())
  self.rgb=np.zeros((24,65,3),dtype='uint8')
  patcher=patch('tools.ocr_support.get_paddle_engine',return_value=object());patcher.start();self.addCleanup(patcher.stop)
 def read(self,first,fields):
  reader=Reader(fields)
  with patch.object(time_ocr,'_predict',side_effect=reader.page):
   return d.wrap(Mock(return_value=first),time_ocr)(self.rgb,self.root,self.context)
 RANGE=time_ocr.TimeRead(error='시간 유효 범위 이탈')
 def test_an_impossible_minute_is_read_again(self):
  result=self.read(self.RANGE,['03:59:45'])
  self.assertTrue(result.ok);self.assertEqual(result.text,'03:59:45');self.assertEqual(result.seconds,3*3600+59*60+45)
 def test_impossible_and_partial_reads_try_the_next_image(self):
  self.assertEqual(self.read(self.RANGE,['03:69:45','','0359','03:59:45']).text,'03:59:45')
 def test_low_confidence_is_not_accepted(self):
  reader=S(page=lambda *a:[{'rec_texts':['03:59:45'],'rec_scores':[.84]}])
  with patch.object(time_ocr,'_predict',side_effect=reader.page):
   result=d.wrap(Mock(return_value=self.RANGE),time_ocr)(self.rgb,self.root,self.context)
  self.assertFalse(result.ok)
 def test_never_guesses_when_every_image_stays_impossible(self):
  result=self.read(self.RANGE,['03:69:45']*6)
  self.assertFalse(result.ok);self.assertEqual(result.error,'시간 유효 범위 이탈')
 def test_a_good_read_and_other_errors_are_untouched(self):
  good=time_ocr.TimeRead(True,'04:03:37',14617)
  self.assertIs(self.read(good,[]),good)
  other=time_ocr.TimeRead(error='시·분·초 중 판독 실패')
  self.assertIs(self.read(other,[]),other)
 def test_the_crop_is_kept_as_evidence_and_bounded(self):
  for _ in range(23):self.read(self.RANGE,['03:59:45'])
  self.assertLessEqual(len(list((self.root/'logs/dungeon-time').glob('*.png'))),20)
 def test_stop_is_not_swallowed(self):
  self.context=S(checkpoint=Mock(side_effect=Cancelled()))
  with self.assertRaises(Cancelled):self.read(self.RANGE,['03:59:45'])
 def test_the_native_retry_loop_reaches_the_wrapped_reader(self):
  original=time_ocr.read_time_image;self.addCleanup(setattr,time_ocr,'read_time_image',original)
  time_ocr.read_time_image=Mock(return_value=time_ocr.TimeRead(True,'03:59:20',14360))
  result=time_ocr.read_time_region('n',lambda name:self.rgb,self.root,self.context,Mock())
  self.assertEqual(result.text,'03:59:20')
 def test_install_wraps_once(self):
  original=time_ocr.read_time_image;self.addCleanup(setattr,time_ocr,'read_time_image',original)
  d.install();first=time_ocr.read_time_image;d.install()
  self.assertIs(time_ocr.read_time_image,first)

if __name__=='__main__':unittest.main()
