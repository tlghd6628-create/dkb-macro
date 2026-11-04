"""Retained actual screens and isolated fake services; no real input/OCR."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,unittest,threading,logging,tempfile
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from project_adapter import event_rewards as event,protected_assets as protected
from biol_base.session import Context,Cancelled
import owner_reward_visual_guard as visual
import owner_disassembly_settings as dis
import owner_reward_context as timing
import json
P=bootstrap.A/'logs/scene-corpus/20261104'
def frame(name):return np.array(Image.open(P/name/'screen.png').convert('RGB'))
GOOD=frame('20261104T000236-9232b4b1');LOCKED=frame('20261104T000246-ce3ac2ce')
POTION=frame('20261104T000305-c7720cc2');INTRO=frame('20261104T000523-4ffa1eda')
TOAST=frame('20261104T000204-1588c487');TOAST2=frame('20261104T000203-f974598c')

class Visual(unittest.TestCase):
 def setUp(self):
  cls=event.EventGlowDetector;before=(cls.find,cls.recheck_point,cls.boxes)
  self.addCleanup(lambda:setattr(cls,'find',before[0]));self.addCleanup(lambda:setattr(cls,'recheck_point',before[1]));self.addCleanup(lambda:setattr(cls,'boxes',before[2]))
  roi=json.loads(protected.read_text(bootstrap.A/'profiles/DKB/roi.json',encoding='utf-8-sig'))
  names=list(dict.fromkeys([v for v in vars(event).values() if isinstance(v,str) and v in roi]+['체크_이벤트']))
  self.detector=RoiDetector(bootstrap.A/'profiles/DKB',names)
  self.native=before;visual.install()
 def proxy(self):return event.EventGlowDetector(self.detector)
 def test_actual_eligible_free_reward_keeps_original_box(self):
  original=self.native[2](self.proxy(),GOOD)
  self.assertEqual(self.proxy().boxes(GOOD),original);self.assertEqual(len(original),1)
 def test_actual_future_locked_reward_is_removed(self):
  self.assertTrue(visual.locked_slot(LOCKED,(665,322,700,356)))
  self.assertTrue(self.native[2](self.proxy(),LOCKED))
  self.assertEqual(self.proxy().boxes(LOCKED),[])
 def test_potion_and_introduction_red_art_are_not_notifications(self):
  for screen in (POTION,INTRO):
   self.assertIsNotNone(self.native[0](self.proxy(),event.DOT,screen,event.REWARD_RANGE))
   self.assertIsNone(self.proxy().find(event.DOT,screen,event.REWARD_RANGE))
   self.assertIsNone(self.proxy().recheck_point(event.DOT,screen,(455,264,(455,264,456,265)),event.REWARD_RANGE))
 def test_sidebar_dot_remains_native_and_install_is_idempotent(self):
  native=self.native[0](self.proxy(),event.DOT,GOOD,event.DOT_RANGE)
  self.assertEqual(self.proxy().find(event.DOT,GOOD,event.DOT_RANGE),native)
  before=event.EventGlowDetector.find;visual.install();self.assertIs(before,event.EventGlowDetector.find)
 def test_field_has_no_event_reward_candidates(self):
  self.assertEqual(self.proxy().boxes(TOAST2),[])
 def test_actual_disassembly_toast_and_false_receipts(self):
  self.assertTrue(visual.disassembly_result(TOAST));self.assertFalse(visual.disassembly_result(TOAST2))
  for screen in (GOOD,LOCKED,np.zeros_like(TOAST),np.full_like(TOAST,255)):
   self.assertFalse(visual.disassembly_result(screen))

class ResultProof(unittest.TestCase):
 def test_two_stable_real_toast_frames_prove_result_without_confirmation(self):
  scope=S(commit=True,proof=False,proof_first=None)
  with patch.object(dis.time,'monotonic',side_effect=[1,2,2.12]):
   dis.observe_result(scope,TOAST2);self.assertFalse(scope.proof)
   dis.observe_result(scope,TOAST);self.assertFalse(scope.proof)
   dis.observe_result(scope,TOAST);self.assertTrue(scope.proof)
 def test_result_without_our_commit_is_not_attributed_to_this_action(self):
  scope=S(commit=False,proof=False,proof_first=None)
  dis.observe_result(scope,TOAST);self.assertFalse(scope.proof)
 def test_optional_missing_message_only_replaced_after_proof(self):
  self.addCleanup(setattr,dis.LOCAL,'scope',None)
  for proof in (False,True):
   dis.LOCAL.scope=S(proof=proof)
   r=logging.LogRecord('project_gui.DKB',20,'',1,'장비 분해 단계 미감지 · '+dis.CONFIRM+' · 클릭 생략',(),None)
   dis.OptionalConfirmLog().filter(r)
   self.assertEqual('완료 확인' in r.getMessage(),proof)

class ClockReuse(unittest.TestCase):
 def service(self,marker=True):
  c=Context(threading.Event(),threading.Event());c.wait=lambda _:c.checkpoint()
  a=S();s=S(context=c,check=Mock(),capture=Mock(return_value=GOOD),detector=S(find=Mock(return_value=True if marker else None)))
  return c,a,s
 def test_current_dungeon_reuses_two_minute_old_proved_countdown(self):
  c,a,s=self.service();a._owner_reward_dungeon_clock={'context':c,'at':100,'seconds':2000}
  with patch.object(timing.time,'monotonic',return_value=220),patch.object(timing,'read_remaining') as reader:
   result=timing.admit(a,c,None,service=s)
  self.assertTrue(result['allowed']);self.assertEqual(result['remaining'],1880);reader.assert_not_called()
 def test_reused_clock_still_blocks_ten_minutes(self):
  c,a,s=self.service();a._owner_reward_dungeon_clock={'context':c,'at':100,'seconds':700}
  with patch.object(timing.time,'monotonic',return_value=220):result=timing.admit(a,c,None,service=s)
  self.assertFalse(result['allowed']);self.assertEqual(result['remaining'],580)
 def test_clock_older_than_five_minutes_or_other_context_needs_new_read(self):
  for old in (True,False):
   c,a,s=self.service();a._owner_reward_dungeon_clock={'context':c if old else object(),'at':0 if old else 200,'seconds':2000}
   with patch.object(timing.time,'monotonic',return_value=310),patch.object(timing,'read_remaining',return_value=None) as reader:
    result=timing.admit(a,c,None,service=s)
   reader.assert_called_once();self.assertFalse(result['allowed'])
 def test_proved_field_clears_clock(self):
  c,a,s=self.service(False);a._owner_reward_dungeon_clock={'context':c,'at':100,'seconds':2000}
  from owner_schedule_priority import LOCAL
  previous=getattr(LOCAL,'combat',None);LOCAL.combat=None
  # The saved frame is a dungeon page, and the check now reads the map title; this case is a field.
  try:
   with patch('owner_dungeon_map.inside',return_value=False):result=timing.admit(a,c,None,service=s)
  finally:LOCAL.combat=previous
  self.assertTrue(result['allowed']);self.assertIsNone(a._owner_reward_dungeon_clock)

if __name__=='__main__':unittest.main()
