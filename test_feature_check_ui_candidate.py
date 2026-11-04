"""Fake-worker tests: no game, server, or input device is touched."""
import sys,threading,time,tempfile,types,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_feature_check_ui_candidate import FeaturePanel

class Session:
 def __init__(self):self.status='stopped';self.alive=False;self.calls=[]
 def snapshot(self):return {'status':self.status,'worker_alive':self.alive}
 def start(self):self.calls.append('session')
 def stop(self):self.calls.append('stop')

class Checks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=tk.Tk();self.root.withdraw();self.addCleanup(self.root.destroy)
  session=Session();self.calls=[]
  gui=NS(root=self.root,closed=threading.Event(),session=session,project=NS(root=Path(self.temp.name)),
         _owner_main=NS(frame=ttk.Frame(self.root)),visual_view=NS(widgets={},originals={}),
         input_preparation=NS(busy=lambda:False),game_hint=tk.StringVar(self.root),
         start_requested=lambda:self.calls.append('request'),_start_after_input_ready=lambda:self.calls.append('ready'),
         launch_flow=NS(start=lambda:self.calls.append('launch')))
  gui.start_button=ttk.Button(self.root,command=gui.start_requested);self.gui=gui
  catalog=types.ModuleType('owner_feature_check_catalog_candidate');catalog.CHECKS=[{'id':'gear','name':'장비'},{'id':'hunt','name':'사냥'}]
  core=types.ModuleType('owner_feature_checks_candidate');core.run_checks=lambda *a,**kw:None;self.core=core
  changes=patch.dict(sys.modules,{'owner_feature_check_catalog_candidate':catalog,'owner_feature_checks_candidate':core})
  changes.start();self.addCleanup(changes.stop)
  self.panel=FeaturePanel(gui);self.panel.open()
 def wait_done(self):
  self.panel.worker.join(timeout=2);self.assertFalse(self.panel.active());self.panel.poll();self.root.update_idletasks()
 def test_button_is_on_stable_main_frame_and_running_pause_cleanup_block(self):
  self.assertIs(self.panel.button.master,self.gui._owner_main.frame)
  for status,alive in [('running',False),('paused',False),('stopped',True)]:
   self.gui.session.status=status;self.gui.session.alive=alive
   self.assertFalse(self.panel.start(['gear']))
  self.gui.session.status='stopped';self.gui.session.alive=False;self.gui.input_preparation.busy=lambda:True
  self.assertFalse(self.panel.start(['gear']));self.assertIsNone(self.panel.worker);self.assertEqual(self.gui.session.calls,[])
 def test_rebinding_is_stable_and_recovers_external_changes(self):
  button=self.gui.start_button;first=str(button.cget('command'))
  for _ in range(20):self.panel.bind_buttons()
  self.assertEqual(str(button.cget('command')),first)
  button.configure(command=lambda:self.calls.append('unsafe'))
  self.panel.bind_buttons();self.assertNotEqual(str(button.cget('command')),first)
  button.invoke();self.assertEqual(self.calls,['request'])
 def test_running_check_fences_start_session_launcher_and_button(self):
  started=threading.Event()
  def run(root,ids,emit,cancel,probe=None):started.set();cancel.wait(2)
  self.core.run_checks=run;self.assertTrue(self.panel.start(['gear']));self.assertTrue(started.wait(1))
  self.gui.start_requested();self.gui.start_button.invoke()
  with self.assertRaises(RuntimeError):self.gui.session.start()
  with self.assertRaises(RuntimeError):self.gui.launch_flow.start()
  with self.assertRaises(RuntimeError):self.gui._start_after_input_ready()
  self.assertEqual(self.calls,[]);self.assertEqual(self.gui.session.calls,[])
  self.panel.stop();self.wait_done();self.gui.session.start();self.assertEqual(self.gui.session.calls,['session'])
 def test_no_probe_cannot_claim_screen_or_overall_success(self):
  def run(root,ids,emit,cancel,probe=None):
   self.assertIsNone(probe);emit({'id':'gear','name':'장비','settings':'정상','screen':'정상','result':'정상','detail':'판독 내용'})
  self.core.run_checks=run;self.panel.start(['gear']);self.wait_done()
  values=self.panel.tree.item('gear','values');self.assertEqual((values[2],values[4]),('미검증','미검증'))
  self.assertEqual(self.panel.details['gear'],'판독 내용')
 def test_probe_forwarding_and_selection(self):
  captured=[];probe=lambda *a:None;self.gui._owner_feature_probe=probe
  def run(root,ids,emit,cancel,probe=None):captured.append((list(ids),probe));emit({'id':'hunt','name':'사냥','settings':'정상','screen':'검사됨','result':'정상','detail':'ok','screen_verified':True,'decision_verified':True})
  self.core.run_checks=run;self.panel.tree.selection_set('hunt');self.panel.run_selected();self.wait_done()
  self.assertEqual(captured,[(['hunt'],probe)]);self.assertEqual(self.panel.tree.item('hunt','values')[4],'정상')
 def test_factory_is_on_main_thread_probe_cleanup_on_worker(self):
  main=threading.get_ident();events=[]
  class Probe:
   def __call__(self,*a):return {}
   def close(self):events.append(('close',threading.get_ident()))
  def factory(cancel):events.append(('factory',threading.get_ident(),cancel));return Probe()
  self.gui._owner_feature_probe_factory=factory
  def run(root,ids,emit,cancel,probe=None):events.append(('run',threading.get_ident(),cancel));return {'report_file':'test-report.json'}
  self.core.run_checks=run;self.panel.start(['gear']);self.wait_done()
  self.assertEqual(events[0][0:2],('factory',main));self.assertEqual(events[1][0],'run');self.assertNotEqual(events[1][1],main)
  self.assertIs(events[0][2],events[1][2]);self.assertEqual(events[2],('close',events[1][1]))
  self.assertIn('test-report.json',self.panel.report_path);self.assertNotIn('test-report.json',self.panel.status.get())
 def test_verified_screen_without_verified_decision_is_not_normal(self):
  self.gui._owner_feature_probe=lambda *a:None
  def run(root,ids,emit,cancel,probe=None):emit({'id':'gear','name':'장비','settings':'정상','screen':'열림','result':'정상','screen_verified':True,'decision_verified':False})
  self.core.run_checks=run;self.panel.start(['gear']);self.wait_done()
  self.assertEqual(self.panel.tree.item('gear','values')[4],'세부 점검 미완료')
 def test_close_requests_cancel_and_keeps_fence_until_worker_exits(self):
  entered=threading.Event();release=threading.Event()
  def run(root,ids,emit,cancel,probe=None):entered.set();release.wait(2)
  self.core.run_checks=run;self.panel.start(['gear']);self.assertTrue(entered.wait(1))
  self.panel.close_dialog();self.assertTrue(self.panel.cancel.is_set())
  with self.assertRaises(RuntimeError):self.gui.session.start()
  release.set();self.wait_done()
 def test_f3_stop_cancels_check_without_touching_stopped_macro(self):
  entered=threading.Event()
  def run(root,ids,emit,cancel,probe=None):entered.set();cancel.wait(2)
  self.core.run_checks=run;self.panel.start(['gear']);self.assertTrue(entered.wait(1))
  owner=Path('C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/owner')
  with patch.object(sys,'path',[str(owner)]+sys.path):
   import owner_controls
   self.gui.action=lambda fn:fn()
   self.assertEqual(owner_controls.run_command(self.gui,'F3'),'stopped')
  self.assertTrue(self.panel.cancel.is_set());self.assertEqual(self.gui.session.calls,[]);self.wait_done()
 def test_factory_reentrant_start_is_fenced_before_worker_exists(self):
  events=[]
  def factory(cancel):
   self.gui.start_requested()
   with self.assertRaises(RuntimeError):self.gui.session.start()
   self.gui.session.stop();events.append(cancel.is_set())
   return None
  self.gui._owner_feature_probe_factory=factory
  self.core.run_checks=lambda root,ids,emit,cancel,probe=None:events.append(cancel.is_set())
  self.assertTrue(self.panel.start(['gear']));self.wait_done()
  self.assertEqual(events,[True,True]);self.assertEqual(self.calls,[]);self.assertEqual(self.gui.session.calls,[])
 def test_factory_failure_releases_fence(self):
  def factory(cancel):raise ValueError('준비 실패')
  self.gui._owner_feature_probe_factory=factory
  self.assertFalse(self.panel.start(['gear']));self.assertFalse(self.panel.active())
  self.gui.session.start();self.assertEqual(self.gui.session.calls,['session'])
 def test_root_destroy_requests_cancellation(self):
  entered=threading.Event()
  def run(root,ids,emit,cancel,probe=None):entered.set();cancel.wait(2)
  self.core.run_checks=run;self.panel.start(['gear']);self.assertTrue(entered.wait(1))
  self.panel.on_root_destroy(NS(widget=self.root));self.assertTrue(self.panel.cancel.is_set());self.wait_done()
 def test_error_message_is_not_overwritten_by_done(self):
  def run(*args,**kwargs):raise ValueError('검사 실패')
  self.core.run_checks=run;self.panel.start(['gear']);self.wait_done();self.assertIn('검사 실패',self.panel.status.get())
 def test_old_worker_queue_does_not_contaminate_new_result(self):
  self.panel.generation=4;self.panel.events.put((3,'row',{'id':'gear','name':'옛 값','result':'정상'}));self.panel.poll()
  self.assertNotEqual(self.panel.tree.item('gear','values')[0],'옛 값')
if __name__=='__main__':unittest.main(verbosity=2)
