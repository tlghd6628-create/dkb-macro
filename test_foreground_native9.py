import bootstrap
import unittest,numpy as np,json
from PIL import Image
from roi_runtime import RoiDetector
from owner_native_contracts import menu_candidates,menu_regions,find_menu_target
from owner_blessing_native_candidate import same_white_text

class Foreground(unittest.TestCase):
 def frames(self):
  root=bootstrap.A/'logs/feature-checks/screens'
  return [np.asarray(Image.open(root/n).convert('RGB')).copy() for n in ('20261102_203849_887364-blessing_growth.png','20261102_205433_430152-blessing_growth.png')]
 def test_actual_same_blessing_text_survives_the_animated_gold_rim(self):
  a,b=self.frames()
  self.assertTrue(same_white_text(a,b,(327,65,133,18)))
  self.assertTrue(same_white_text(a,b,(317,123,70,24)))
 def test_changed_current_digit_still_invalidates_the_proof(self):
  import cv2
  a,b=self.frames();box=(317,123,70,24);x,y,w,h=box
  hsv=cv2.cvtColor(b[y:y+h,x:x+w],cv2.COLOR_RGB2HSV)
  py,px=np.argwhere((hsv[:,:,1]<60)&(hsv[:,:,2]>170))[0]
  b[y+py,x+px]=0
  self.assertFalse(same_white_text(a,b,box))
 def test_native_guide_alternates_do_not_cross_into_another_menu(self):
  root=bootstrap.A/'logs/feature-checks/screens'
  f=np.asarray(Image.open(root/'20261102_205449_570690-guide.png').convert('RGB'))
  names=menu_candidates('버튼_길라잡이');d=RoiDetector(bootstrap.A/'profiles/DKB',list(names)+list(menu_regions()))
  self.assertIsNone(d.find(names[0],f,threshold=.95))
  self.assertEqual(names,('버튼_길라잡이','버튼_길라잡이2'))
  # Neither guide icon is proven on this particular field screenshot.
  # This remains an actual reported blocker, never a fabricated successful hit.
  self.assertIsNone(d.find(names[1],f,threshold=.95))
  self.assertIsNotNone(find_menu_target(d,names[0],f))
  self.assertNotIn('버튼_이벤트2',names)

if __name__=='__main__':unittest.main()
