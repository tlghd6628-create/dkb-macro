"""Saved-frame checks for release 12: story row colours, emote cards, settings click."""
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
import bootstrap
import owner_emote_dispatch as d
import owner_story_groups as story

P=Path(__file__).parent/'live_fixtures'
def frame(name):return np.asarray(Image.open(P/name).convert('RGB'))
ROWS=(120,158,197,235,273,312,350,388)
class StoryRows(unittest.TestCase):
 def test_every_visible_suitable_row_reads_as_suitable(self):
  # The old image comparison rejected six of these eight real 적합 rows.
  f=frame('story-rows-suitable.png')
  self.assertEqual([r['y'] for r in story.group_rows(f)],list(ROWS))
  for y in ROWS:self.assertEqual(story.row_tag(f,y),'적합',y);self.assertTrue(story.suitable(f,y))
 def test_challenge_and_danger_rows_are_not_suitable(self):
  for name,tag in (('story-rows-challenge.png','도전'),('story-rows-danger.png','위험')):
   f=frame(name);rows=[r['y'] for r in story.group_rows(f) if 114<=r['y']<=420 and story.row_tag(f,r['y'])==tag]
   self.assertTrue(rows,name)
   for y in rows:self.assertFalse(story.suitable(f,y))
 def test_unknown_or_empty_row_is_not_suitable(self):
  self.assertIsNone(story.row_tag(np.zeros((479,897,3),dtype='uint8'),200))
  self.assertIsNone(story.row_tag(np.zeros((10,10,3),dtype='uint8'),200))

class EmoteCards(unittest.TestCase):
 def test_requested_cards_are_found_at_other_scroll_positions(self):
  # Actual23:13 panel: the same row at three positions over this background.
  for name,y in (('emote-panel-row-324.png',334),('emote-panel-row-356.png',366),('emote-panel-row-388.png',398)):
   f=frame(name)
   self.assertEqual([d.card_hit(f,s) for s in ('졸기','뽐내기','황당')],[(279,y),(338,y),(397,y)],name)
 def test_cards_not_on_screen_are_not_matched(self):
  for name in ('emote-panel-top.png','emote-panel-middle.png','emote-panel-bottom.png'):
   f=frame(name)
   for target in ('졸기','뽐내기','황당'):self.assertIsNone(d.card_hit(f,target),(name,target))
 def test_card_hidden_by_scroll_button_waits_for_a_clear_position(self):
  f=frame('emote-panel-row-420.png')
  self.assertIsNone(d.card_hit(f,'황당'))
  self.assertEqual(d.card_hit(f,'졸기'),(279,430))
 def test_closed_panel_and_unknown_target_stay_unmatched(self):
  self.assertIsNone(d.card_hit(np.zeros((479,897,3),dtype='uint8'),'황당'))
  self.assertIsNone(d.card_hit(frame('emote-panel-row-324.png'),'웃음'))

class SettingsClick(unittest.TestCase):
 def _show(self,snapshot):
  import tkinter as tk
  import owner_hunt_settings_candidate as hunt
  root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
  button=tk.Button(root)
  gui=S(root=root,logger=Mock(),session=S(snapshot=snapshot),details_button=button,project=S(root=Path(__file__).parent))
  with patch('owner_telemetry.install'),patch('owner_settings_layout.install'):hunt.install(gui)
  return gui,hunt
 def test_failure_opening_settings_is_logged_and_shown(self):
  def broken():raise RuntimeError('boom')
  gui,hunt=self._show(broken)
  with patch.object(hunt.messagebox,'showerror') as shown:gui.open_details()
  gui.logger.exception.assert_called_once()
  self.assertIn('boom',shown.call_args[0][1])
 def test_running_program_still_explains_stop_first(self):
  gui,hunt=self._show(lambda:{'status':'running','worker_alive':True})
  with patch.object(hunt.messagebox,'showinfo') as shown:gui.open_details()
  self.assertIn('중지',shown.call_args[0][1])
  gui.logger.exception.assert_not_called()

class ResultOnlyAndBinding(unittest.TestCase):
 def setUp(self):
  import tempfile
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)
 def test_unreadable_binding_keeps_a_proven_mismatch(self):
  import owner_character_binding as binding
  adapter=S(project=S(root=self.root))
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='server / A'):
   binding.observe(adapter,'hash-A',50);binding.observe(adapter,'hash-B',50)
   self.assertTrue(binding.mismatch(adapter))
   (self.root/'settings/owner-character-binding.json').write_text('{broken',encoding='utf-8')
   binding.observe(adapter,'hash-B',50);self.assertTrue(binding.mismatch(adapter))
 def test_timetable_result_retry_reaches_runtime_as_result_only(self):
  import owner_outcome as outcome,owner_timetable as timetable
  for key in ('gear','growth'):
   job=timetable.BY_KEY[key];seen=[]
   adapter=S(project=S(root=self.root),values={job.setting:True},mode='auto_mode')
   plan=S(state={key:{'status':'pending','retry_mode':'reconcile','incomplete_retry':True}},values={job.setting:True},
          reason=lambda k:None,begin=lambda k:None,apply_outcome=lambda *a,**kw:None)
   def runtime():seen.append(adapter._owner_growth_reconcile_only);return True
   with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'config',return_value={}),patch.object(timetable,'classify_outcome',return_value=outcome.Outcome(outcome.DONE)):
    timetable.scheduled_call(runtime,job.label,(),{},adapter,timed_dispatch=True)
   self.assertEqual(seen,[True],key);self.assertIs(adapter._owner_growth_reconcile_only,False)
 def test_ordinary_retry_is_not_result_only(self):
  import owner_outcome as outcome,owner_timetable as timetable
  job=timetable.BY_KEY['gear'];seen=[]
  adapter=S(project=S(root=self.root),values={job.setting:True},mode='auto_mode')
  plan=S(state={'gear':{'status':'pending','retry_mode':'recheck','incomplete_retry':True}},values={job.setting:True},
         reason=lambda k:None,begin=lambda k:None,apply_outcome=lambda *a,**kw:None)
  def runtime():seen.append(getattr(adapter,'_owner_growth_reconcile_only',False));return True
  with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'config',return_value={}),patch.object(timetable,'classify_outcome',return_value=outcome.Outcome(outcome.DONE)):
   timetable.scheduled_call(runtime,job.label,(),{},adapter,timed_dispatch=True)
  self.assertEqual(seen,[False])
 def _energy(self,saved):
  import owner_energy_native_candidate as energy
  from owner_gear_decision_candidate import Observation
  name=energy.NAMES[0];seen=[]
  def obs(seq,level):return Observation(seq,float(seq),'character','item','slot',name,level,5,None,True,None,None)
  if saved:saved['pending']={'phase':'sent','before':obs(1,3)}
  class Intents:
   def pending(self):return saved.get('pending')
   def complete(self,result):saved['pending']=None
  class FakeGuard:
   def __init__(self,*a,**k):pass
   def run_one(self,*a,**k):seen.append('fresh');return 'hold_policy'
  context=S(checkpoint=lambda:None,wait=lambda n:None)
  service=S(adapter=S(project=S(root=self.root),_owner_growth_reconcile_only=True),check=lambda:None,capture=lambda:None)
  observer=S(read_pair=lambda:{'screen_proof':True,'first':obs(3,4),'second':obs(4,4)})
  with patch.object(energy,'Store',return_value=S(path=self.root/'profile.json')),patch.object(energy,'IntentStore',return_value=Intents()),patch.object(energy,'EnergyObserver',return_value=observer),patch.object(energy,'Guard',FakeGuard):
   energy.run_energy(service,context,'character',{name:{'enabled':True,'stage':9}},text_reader=lambda *a:{'name':name})
  return seen,saved
 def test_energy_result_only_never_requests_a_fresh_action(self):
  seen,saved=self._energy({'pending':True})
  self.assertEqual(seen,[]);self.assertIsNone(saved['pending'])
  self.assertEqual(self._energy({})[0],[])

class RealModulePath(unittest.TestCase):
 def test_owner_modules_only_import_tools_that_ship_in_the_app_package(self):
  # The running program's `tools` package is DKB_Auto/tools. The test bootstrap
  # also exposes the base folder, which hid the 세부설정 import failure.
  import ast
  here=Path(__file__).parent;bad=[]
  shipped={p.name.split('.')[0] for p in (bootstrap.A/'tools').iterdir()}
  for path in here.glob('owner_*.py'):
   for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
    if isinstance(node,ast.ImportFrom) and (node.module or '').startswith('tools.') and node.module.split('.')[1] not in shipped:bad.append((path.name,node.module))
  self.assertEqual(bad,[])

class SettingsWindow(unittest.TestCase):
 def test_failed_build_leaves_no_window_behind(self):
  import tkinter as tk
  import owner_settings_console as console
  root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
  gui=S(root=root)
  with patch.object(console,'NativeFields'),patch.object(console.SettingsConsole,'build',side_effect=KeyError('field')):
   with self.assertRaises(KeyError):console.SettingsConsole(gui,{})
  self.assertEqual([w for w in root.winfo_children() if isinstance(w,tk.Toplevel)],[])
 def test_buttons_rebind_once_and_after_replacement(self):
  import tkinter as tk
  from tkinter import ttk
  import owner_hunt_settings_candidate as hunt
  root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
  shown=ttk.Button(root);original=ttk.Button(root)
  gui=S(root=root,logger=Mock(),session=S(snapshot=lambda:{}),details_button=ttk.Button(root),project=S(root=Path(__file__).parent),
        visual_view=S(widgets={'details':shown},originals={'details':original}))
  with patch('owner_telemetry.install'),patch('owner_settings_layout.install'):hunt.install(gui)
  command=str(shown.cget('command'));self.assertEqual(str(shown.cget('text')),'세부설정');self.assertTrue(str(original.cget('command')))
  gui._owner_hunt_rebind();self.assertEqual(str(shown.cget('command')),command)
  shown.configure(command='');gui._owner_hunt_rebind();self.assertTrue(str(shown.cget('command')))

if __name__=='__main__':unittest.main()
