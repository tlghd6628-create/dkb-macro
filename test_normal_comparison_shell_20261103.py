import bootstrap,unittest
import numpy as np
from PIL import Image
from unittest.mock import patch
import owner_equipment_tooltip_candidate as t
class NormalShell(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261103T053109Z-6bec8c4c/screen.png').convert('RGB'))
 def test_actual_normal_worn_comparison_has_two_known_close_glyphs(self):
  self.assertTrue(t.comparison_shell(self.f))
 def test_translucent_background_only_can_change_but_button_glyph_cannot(self):
  f=self.f.copy();f[153,400]=[21,24,22]
  self.assertTrue(t._same_anchors(self.f,f))
  f=self.f.copy();f[350:376,526:598]=0
  self.assertFalse(t._same_anchors(self.f,f))
 def test_different_weapon_kind_is_not_allowed_to_equip(self):
  values=iter(['일반','희귀','부채','검','장착해제','장착'])
  with patch.object(t,'_ocr',side_effect=lambda *a,**k:next(values)):
   with self.assertRaises(t.Hold):t.compare_frame(self.f,None)
if __name__=='__main__':unittest.main()
