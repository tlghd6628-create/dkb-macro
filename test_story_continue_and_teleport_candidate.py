import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock
from PIL import Image
import numpy as np
import bootstrap
import owner_movement as movement
import owner_mission_controller as controller

P=Path(__file__).parent/'live_fixtures'
class Tests(unittest.TestCase):
 def tearDown(self):
  controller.LOCAL.active=None;controller.LOCAL.stalled=None
 def test_progress_after_old_six_second_deadline_keeps_native_runner(self):
  controller.LOCAL.active=('adapter','context','chapter',0);controller.LOCAL.stalled=None
  handler=Mock(return_value='native_step');runner=object()
  self.assertEqual(controller.continue_progress(handler,runner,'spec','match','frame'),'native_step')
  handler.assert_called_once_with(runner,'spec','match','frame')
 def test_confirmed_stall_still_releases_chapter(self):
  controller.LOCAL.active=('adapter','context','chapter',0);controller.LOCAL.stalled='chapter';handler=Mock()
  with self.assertRaises(controller.QuestBoundary):controller.continue_progress(handler,object())
  handler.assert_not_called()
 def test_stop_and_native_failures_are_not_swallowed(self):
  controller.LOCAL.active=('adapter','context','chapter',0);controller.LOCAL.stalled=None
  for error in (InterruptedError('stop'),RuntimeError('native failure')):
   with self.assertRaises(type(error)):controller.continue_progress(Mock(side_effect=error),object())
 def test_actual_changed_background_two_fresh_button_proofs(self):
  for name in ('moving_415_native.png','moving_409_native.png'):
   f=np.asarray(Image.open(P/name).convert('RGB'));l,t,r,b=movement.moving_bar(f)[2];box=(l+88,t-7,37,39)
   self.assertTrue(movement.moving_field(f));self.assertIsNotNone(movement.moving_b_hit(f,box))
   if name=='moving_415_native.png':self.assertIsNone(movement.find(f,'moving-b-key',box,.92))
 def test_damaged_foreground_does_not_authorize(self):
  f=np.asarray(Image.open(P/'moving_415_native.png').convert('RGB')).copy();l,t,r,b=movement.moving_bar(f)[2];box=(l+88,t-7,37,39)
  hit=movement.moving_b_hit(f,box);x,y=hit[2][:2];f[y:y+25,x:x+25]=0
  self.assertIsNone(movement.moving_b_hit(f,box))
 def test_actual_far_field_uses_two_keys_only_after_known_modal(self):
  field=np.asarray(Image.open(P/'moving_415_native.png').convert('RGB'))
  modal=np.asarray(Image.open(bootstrap.O/'current_checks/live/b-move-dialog.png').convert('RGB'))
  class UI:
   def __init__(self):self.current=field;self.keys=[];self.context=S(wait=lambda n:None)
   def frame(self):return self.current.copy()
   def rows(self,*a,**kw):return [{'text':'415m','score':.999}]
   def key(self,key):self.keys.append(key);self.current=modal if len(self.keys)==1 else field
   def wait(self,predicate,seconds):
    if not predicate(self.current):raise AssertionError('unknown transition')
  ui=UI();self.assertTrue(movement.travel(ui));self.assertEqual(ui.keys,[0x42,0x42])

if __name__=='__main__':unittest.main()
