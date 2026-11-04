"""Real 10:14 missed sleep frames and negative words; no live input."""
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
import bootstrap
import owner_emote_dispatch as d
from owner_quest_emote_candidate import target_zone,panel

class Marquee(unittest.TestCase):
 def frame(self,name):return np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261103'/name/'screen.png').convert('RGB'))
 def test_actual_sleep_word_visible_at_arrival_is_read(self):
  f=self.frame('20261103T101403-b43259e7')
  self.assertTrue(target_zone(f));self.assertTrue(panel(f))
  self.assertEqual(d.known_goal(f),('졸기',146))
 def test_same_sleep_word_on_the_return_frame_is_read(self):
  self.assertEqual(d.known_goal(self.frame('20261103T101439-edabce94')),('졸기',146))
 def test_scrolled_away_requirements_prove_nothing(self):
  for name in ('20261103T101418-b3492784','20261103T101433-8ebc23a8'):
   self.assertIsNone(d.known_goal(self.frame(name)),name)
 def test_old_sleep_reference_keeps_its_own_target(self):
  f=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/emote-sleep-goal.png').convert('RGB'))
  self.assertEqual(d.known_goal(f)[0],'졸기')
 def test_old_surprise_reference_keeps_its_own_target(self):
  f=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/emote-surprise-goal.png').convert('RGB'))
  self.assertEqual(d.known_goal(f)[0],'황당')

if __name__=='__main__':unittest.main()
