"""Paused AUTO: real templates on frames saved from the game, and a fake click. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock
import numpy as np
from PIL import Image
from owner_sleep_auto import wrap,paused_hit,PAUSED,RUNNING,OFF,SLEEP,FIGHTING

LIVE=HERE/'image_scope_20261104/live'


class Frames(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from roi_runtime import RoiDetector
  cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',[PAUSED,RUNNING,OFF,SLEEP,FIGHTING])
 def load(self,name):
  path=LIVE/(name+'.png')
  if not path.exists():self.skipTest('saved frame not on this PC')
  return np.asarray(Image.open(path).convert('RGB'))
 def test_only_the_paused_frame_is_paused(self):
  self.assertTrue(paused_hit(self.detector,self.load('a0')))
  self.assertFalse(paused_hit(self.detector,self.load('a3')),'white AUTO')
  self.assertFalse(paused_hit(self.detector,self.load('b1c')),'gold AUTO')


class Flow(unittest.TestCase):
 HIT=(797,447,(780,430,815,465))
 def setUp(self):
  self.original=Mock(return_value=True);self.context=S(wait=lambda *_:None,checkpoint=lambda:None)
 def run_with(self,paused,**options):
  detector=Mock();detector.find=lambda name,frame,threshold=0:self.HIT if name==PAUSED and paused else None
  self.actions=S(capture=lambda:'frame',click_hit=Mock())
  return wrap(self.original,lambda:detector)(self.actions,self.context,None,**options)
 def test_paused_is_pressed_once_then_the_native_check_runs_on_a_new_frame(self):
  self.assertTrue(self.run_with(True,frame='old',post_click_wait=1))
  self.actions.click_hit.assert_called_once_with(self.HIT)
  self.original.assert_called_once_with(self.actions,self.context,None,post_click_wait=1)
 def test_other_states_go_straight_to_the_native_check(self):
  self.assertTrue(self.run_with(False));self.actions.click_hit.assert_not_called();self.original.assert_called_once()
 def test_actions_without_click_hit_use_their_own_click(self):
  detector=Mock();detector.find=lambda name,frame,threshold=0:self.HIT if name==PAUSED else None
  actions=S(capture=lambda:'frame',click=Mock())
  wrap(self.original,lambda:detector)(actions,self.context,None)
  actions.click.assert_called_once_with(PAUSED,self.HIT,threshold=.90,pre_wait=.1,revalidate_template=False)
 def test_a_failed_press_does_not_stop_the_run(self):
  detector=Mock();detector.find=lambda name,frame,threshold=0:self.HIT if name==PAUSED else None
  actions=S(capture=lambda:'frame',click=Mock(side_effect=RuntimeError('절전 버튼 위치 변경')))
  self.assertTrue(wrap(self.original,lambda:detector)(actions,self.context,None))
  self.original.assert_called_once()


if __name__=='__main__':unittest.main()
