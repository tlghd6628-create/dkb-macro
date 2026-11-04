"""Saved frames/fake input only. Manual live success is recorded separately."""
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
from PIL import Image
import numpy as np
import bootstrap
import owner_emote_dispatch as d
from owner_emote_requirements import EmoteQuestMismatch
from biol_base.session import Cancelled
C=Path(__file__).resolve().parent
def frame(n):return np.asarray(Image.open(C/'live_fixtures'/n).convert('RGB')).copy()

class Proud(unittest.TestCase):
 def test_actual_cards_use_the_original_proud_only_vertical_centre(self):
  for name in ('emote-three-cards-1.png','emote-three-cards-2.png'):
   f=frame(name);point=d.card_hit(f,'뽐내기')
   self.assertEqual(point,(338,449));self.assertTrue(d.card_at(f,'뽐내기',point))
   self.assertFalse(d.card_at(f,'뽐내기',(338,440)))
   self.assertEqual(d.proud_face_state(f,point),'enabled')
   self.assertEqual(d.card_hit(f,'졸기'),(279,440));self.assertEqual(d.card_hit(f,'황당'),(397,440))
 def test_proud_word_is_found_on_another_tracker_row(self):
  f=np.zeros((479,897,3),dtype='uint8');word=d.asset('target');h,w=word.shape[:2]
  f[209:209+h,770:770+w]=word
  self.assertEqual(d.known_goal(f),('뽐내기',209))
  f[209:209+h,770:770+w]=0;self.assertIsNone(d.known_goal(f))
 def test_other_known_emotes_do_not_become_proud(self):
  for name,wanted in (('emote-sleep-goal.png','졸기'),('emote-surprise-goal.png','황당'),('emote-angry-goal-0854-24.png','화남')):
   self.assertEqual(d.known_goal(frame(name))[0],wanted)
 def test_known_proud_quest_cannot_be_charged_to_another_root(self):
  f=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261101T205743Z-1bafafd4/screen.png').convert('RGB'))
  self.assertTrue(d.objective(f))
  with self.assertRaises(EmoteQuestMismatch):
   d.require_same_quest(None,{'title':'[외전] 분수를 모르는 자를'},None,f,f,145,'뽐내기')
  for title in ('[외전] 산길의 호환','[외전] 1산길의 호환','[외전] ㅣ산길의 호환'):
   ui=S(context=S(wait=lambda n:None),rows=lambda *a,**kw:[])
   d.require_same_quest(ui,{'title':title},S(packaged_images=lambda:[]),f,f,145,'뽐내기')
 def test_wrong_card_unknown_resolution_and_hidden_panel_cannot_authorize_enabled(self):
  f=frame('emote-three-cards-1.png')
  for point in ((279,449),(397,449),(338,440)):
   self.assertIsNone(d.proud_face_state(f,point))
  self.assertIsNone(d.proud_face_state(np.zeros((720,1280,3),dtype='uint8'),(338,449)))
 def test_two_disabled_observations_acknowledge_only_ui_response(self):
  calls=[];ui=S(context=S(wait=lambda n:calls.append(n),checkpoint=lambda:None),frame=lambda:object())
  with patch.object(d,'proud_face_state',side_effect=['enabled','disabled','disabled']),patch.object(d,'panel',return_value=True):
   self.assertEqual(d.observe_proud_response(ui,(338,449)),'card_disabled')
  self.assertEqual(len(calls),3)
 def test_no_response_is_bounded_and_does_not_click_or_assert_completion(self):
  calls=[];ui=S(context=S(wait=lambda n:calls.append(n),checkpoint=lambda:None),frame=lambda:object())
  with patch.object(d,'proud_face_state',return_value=None),patch.object(d,'panel',return_value=True):
   self.assertEqual(d.observe_proud_response(ui,(338,449)),'unverified')
  self.assertEqual(len(calls),10);self.assertAlmostEqual(sum(calls),1.2)
 def test_cancellation_propagates_before_cleanup(self):
  ui=S(context=S(wait=lambda n:None,checkpoint=lambda:(_ for _ in ()).throw(Cancelled())),frame=lambda:None)
  with self.assertRaises(Cancelled):d.observe_proud_response(ui,(338,449))

if __name__=='__main__':unittest.main()
