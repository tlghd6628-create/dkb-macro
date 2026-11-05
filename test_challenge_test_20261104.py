"""TEST rows: real native dispatcher and raid flow with fakes underneath. Never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import inspect,logging,re,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import MagicMock,Mock,patch
import numpy as np
import tkinter as tk
from biol_base.session import Session,Context,Cancelled
import owner_challenge_test as c
from owner_challenge_test import TARGETS,execute,prepare,start
from owner_reward_action_test import Controller,TARGETS as REWARDS
from owner_settings_console import SettingsConsole,category
from test_settings_theme_20261103 import Base,walk
import project_adapter.boss_raid as raid
from project_adapter._entry import Adapter as Native

ROOT=bootstrap.T/'test_scratch/no-test-reservations'
RAID='auto_schedule.boss_raid.enabled'
LOG=logging.getLogger('project_gui.DKB')

def context(ran=None):
 x=Context(threading.Event(),threading.Event())
 x.run_action=lambda key,operation:((ran.append(key) if ran is not None else None),operation())[1]
 return x

def real(values,mode='sub_quest',order=None):
 order=order if order is not None else []
 class Real:
  _run_auto_features=Native._run_auto_features
  project=S(app_id='DKB',code='DKB',root=ROOT)
  def get_due_schedules(self):return ['ordinary_due']
  def __getattr__(self,name):
   if name.startswith('run_'):
    def f(*a,**k):order.append(name);return True
    return f
   raise AttributeError(name)
 adapter=Real();adapter.values=values;adapter.mode=mode
 return adapter

class Dispatch(unittest.TestCase):
 MODULES=[('mission_quests','run_mission_quests'),('folktale','run_folktale'),('secret_exploration','run_secret_exploration'),('secret_folktale','run_folktale_exploration')]
 def run_key(self,key,mode='sub_quest'):
  import importlib
  order=[];ran=[];saved={key:False,'auto_rewards.mail.enabled':True,'auto_schedule.field_boss.enabled':True,'auto_schedule.field_boss.skill_preset.enabled':True}
  adapter=real(saved,mode,order);seen=[]
  patches=[]
  for mod,name in self.MODULES:
   def rec(*a,_n=mod+'.'+name,**k):order.append((_n,k));return True
   patches.append(patch.object(importlib.import_module('project_adapter.'+mod),name,rec))
  for p in patches:p.start()
  try:execute(adapter,context(ran),Mock(),key)
  finally:
   for p in patches:p.stop()
  self.assertIs(adapter.values,saved);self.assertIs(saved[key],False);self.assertEqual(adapter.mode,mode)
  self.assertEqual(adapter.get_due_schedules(),['ordinary_due'])
  return order,ran
 def test_each_dispatched_row_reaches_its_own_native_entry_from_a_quest_mode(self):
  want={'auto_schedule.daily_quest.enabled':'mission_quests.run_mission_quests','auto_schedule.weekly_quest.enabled':'mission_quests.run_mission_quests',
   'auto_challenge.ascension_tower.enabled':'run_ascension_tower','auto_schedule.falling_battle.enabled':'run_falling_battle','auto_schedule.folktale.enabled':'folktale.run_folktale',
   'auto_challenge.secret_exploration.enabled':'secret_exploration.run_secret_exploration','auto_challenge.secret_exploration_always.enabled':'secret_exploration.run_secret_exploration',
   'auto_challenge.secret_folktale_5h.enabled':'secret_folktale.run_folktale_exploration','auto_challenge.secret_folktale.enabled':'secret_folktale.run_folktale_exploration','auto_growth.spirit_training.enabled':'run_spirit_training'}
  self.assertEqual(set(want),{k for k,v in TARGETS.items() if v[1]==c.DISPATCH})
  for key,entry in want.items():
   with self.subTest(key=key):
    order,ran=self.run_key(key)
    names=[o[0] if isinstance(o,tuple) else o for o in order]
    self.assertIn(entry,names);self.assertNotIn('run_mail_rewards',names)
    self.assertNotIn('run_town_return',names)
    self.assertNotIn('common.run_town_return',ran)
 def test_kinds_are_passed_to_folktale_and_daily24(self):
  order,_=self.run_key('auto_challenge.secret_folktale_5h.enabled');self.assertIn(('secret_folktale.run_folktale_exploration',{'kind':'5h'}),order)
  order,_=self.run_key('auto_challenge.secret_folktale.enabled');self.assertIn(('secret_folktale.run_folktale_exploration',{'kind':'24h'}),order)
  order,_=self.run_key('auto_challenge.secret_exploration_always.enabled');self.assertIn(('secret_exploration.run_secret_exploration',{'variant':'daily24h'}),order)
 def test_only_this_switch_and_the_presets_stay_on(self):
  shown=c.only({'a.enabled':True,'x.y':3,'auto_schedule.boss_raid.skill_preset.enabled':True,RAID:False},RAID)
  self.assertEqual(shown,{'a.enabled':False,'x.y':3,'auto_schedule.boss_raid.skill_preset.enabled':True,RAID:True})
 def test_values_come_back_after_failure(self):
  saved={RAID:False,'auto_schedule.boss_raid.stage':'nope'};adapter=real(saved)
  with self.assertRaisesRegex(RuntimeError,'단계 설정'):execute(adapter,context(),Mock(),RAID)
  self.assertIs(adapter.values,saved)
 def test_clock_events_use_their_own_entries(self):
  adapter=real({'auto_schedule.field_boss.enabled':False},order=(order:=[]))
  execute(adapter,context(),Mock(),'auto_schedule.field_boss.enabled');self.assertEqual(order,['run_field_boss_entry'])
  import project_adapter.clan_boss_request as clan
  with patch.object(clan,'run_clan_boss_request') as run:
   execute(real({}),context(),Mock(),'auto_schedule.artifact_charm.enabled')
  self.assertEqual(run.call_args.kwargs,{'combat':True})
 def test_a_boss_return_signal_just_ends_the_test(self):
  from owner_work_resume import ResumeWork
  adapter=real({});adapter.run_field_boss_entry=Mock(side_effect=ResumeWork('sub_quest'))
  self.assertIsNone(execute(adapter,context(),Mock(),'auto_schedule.field_boss.enabled'))
 def test_entry_inside_content_is_refused(self):
  from project_adapter import town_services
  # One spoiled frame during combat is read again; lasting doubt still refuses.
  for kinds,ok in ((('field','field'),True),(('dungeon','dungeon'),False),(('unknown','field','field'),True),(('field','unknown')*6,False),(('unknown',)*12,False)):
   service=Mock();adapter=S(exit_sleep_mode=Mock())
   with patch.object(town_services,'TownServices',return_value=service),patch('owner_start_menu.normalize'),patch('owner_startup_stage.scene',side_effect=kinds):
    if ok:prepare(adapter,context(),Mock())
    else:
     with self.assertRaisesRegex(RuntimeError,'필드에서'):prepare(adapter,context(),Mock())

class RaidPreview(unittest.TestCase):
 """The real RaidFlow.entry walks the menu; only screen reads and clicks are faked."""
 GONE={raid.NO_TICKET,raid.NEXT,raid.DEATH,raid.ENTERED,raid.MATCHING,raid.ADMIT,raid.COMPLETE,raid.REJECT,*raid.SLEEP,'체크_절전모드중',raid.SKIP}
 def flow(self,gone=()):
  gone=self.GONE|set(gone);pressed=[]
  class Screen(raid.RaidFlow):
   def check(self):pass
   def wake(self,frame):return False
   def find(self,name,frame):return None if name in gone or re.match('체크_레이드_[2-5]단계',name) else (9,9)
   def detect(self,name,seconds=3,*,alternatives=(),with_name=False):
    hit=None if name in gone else (9,9)
    return (hit,name) if with_name else hit
   def click(self,name,hit):pressed.append(name)
  # The guard sits above the fake screen, as it sits above the real flow.
  with patch.object(raid,'RaidFlow',Screen):Preview=c.preview_flow(raid)
  x=MagicMock();x.project=S(root=bootstrap.A,code='DKB',app_id='DKB');x.values={}
  flow=Preview(x,context(),Mock());flow.capture=lambda:np.zeros((479,897,3),dtype='uint8')
  return flow,pressed
 def test_match_is_reached_but_never_pressed(self):
  flow,pressed=self.flow()
  with self.assertRaises(c.AtMatchButton):flow.entry(1)
  self.assertIn('버튼_보스',pressed);self.assertIn('버튼_보스_레이드탭',pressed)
  for name in (raid.MATCH,raid.CONFIRM,raid.CONFIRM2,raid.BULK,raid.BULK2):self.assertNotIn(name,pressed)
 def test_every_commit_button_is_blocked(self):
  for name in (raid.MATCH,raid.CONFIRM,raid.CONFIRM2,raid.BULK,raid.BULK2):
   with self.subTest(name=name):
    flow,pressed=self.flow()
    with self.assertRaises(c.AtMatchButton):flow.press(name)
    with self.assertRaises(c.AtMatchButton):flow.click(name,(9,9))
    self.assertEqual(pressed,[])
 def test_preview_leaves_and_reports(self):
  flow,pressed=self.flow();flow.leave=Mock(return_value=True)
  a=S(values={'auto_schedule.boss_raid.stage':'1단계'})
  with patch.object(c,'preview_flow',return_value=lambda *x:flow):
   self.assertEqual(c.raid_preview(a,context(),Mock()),'입장 직전 확인 · 매칭 안 누름')
  flow.leave.assert_called_once();self.assertNotIn(raid.MATCH,pressed)
 def test_no_ticket_closes_the_menu_and_says_so(self):
  flow,pressed=self.flow();flow.leave=Mock(return_value=True);flow.entry=Mock(side_effect=raid.RaidPending('레이드 티켓 없음'))
  a=S(values={'auto_schedule.boss_raid.stage':'3단계'})
  with patch.object(c,'preview_flow',return_value=lambda *x:flow),self.assertRaisesRegex(RuntimeError,'티켓 없음'):c.raid_preview(a,context(),Mock())
  flow.entry.assert_called_once_with(3);flow.leave.assert_called_once();self.assertEqual(pressed,[])

class Text(unittest.TestCase):
 def test_result_says_what_really_happened(self):
  self.assertEqual(c.outcome_text('입장 직전 확인 · 매칭 안 누름',None),'입장 직전 확인 · 매칭 안 누름')
  self.assertEqual(c.outcome_text(True,None),'처리 종료 · 실행 로그 확인')
  self.assertEqual(c.outcome_text(None,'비경탐험 미완료'),'종료 · 비경탐험 미완료')
  self.assertEqual(c.outcome_text(False,None),'실패 · 실행 로그 확인')
 def test_reason_listener_keeps_the_last_native_line_on_this_thread(self):
  r=c.Reasons();old=LOG.level;LOG.setLevel(logging.INFO);LOG.addHandler(r)
  try:
   LOG.info('자동 기능 시작 · 비경');self.assertIsNone(r.last)
   LOG.info('자동 기능 건너뜀 · 비경 미완료');self.assertIn('건너뜀',r.last)
   LOG.info('실전 TEST 준비 실패');self.assertIn('건너뜀',r.last)
   other=threading.Thread(target=lambda:LOG.info('다른 작업 보류'));other.start();other.join()
   self.assertIn('건너뜀',r.last)
  finally:LOG.removeHandler(r);LOG.setLevel(old)

class Worker(unittest.TestCase):
 def setUp(self):
  # Tk variables left by earlier UI tests must not be collected on the worker:
  # with no main loop here, each one blocks that thread for about a second.
  import gc;gc.collect()
 def wrapped(self,adapter):
  from operating_policy import PolicyAdapter
  return PolicyAdapter(adapter,{'execution':{'failure_limit':1,'pause_on_error':False,'action_gap_ms':0},'notifications':{'result_summary':False}},logging.getLogger('fake'),None)
 def gui(self,session,**kw):return S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),game_window=S(require_ready=Mock()),**kw)
 def fake(self):
  class F:
   input_backend='fake-only';mode='sub_quest';closed=False;values={RAID:False}
   def close(self):self.closed=True
  return F()
 def test_ordinary_session_owns_it_and_keeps_its_factory(self):
  adapter=self.fake();inputs=Mock();factory=Mock(return_value=self.wrapped(adapter))
  session=Session(lambda:None,factory,lambda b,x:inputs);gui=self.gui(session);result=Mock()
  with patch.object(c,'prepare'),patch.object(c,'execute',return_value='입장 직전 확인 · 매칭 안 누름') as run:
   self.assertTrue(start(gui,RAID,result));session.worker.join(2);gui._owner_reward_action_test.poll(result)
  run.assert_called_once();self.assertTrue(adapter.closed);inputs.close.assert_called_once()
  self.assertIs(session.adapter_factory,factory);self.assertFalse(gui._owner_reward_action_test.active)
  self.assertIn('입장 직전',result.set.call_args[0][0])
 def test_refused_location_never_runs_the_entry(self):
  adapter=self.fake();session=Session(lambda:None,lambda:self.wrapped(adapter),lambda b,x:Mock());gui=self.gui(session);result=Mock()
  with patch.object(c,'prepare',side_effect=RuntimeError('필드에서 눌러 주세요')),patch.object(c,'execute') as run:
   self.assertTrue(start(gui,RAID,result));session.worker.join(2);gui._owner_reward_action_test.poll(result)
  run.assert_not_called();self.assertIn('필드에서',result.set.call_args[0][0])
 def test_busy_states_create_no_input(self):
  for state in ('running','paused'):
   session=Session(lambda:None,Mock(),Mock());session.state=state
   self.assertFalse(start(self.gui(session),RAID,Mock()));session.adapter_factory.assert_not_called()
  session=Session(lambda:None,Mock(),Mock());gui=self.gui(session);gui._owner_reward_action_test=Controller(gui);gui._owner_reward_action_test.active=True
  self.assertFalse(start(gui,RAID,Mock()));session.adapter_factory.assert_not_called()
 def test_update_cannot_resume_it_as_a_full_macro(self):
  from owner_auto_update import resume_status
  from owner_reward_action_test import controller
  gui=self.gui(Session(lambda:None,Mock(),Mock()));controller(gui).active=True
  self.assertEqual(resume_status(gui,{'status':'running'}),'stopped')

class Rows(Base):
 def close(self):
  for token in self.tk.tk.call('after','info'):self.tk.after_cancel(token)
  super().close()
 def console(self):
  self.gui.logger=logging.getLogger('fake')
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.addCleanup(console.window.destroy);return console
 def test_every_row_has_its_test_including_treasure(self):
  console=self.console()
  buttons=[w for w in walk(console.window) if w.winfo_class()=='TButton' and str(w.cget('text'))=='TEST']
  visible={item['id'] for item,_ in console.native.controls}
  # The growth switches sit on the growth pages, each with its own TEST.
  from owner_settings_layout import GROWTH_SWITCHES
  # The shop page has one; the worn tables and the higher-grade equips on the gear and blessing pages one each; 가호 소환 one.
  self.assertEqual(len(buttons),len(REWARDS)+len(set(TARGETS)&visible)+len(GROWTH_SWITCHES)+1+2+2+1)
  self.assertIn('auto_challenge.treasure_hunt.enabled',TARGETS)
  self.assertIn('auto_challenge.treasure_hunt.enabled',visible)
  self.assertLessEqual({'auto_schedule.boss_raid.enabled','auto_growth.spirit_training.enabled','auto_schedule.field_boss.enabled'},visible)
 def test_each_test_saves_first_and_goes_to_its_own_row(self):
  console=self.console();result=tk.StringVar(self.tk)
  with patch('owner_challenge_test.start') as run:
   with patch.object(console,'save',return_value=False):console.test_action(RAID,result)
   run.assert_not_called()
   with patch.object(console,'save',return_value=True):console.test_action(RAID,result)
   run.assert_called_once_with(self.gui,RAID,result)
 def test_pressing_test_turns_no_schedule_on(self):
  console=self.console()
  with patch('owner_challenge_test.start'):console.test_action(RAID,tk.StringVar(self.tk))
  self.assertIs(self.model().values[RAID],False)
 def test_basic_hunt_rows_are_gone_but_saved(self):
  self.assertIsNone(category('common.potion_and_favorite.source'));self.assertIsNone(category('common.potion_and_favorite.slot'))
  model=self.model();model.save('main_quest',dict(model.values,**{'common.potion_and_favorite.slot':'3번'}))
  console=self.console()
  self.assertNotIn('common.potion_and_favorite.slot',console.native.vars)
  self.assertTrue(console.native.save() is True)
  self.assertEqual(self.model().values['common.potion_and_favorite.slot'],'3번')

if __name__=='__main__':unittest.main()
