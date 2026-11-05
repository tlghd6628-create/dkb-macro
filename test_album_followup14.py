"""Saved image/fake-input checks only. Never attaches to the game."""
import bootstrap
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock
import numpy as np
from PIL import Image
import owner_album_disabled as a

class AlbumTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'followup_20261103');self.addCleanup(self.temp.cleanup)
  self.adapter=S(project=S(root=Path(self.temp.name)))
  self.hit=(787,420,(774,414,800,426))
  self.frame=np.zeros((479,897,3),dtype=np.uint8)
  detector=S(find=lambda name,frame,**kw:self.hit if name==a.COMPLETE else (71,19,(58,12,85,27)))
  self.service=S(adapter=self.adapter,detector=detector,check=lambda:None,
   context=S(wait=lambda _:None,checkpoint=lambda:None),capture=lambda:self.frame.copy())
  a.LOCAL.scope={'adapter':self.adapter,'identity':'test-character','mode':'조각 등록만','sent':False}
  self.addCleanup(lambda:setattr(a.LOCAL,'scope',None))
 def test_register_only_never_clicks_complete(self):
  click=Mock()
  with self.assertRaises(a.AlbumBoundary):a.guarded_click(click,self.service,self.hit)
  click.assert_not_called()
  self.assertFalse((Path(self.temp.name)/'settings/owner-album-inputs.json').exists())
 def test_completion_opt_in_persists_before_click_and_no_repeat(self):
  a.LOCAL.scope['mode']='완성'
  path=Path(self.temp.name)/'settings/owner-album-inputs.json'
  click=Mock(side_effect=lambda *args:self.assertIn('sent_unconfirmed',path.read_text()))
  a.guarded_click(click,self.service,self.hit)
  self.assertEqual(click.call_count,1)
  with self.assertRaises(a.AlbumBoundary):a.guarded_click(click,self.service,self.hit)
  self.assertEqual(click.call_count,1)
 def test_changed_title_no_input(self):
  a.LOCAL.scope['mode']='완성'
  changed=self.frame.copy();changed[70,230]=255
  self.service.capture=Mock(side_effect=[self.frame,changed])
  click=Mock()
  with self.assertRaises(a.AlbumBoundary):a.guarded_click(click,self.service,self.hit)
  click.assert_not_called()
 def test_native_button_cannot_bypass_register_only(self):
  original=Mock()
  with self.assertRaises(a.AlbumBoundary):a.guarded_button(original,self.service,a.COMPLETE)
  original.assert_not_called()
 def test_original_completion_template_matches_user_screenshot(self):
  from tools.roi_runtime import RoiDetector
  root=Path('C:/Users/홍이/Downloads/도깨비의 세계/vendor/DKB_Auto')
  frame=np.array(Image.open(Path(__file__).parent/'reference_evidence/album_completion/completion_with_currency_20261102.png').convert('RGB'))[31:510,1:898]
  detector=RoiDetector(root/'profiles/DKB',(a.CHECK,a.COMPLETE))
  self.assertIsNotNone(a.completion_hit(S(detector=detector),frame))

class LooksTests(unittest.TestCase):
 """Saved shapes only: a fake log line and a fake screen, not a real album visit."""
 def look(self,watch,text='화첩 추가·동물탭 빨점 없음 · 다른 빨점 재확인'):
  watch.emit(a.logging.LogRecord('x',20,'x',1,text,(),None))
 def test_clear_screen_ends_at_the_first_look(self):
  with self.assertRaises(a.AlbumNothingLeft):self.look(a.NoDots(lambda:True))
 def test_dots_on_screen_leave_it_to_the_count(self):
  watch=a.NoDots(lambda:False);self.look(watch)
  with self.assertRaises(a.AlbumNothingLeft):self.look(watch)
 def test_other_album_lines_ask_nothing(self):
  asked=Mock(return_value=True);self.look(a.NoDots(asked),'화첩 보상 시작');asked.assert_not_called()
 def screen(self,found=True):
  frame=np.zeros((479,897,3),dtype=np.uint8).view(type('F',(np.ndarray,),{}))
  frame.hi=np.zeros((768,1366,3),dtype=np.uint8);frame.layout=None
  return S(capture=lambda:frame,detector=S(find=lambda *_,**__:(1,1) if found else None))
 def test_real_pixels_decide(self):
  service=self.screen();self.assertTrue(a.screen_clear(service))
  import cv2
  cv2.circle(service.capture().hi,(700,300),5,(220,30,30),-1);self.assertFalse(a.screen_clear(service))
 def test_not_the_album_or_no_real_pixels_says_nothing(self):
  self.assertFalse(a.screen_clear(self.screen(False)))
  self.assertFalse(a.screen_clear(S(capture=lambda:np.zeros((479,897,3),dtype=np.uint8),detector=S(find=lambda *_,**__:(1,1)))))
 def test_a_failed_read_says_nothing(self):
  self.assertFalse(a.screen_clear(S(capture=Mock(side_effect=RuntimeError('no')),detector=None)))

if __name__=='__main__':unittest.main()
