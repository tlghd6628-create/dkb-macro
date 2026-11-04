from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
import numpy as np
from PIL import Image
from owner_equipment_boxes import paired_rare_weapon,plan,WEAPON,_weapon_grade_detector

class Tests(unittest.TestCase):
 def frame(self,name):
  frame=np.asarray(Image.open(T/'live_fixtures'/name).convert('RGB'))
  return frame.copy() if frame.shape[:2]==(479,897) else frame[31:510,1:898].copy()
 def test_actual_worn_rare_weapon_two_frames(self):
  a=self.frame('inventory_worn_native_1.png');b=self.frame('inventory_worn_native_2.png')
  self.assertTrue(paired_rare_weapon(A/'profiles/DKB',a,b))
  self.assertNotIn(WEAPON,plan({'무기':True},50,True)[0])
 def test_lossy_inspection_copy_cannot_replace_original_proof(self):
  a=self.frame('inventory_worn_1.jpg');b=self.frame('inventory_worn_2.jpg')
  self.assertIsNone(paired_rare_weapon(A/'profiles/DKB',a,b))
 def test_normal_weapon_is_not_excused_by_equipped_badge(self):
  self.assertIn(WEAPON,plan({'무기':True},30,False)[0])
  self.assertNotIn(WEAPON,plan({'무기':True},29,False)[0])
  self.assertNotIn(WEAPON,plan({'무기':True},30,None)[0])
 def test_private_crop_does_not_change_body_classifier(self):
  from roi_runtime import RoiDetector
  d=RoiDetector(A/'profiles/DKB',['체크_인벤토리_갑옷'])
  before=dict(d.entries['체크_인벤토리_갑옷'])
  _weapon_grade_detector(str(A/'profiles/DKB'))
  self.assertEqual(d.entries['체크_인벤토리_갑옷'],before)
 def test_menu_and_size_mismatch_never_proves_rare(self):
  f=np.zeros((479,897,3),dtype=np.uint8)
  self.assertIsNone(paired_rare_weapon(A/'profiles/DKB',f,f))

if __name__=='__main__':unittest.main()
