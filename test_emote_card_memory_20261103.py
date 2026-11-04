"""Remembered card slots are hints; fresh card identity still authorizes input.
Saved frames and mocked input only; no game operation is exercised here."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
from pathlib import Path
from PIL import Image
import numpy as np
import bootstrap
import owner_emote_dispatch as d

P=Path(__file__).parent/'live_fixtures'
def frame(name):return np.asarray(Image.open(P/name).convert('RGB')).copy()

class CardMemory(unittest.TestCase):
 def test_three_shared_positions_avoid_search_on_two_backgrounds(self):
  for name in ('emote-three-cards-1.png','emote-three-cards-2.png'):
   f=frame(name);locator=d.CardLocator(S(),None)
   with patch.object(d,'card_point',side_effect=AssertionError('unnecessary full-panel search')):
    for target in ('졸기','뽐내기','황당'):
     point=d.CARD_POSITIONS[target]
     self.assertEqual(locator.find(f,target),point)
     self.assertTrue(locator.matches(f,target,point))
 def test_wrong_emote_or_changed_page_does_not_authorize_saved_point(self):
  f=frame('emote-three-cards-1.png');locator=d.CardLocator(S(),None)
  for target in ('졸기','뽐내기','황당'):
   for other in ('졸기','뽐내기','황당'):
    if target!=other:self.assertFalse(locator.matches(f,target,d.CARD_POSITIONS[other]))
  for name in ('emote-panel-top.png','emote-panel-bottom.png'):
   for target in ('졸기','뽐내기','황당'):
    self.assertFalse(locator.matches(frame(name),target,d.CARD_POSITIONS[target]),(name,target))
 def test_native_clipped_angry_retains_original_proof(self):
  detector=d.chat_detector(str(bootstrap.A));locator=d.CardLocator(S(),detector)
  self.assertEqual(locator.find(frame('emote-panel-top.png'),'화남'),(281,460))
  self.assertFalse(locator.matches(frame('emote-panel-bottom.png'),'화남',(281,460)))
 def test_moved_card_is_relocated_then_checked_at_its_new_slot(self):
  ui=S();locator=d.CardLocator(ui,None);f=frame('emote-three-cards-1.png')
  # Synthetic scroll, not another real observation. The face/label and panel
  # title remain independent: only the card viewport is shifted upward.
  shifted=f.copy();shifted[322:447,250:429]=f[354:479,250:429];shifted[447:479,250:429]=0
  point=d.card_hit(shifted,'졸기');self.assertEqual(point,(279,408))
  with patch.object(d,'card_point',wraps=d.card_point) as search:
   self.assertEqual(locator.find(shifted,'졸기'),point);self.assertEqual(search.call_count,1)
  self.assertEqual(ui._owner_emote_card_positions['졸기'],point)
  with patch.object(d,'card_point',side_effect=AssertionError('cached hint should be locally proven')):
   self.assertEqual(d.CardLocator(ui,None).find(shifted,'졸기'),point)
  # Moving back invalidates the old coordinates. Shared observed slot works.
  self.assertEqual(locator.find(f,'졸기'),(279,440))
 def test_no_frame_reuse_or_invalid_coordinate_acceptance(self):
  f=frame('emote-three-cards-1.png');locator=d.CardLocator(S(),None)
  self.assertTrue(locator.matches(f,'황당',(397,440)))
  f[420:479,370:429]=0
  self.assertFalse(locator.matches(f,'황당',(397,440)))
  for point in (None,(-1,440),(397,479),(397.0,440),('397',440)):
   self.assertFalse(d.card_at(f,'황당',point))
  self.assertFalse(d.card_at(np.zeros((720,1280,3),dtype='uint8'),'황당',(397,440)))

if __name__=='__main__':unittest.main()
