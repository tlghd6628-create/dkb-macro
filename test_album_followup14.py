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

if __name__=='__main__':unittest.main()
