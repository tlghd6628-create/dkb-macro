"""Isolated settings + production Session fake-input checks, never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import copy,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import tkinter as tk
from biol_base.session import Session,Context,Cancelled
from owner_settings_console import category,SettingsConsole
from owner_reward_action_test import TARGETS,PATHS,execute,Controller,OneAction
from owner_disassembly_settings import add_fields,grade_key,selected,install,MASTER
from test_settings_theme_20261103 import Base,walk


class UI(Base):
 def close(self):
  for token in self.tk.tk.call('after','info'):
   self.tk.after_cancel(token)
  super().close()
 def setUp(self):
  super().setUp();add_fields(self.schema)
 def test_moved_flags_are_visible_once_and_keep_native_keys(self):
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.addCleanup(console.window.destroy)
  self.assertEqual(category('auto_rewards.blessing.enabled'),'가호')
  self.assertEqual(category('auto_rewards.seal_release.enabled'),'아이템 사용')
  self.assertEqual(category('auto_rewards.inventory_use.enabled'),'아이템 사용')
  for key in ('auto_rewards.blessing.enabled','auto_rewards.seal_release.enabled','auto_rewards.inventory_use.enabled'):
   self.assertIn(key,console.native.vars)
   self.assertEqual(sum(item['id']==key for item,_ in console.native.controls),1)
  self.assertFalse(set(TARGETS)&self.visible('가호'))
  self.assertFalse(set(TARGETS)&self.visible('아이템 사용'))
 def test_only_remaining_reward_page_has_test_buttons(self):
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.addCleanup(console.window.destroy)
  buttons=[w for w in walk(console.window) if w.winfo_class()=='TButton' and str(w.cget('text'))=='TEST']
  # The rest are on the 비경·보스 and 수련 pages: test_challenge_test_20261104.
  from owner_challenge_test import TARGETS as CHALLENGES
  from owner_settings_layout import GROWTH_SWITCHES
  self.assertEqual(len(buttons),len(TARGETS)+len(set(CHALLENGES)&{item['id'] for item,_ in console.native.controls})+len(GROWTH_SWITCHES))
  self.assertEqual(set(TARGETS),set(TARGETS)&self.visible('보상·정리'))
  self.assertTrue(all(str(w.cget('style'))=='DkbTest.TButton' for w in buttons))
 def test_grade_choices_persist_and_legend_is_absent(self):
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.addCleanup(console.window.destroy)
  for code in ('normal','rare','hero'):self.assertIn(grade_key(code),console.native.vars)
  self.assertNotIn(grade_key('legend'),console.native.vars)
  self.assertEqual(selected(console.native.model.values),('일반',))
  console.native.vars[grade_key('rare')].set(True)
  console.native.vars['auto_rewards.seal_release.enabled'].set(True)
  console.native.vars['auto_rewards.blessing.enabled'].set(True)
  self.assertTrue(console.save())
  model=self.model();self.assertEqual(selected(model.values),('일반','희귀'))
  self.assertIs(model.values['auto_rewards.blessing.enabled'],True)
  self.assertIs(model.values['auto_rewards.seal_release.enabled'],True)
 def test_start_test_saves_before_request_and_does_not_run_on_failed_save(self):
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.addCleanup(console.window.destroy)
  runner=Mock();result=tk.StringVar(self.tk)
  with patch('owner_reward_action_test.controller',return_value=runner):
   with patch.object(console,'save',return_value=True):console.test_action(MASTER,result)
   runner.start.assert_called_once_with(MASTER,result,console.window)
   runner.reset_mock();console.notice.set('보류')
   with patch.object(console,'save',return_value=False):console.test_action(MASTER,result)
   runner.start.assert_not_called();self.assertEqual(result.get(),'보류')


class Adapter:
 input_backend='fake-only'
 def __init__(self,values):self.values=values;self.calls=[];self.closed=False;self.project=S(root=bootstrap.T/'test_scratch/no-test-reservations')
 def get_due_schedules(self):return ['ordinary_due']
 def record(self,name,context,inputs):
  context.checkpoint();self.calls.append((name,{k:v for k,v in self.values.items() if k.endswith('.enabled')}));return True
 def __getattr__(self,name):
  if name.startswith('run_'):return lambda context,inputs:self.record(name,context,inputs)
  raise AttributeError(name)
 def _run_auto_features(self,context,inputs,**kwargs):
  context.checkpoint()
  self.calls.append(({k:v for k,v in self.values.items() if k.endswith('.enabled')},self.get_due_schedules(),kwargs))
  return True
 def close(self):self.closed=True


class Runtime(unittest.TestCase):
 def context(self):
  context=Context(threading.Event(),threading.Event());context.run_action=lambda key,operation:operation();return context
 def wrapped(self,adapter,session=None):
  from operating_policy import PolicyAdapter
  import logging
  return PolicyAdapter(adapter,{'execution':{'failure_limit':1,'pause_on_error':False,'action_gap_ms':0},'notifications':{'result_summary':False}},logging.getLogger('fake'),session)
 def test_every_test_uses_existing_dispatch_and_exposes_only_selected_flag(self):
  values={key:False for key in TARGETS};values.update({'auto_growth.equipment.enabled':True,'auto_rewards.blessing.enabled':True,'auto_rewards.seal_release.enabled':True})
  for key in (key for key,path in PATHS.items() if path is not None):
   adapter=Adapter(copy.deepcopy(values));before=adapter.values
   with patch('project_adapter.market_inventory.run_equipment_disassembly',side_effect=lambda adapter,c,i:adapter.record('run_equipment_disassembly',c,i)):
    self.assertTrue(execute(adapter,self.context(),Mock(),key))
   self.assertIs(adapter.values,before);self.assertEqual(adapter.values,values)
   self.assertEqual(len(adapter.calls),1)
   name,flags=adapter.calls[0]
   self.assertEqual(name,PATHS[key][1])
   self.assertEqual([k for k,v in flags.items() if v],[key])
   self.assertEqual(adapter.get_due_schedules(),['ordinary_due'])
 def test_dispatch_exception_restores_values_and_due_schedule(self):
  key='auto_rewards.guide.enabled';adapter=Adapter({key:False});before=adapter.values
  adapter.run_guide_rewards=Mock(side_effect=RuntimeError('fixture'))
  with self.assertRaisesRegex(RuntimeError,'fixture'):execute(adapter,self.context(),Mock(),key)
  self.assertIs(adapter.values,before)
 def test_existing_session_owns_and_closes_the_test_and_restores_factory(self):
  adapter=Adapter({MASTER:False});inputs=Mock();factory=Mock(return_value=self.wrapped(adapter))
  session=Session(lambda:None,factory,lambda backend,context:inputs)
  gui=S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),game_window=S(require_ready=Mock()))
  controller=Controller(gui);result=Mock()
  with patch('owner_reward_action_test.prepare'),patch('project_adapter.market_inventory.run_equipment_disassembly',side_effect=lambda adapter,c,i:adapter.record('run_equipment_disassembly',c,i)):
   self.assertTrue(controller.start(MASTER,result,None))
   session.worker.join(2);controller.poll(result)
  self.assertFalse(session.snapshot()['worker_alive']);self.assertEqual(session.snapshot()['status'],'stopped')
  self.assertIs(session.adapter_factory,factory);self.assertFalse(controller.active)
  self.assertTrue(adapter.closed);inputs.close.assert_called_once()
  self.assertEqual(len(adapter.calls),1)
 def test_a_worker_that_builds_late_still_runs_the_test_not_the_macro(self):
  """Seen live on pc1: the worker asked for its adapter after start() returned and ran the whole macro."""
  adapter=Adapter({MASTER:False});inputs=Mock();factory=Mock(return_value=self.wrapped(adapter))
  session=Session(lambda:None,factory,lambda backend,context:inputs);late=threading.Event()
  original_start=session.start;started=threading.Event()
  def start():
   # Like the OCR-readiness start: the real start, and its factory call, come after start() returned.
   def later():late.wait(2);original_start();started.set()
   threading.Thread(target=later,daemon=True).start()
  session.start=start
  gui=S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),game_window=S(require_ready=Mock()))
  controller=Controller(gui);result=Mock()
  with patch('owner_reward_action_test.prepare'),patch('project_adapter.market_inventory.run_equipment_disassembly',side_effect=lambda adapter,c,i:adapter.record('run_equipment_disassembly',c,i)):
   self.assertTrue(controller.start(MASTER,result,None));late.set();self.assertTrue(started.wait(2))
   session.worker.join(2);controller.poll(result)
  self.assertEqual([name for name,_ in adapter.calls],['run_equipment_disassembly'])
  self.assertIs(session.adapter_factory,factory);self.assertFalse(controller.active)
 def test_a_worker_that_never_took_the_test_factory_leaves_the_ordinary_one(self):
  session=Session(lambda:None,Mock(),Mock());session.start=lambda:None
  gui=S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),game_window=S(require_ready=Mock()))
  factory=session.adapter_factory;controller=Controller(gui);result=Mock()
  self.assertTrue(controller.start(MASTER,result,None));self.assertIsNot(session.adapter_factory,factory)
  controller.poll(result);self.assertIs(session.adapter_factory,factory)
 def test_market_keeps_its_selected_item_filters_and_training_is_not_fake_success(self):
  key='auto_register.market.enabled';adapter=Adapter({key:False,'auto_register.market.bag.enabled':True,'auto_rewards.mail.enabled':True})
  self.assertTrue(execute(adapter,self.context(),Mock(),key))
  self.assertEqual(adapter.calls[0][1],{key:True,'auto_register.market.bag.enabled':True,'auto_rewards.mail.enabled':False})
  with self.assertRaisesRegex(RuntimeError,'기존 실행 경로 없음'):execute(adapter,self.context(),Mock(),'auto_rewards.training_log.enabled')
 def test_running_paused_preparing_and_double_requests_do_not_create_inputs(self):
  for state in ('running','paused'):
   session=Session(lambda:None,Mock(),Mock());session.state=state
   controller=Controller(S(session=session,closed=threading.Event(),root=S(after=Mock())))
   self.assertFalse(controller.start(MASTER,Mock(),None));session.adapter_factory.assert_not_called()
  session=Session(lambda:None,Mock(),Mock())
  gui=S(session=session,closed=threading.Event(),root=S(after=Mock()),input_preparation=S(busy=lambda:True))
  controller=Controller(gui);self.assertFalse(controller.start(MASTER,Mock(),None));session.adapter_factory.assert_not_called()
 def test_stop_during_ready_uses_same_stop_event_and_sends_no_action(self):
  adapter=Adapter({MASTER:False});entered=threading.Event()
  class Ready:
   def wait(self,context):
    entered.set()
    while not context.stop.wait(.01):context.checkpoint()
    context.checkpoint()
  session=Session(lambda:None,lambda:self.wrapped(adapter),lambda b,c:Mock())
  gui=S(session=session,closed=threading.Event(),root=S(after=Mock()),_owner_ocr_readiness=Ready(),preparation_gate=Mock(),game_window=S(require_ready=Mock()))
  controller=Controller(gui);result=Mock()
  self.assertTrue(controller.start(MASTER,result,None));self.assertTrue(entered.wait(1))
  session.stop();session.worker.join(2);controller.poll(result)
  self.assertEqual(adapter.calls,[]);self.assertFalse(controller.active);self.assertTrue(adapter.closed)
 def test_unreached_native_disassembly_commit_is_never_claimed_complete(self):
  original=Mock();native=S(run_equipment_disassembly=original);alias=S(run_equipment_disassembly=original)
  install(native,[alias]);self.assertIs(alias.run_equipment_disassembly,native.run_equipment_disassembly)
  adapter=S(values={MASTER:True,grade_key('normal'):True})
  self.assertTrue(native.run_equipment_disassembly(adapter,self.context(),Mock()))
  original.assert_called_once();self.assertEqual(adapter._owner_disassembly_outcome['state'],'not_attempted')
  self.assertFalse(adapter._owner_disassembly_outcome['verified'])
 def test_test_session_never_becomes_an_update_full_macro_resume(self):
  from owner_auto_update import resume_status
  self.assertEqual(resume_status(S(_owner_reward_action_test=S(active=True)),{'status':'running'}),'stopped')
  self.assertEqual(resume_status(S(_owner_reward_action_test=S(active=False)),{'status':'running'}),'running')
  self.assertEqual(resume_status(S(),{'status':'paused'}),'paused')
 def test_checker_not_installed_anymore(self):
  import ast
  tree=ast.parse((bootstrap.T/'owner_support.py').read_text(encoding='utf-8-sig'))
  self.assertFalse(any(isinstance(n,ast.ImportFrom) and n.module in ('owner_feature_check_live_candidate','owner_feature_check_ui_candidate') for n in ast.walk(tree)))
 def test_real_native_reward_dispatch_has_its_original_action_context(self):
  import inspect,logging
  from operating_policy import ActionPolicy
  from project_adapter._entry import Adapter as Native
  for key,method in (('auto_rewards.guide.enabled','run_guide_rewards'),('auto_rewards.event.enabled','run_event_rewards'),
                     ('auto_rewards.mail.enabled','run_mail_rewards'),('auto_rewards.achievement.enabled','run_achievement_rewards')):
   calls=[]
   adapter=S(values={key:True},project=S(app_id='DKB'))
   for name in ('run_guide_rewards','run_event_rewards','run_mail_rewards','run_achievement_rewards'):
    setattr(adapter,name,lambda *a,name=name,**kw:calls.append(name) or True)
   context=self.context()
   policy=ActionPolicy(context,{'execution':{'failure_limit':1,'pause_on_error':False,'action_gap_ms':0}},logging.getLogger('fake'))
   context.run_action=policy.run
   self.assertTrue(inspect.unwrap(Native._run_auto_features)(adapter,context,Mock(),wait_for_hunt=False,potion_done=True,periodic_wait=False))
   self.assertEqual(calls,[method])
 def test_preparation_allows_instance_and_only_holds_the_last_ten_minutes(self):
  from owner_reward_action_test import prepare
  from project_adapter import town_services
  from owner_reward_context import decision
  for remaining in (1800,600,None):
   service=Mock();adapter=S(exit_sleep_mode=Mock());context=self.context()
   with patch.object(town_services,'TownServices',return_value=service),patch('owner_start_menu.normalize') as normalize,patch('owner_progression.inventory_parts',return_value=(False,False)),patch('owner_reward_context.admit',return_value=decision(True,remaining)):
    if remaining==1800:prepare(adapter,context,Mock())
    else:
     with self.assertRaisesRegex(RuntimeError,'보상·정리 시작 보류'):prepare(adapter,context,Mock())
    normalize.assert_called_once_with(service)


if __name__=='__main__':unittest.main()
