"""Saved screenshots and simulated input only; never click the real game."""
import sys,unittest,ctypes,contextlib,tempfile,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
import owner_quest_emote_candidate as e

ROOT=bootstrap.A/'logs'
def frame(path):return np.asarray(Image.open(ROOT/path).convert('RGB')).copy()
FIELD=frame('quest-incidents/20261101T205743Z-1bafafd4/screen.png')
MENU1=frame('manual-captures/20261102_062236_a74a1361.png')
MENU2=frame('manual-captures/20261102_062305_fa2a9098.png')

class Context:
 def checkpoint(self):pass
 def wait(self,x):pass
class UI:
 def __init__(self):
  self.context=Context();self.adapter=NS(project=NS(root=bootstrap.A));self.inputs=NS()
  self.page='field';self.actions=[]
  self.chat=FIELD.copy();self.chat[:,:245]=MENU1[:,:245]
  self.menu=self.chat.copy();self.menu[300:479,245:430]=MENU1[300:479,245:430]
 def frame(self):return {'field':FIELD,'chat':self.chat,'menu':self.menu}[self.page].copy()
 def normal(self):return self.page=='field'
 def normal_frame(self,frame):return self.page=='field'
 def wait(self,predicate,seconds=5):
  if not predicate(self.frame()):raise e.Pending('not observed')
 def key(self,key):self.actions.append(('key',key));self.page='chat'
 def click(self,x,y,predicate):
  if not predicate(self.frame()):raise e.Pending('changed')
  self.actions.append(('click',x,y))
  if self.page=='field' and x==114:self.page='chat'
  elif self.page=='chat' and x==198:self.page='menu'
  elif self.page=='menu' and x==338:self.page='chat'
  elif self.page=='menu' and x==419:self.page='chat'
  elif self.page=='chat' and x==232:self.page='field'

class Tests(unittest.TestCase):
 def test_real_saved_screens_locate_exact_card_and_different_location_is_rejected(self):
  self.assertTrue(e.objective(FIELD));self.assertTrue(e.target_zone(FIELD))
  self.assertEqual(e.card(MENU1),(338,449));self.assertEqual(e.card(MENU2),(338,449))
  self.assertTrue(e.empty_chat(MENU1));self.assertTrue(e.empty_chat(MENU2))
  self.assertFalse(e.target_zone(MENU1));self.assertFalse(e.target_zone(MENU2))
  changed=MENU1.copy();changed[431:468,326:351]=0;self.assertIsNone(e.card(changed))
  book=NS(item={'quests':{'k':{'title':'[외전] 산길의 호환','mode':'sub_quest','group':True}}})
  self.assertTrue(e.suppress_native_chat(book,'k',MENU1));self.assertTrue(e.suppress_native_chat(book,'k',MENU2))
  self.assertFalse(e.suppress_native_chat(book,'other',MENU1))
 def test_no_emote_input_without_native_request_or_explicit_current_requirement(self):
  # This requirement test must not read this PC's live interrupted-send marker.
  temporary=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(temporary.cleanup)
  marker=patch.object(e,'_marker_path',return_value=Path(temporary.name)/'navigation.json')
  marker.start();self.addCleanup(marker.stop)
  ui=UI();row={'title':'[외전] 산길의 호환','mode':'sub_quest','group':True};book=NS(item={'active':'k','quests':{'k':row}},commit=lambda:None)
  ui.rows=lambda *a,**kw:[]
  with patch('owner_emote_dispatch.known_goal',return_value=None),patch('owner_progression.state',return_value=NS(character='c')),patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch.object(e,'save_navigation'):
   self.assertFalse(e.run(ui,book,'k'))
  self.assertEqual(ui.page,'field');self.assertEqual(ui.actions,[])
  self.assertNotIn('emote_attempt',row)
  alias={'title':'[외전] 1산길의 호환','mode':'sub_quest','group':True}
  book.item['quests']['alias']=alias;book.item['active']='alias'
  with patch('owner_emote_dispatch.known_goal',return_value=None),patch('owner_progression.state',return_value=NS(character='c')),patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'):
   self.assertFalse(e.run(ui,book,'alias'))
  self.assertEqual(ui.actions,[])
 def test_stop_prevents_all_input(self):
  ui=UI();ui.context.checkpoint=lambda:(_ for _ in ()).throw(RuntimeError('stopped'))
  row={'title':'[외전] 산길의 호환','mode':'sub_quest','group':True};book=NS(item={'active':'k','quests':{'k':row}},commit=lambda:None)
  with patch('owner_progression.state',return_value=NS(character='c')),patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'):
   with self.assertRaisesRegex(RuntimeError,'stopped'):e.run(ui,book,'k')
  self.assertEqual(ui.actions,[])
 def test_scroll_reuses_existing_wheel_with_physical_cursor_verification(self):
  ui=UI();ui.page='menu';calls=[]
  ui.wheel=lambda direction,notches,**kw:calls.append((direction,notches,kw))
  # This composite supplies a real on-site ring and the observed menu.
  e.wheel(ui,lambda:True)
  self.assertEqual(calls[0][:2],(-1,1));self.assertTrue(calls[0][2]['verify_cursor'])
  self.assertEqual(calls[0][2]['at'],(338,390));self.assertTrue(calls[0][2]['scene'](ui.frame()))
 def test_native_wheel_rejects_nonphysical_cursor_or_foreground(self):
  from owner_mission_ui import MissionUI
  import input_target,window_resolution,win32gui
  sends=[]
  class Send:
   def __call__(self,*args):sends.append(1);return 1
  fake=NS(SendInput=Send());ui=UI();ui.page='menu';ui.adapter.window=object()
  ui.inputs=NS(transaction=lambda:contextlib.nullcontext(),move=lambda *a:None,_guard_target=lambda:None)
  with patch.object(ctypes.windll,'user32',fake),patch.object(input_target,'resolve',return_value=(11,338,390)),\
       patch.object(window_resolution,'physical_coordinates',side_effect=contextlib.nullcontext),\
       patch.object(win32gui,'ClientToScreen',return_value=(500,600)),\
       patch.object(win32gui,'GetCursorPos',return_value=(1,2)),patch.object(win32gui,'GetForegroundWindow',return_value=11):
   with self.assertRaises(e.Pending):MissionUI.wheel(ui,-1,1,at=(338,390),verify_cursor=True,scene=lambda f:True)
  self.assertEqual(sends,[])
 def test_interrupted_owned_menu_closes_on_start_without_emote_or_text(self):
  from roi_runtime import RoiDetector
  real_detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.page='menu';ui.adapter.project.root=root
   e.save_navigation(root,'profile','opened')
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=real_detector):
    self.assertTrue(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs))
   self.assertEqual(ui.actions,[('click',419,312),('click',232,17)])
   self.assertEqual(json.loads(e._marker_path(root).read_text(encoding='utf-8'))['phase'],'closed')
 def test_unconfirmed_opening_closes_only_proven_empty_chat_on_start(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.page='chat';ui.adapter.project.root=root;e.save_navigation(root,'profile','opening')
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
    self.assertTrue(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs))
   self.assertEqual(ui.actions,[('click',232,17)]);self.assertEqual(json.loads(e._marker_path(root).read_text(encoding='utf-8'))['phase'],'closed')
 def test_unconfirmed_opening_clears_only_on_proved_field(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.adapter.project.root=root;e.save_navigation(root,'profile','opening')
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
    self.assertTrue(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs))
   self.assertEqual(ui.actions,[]);self.assertEqual(json.loads(e._marker_path(root).read_text(encoding='utf-8'))['phase'],'closed')
 def test_owned_chat_with_text_or_damaged_placeholder_never_closes(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  for damage in ('typed','damaged'):
   with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);ui=UI();ui.page='menu';ui.adapter.project.root=root
    if damage=='typed':ui.chat[451:464,144:180]=255;ui.menu[451:464,144:180]=255
    else:ui.chat[452:458,75:85]=0;ui.menu[452:458,75:85]=0
    e.save_navigation(root,'profile','opened')
    with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
     with self.assertRaises(e.Pending):e.normalize_after_stop(ui.adapter,ui.context,ui.inputs)
    self.assertEqual(ui.actions,[('click',419,312)]);self.assertEqual(ui.page,'chat');self.assertEqual(json.loads(e._marker_path(root).read_text(encoding='utf-8'))['phase'],'opened')
 def test_hidden_placeholder_recovers_after_only_panel_x(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.page='menu';ui.adapter.project.root=root
   ui.menu[448:468,55:214]=20 # observed panel hides placeholder, no typed text
   e.save_navigation(root,'profile','opened')
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
    self.assertTrue(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs))
   self.assertEqual(ui.actions,[('click',419,312),('click',232,17)])
 def test_stop_after_panel_x_never_closes_chat(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.page='menu';ui.adapter.project.root=root;e.save_navigation(root,'profile','opened')
   original=ui.click
   def click(x,y,proof):
    original(x,y,proof)
    if (x,y)==(419,312):ui.context.checkpoint=lambda:(_ for _ in ()).throw(RuntimeError('stopped'))
   ui.click=click
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='profile'),patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
    with self.assertRaisesRegex(RuntimeError,'stopped'):e.normalize_after_stop(ui.adapter,ui.context,ui.inputs)
   self.assertEqual(ui.actions,[('click',419,312)]);self.assertEqual(ui.page,'chat')
 def test_user_opened_empty_chat_closes_at_requested_start_without_ownership_claim(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.page='menu';ui.adapter.project.root=root
   with patch('owner_mission_ui.MissionUI',return_value=ui),patch('roi_runtime.RoiDetector',return_value=detector):
    self.assertTrue(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs))
   self.assertEqual(ui.actions,[('click',419,312),('click',232,17)]);self.assertFalse(e._marker_path(root).exists())
 def test_nonchat_special_or_unknown_start_returns_without_ui_or_field_requirement(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);ui=UI();ui.adapter.project.root=root;e.save_navigation(root,'profile','opening')
   unknown=np.zeros_like(FIELD)
   with patch('owner_mission_ui.MissionUI',side_effect=AssertionError('must not open UI')),patch('roi_runtime.RoiDetector',return_value=detector):
    self.assertFalse(e.normalize_after_stop(ui.adapter,ui.context,ui.inputs,frames=(unknown,unknown.copy()),field_confirmed=False))
   self.assertEqual(ui.actions,[]);self.assertEqual(json.loads(e._marker_path(root).read_text(encoding='utf-8'))['phase'],'opening')

if __name__=='__main__':unittest.main(verbosity=2)
