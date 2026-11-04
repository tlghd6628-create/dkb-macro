exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
from owner_equipment_boxes import plan,WEAPON
class Cases(unittest.TestCase):
 def test_rare_weapon_waits_until_level30(self):
  for level in (None,1,29):self.assertNotIn(WEAPON,plan({'무기':False},level)[0])
  self.assertIn(WEAPON,plan({'무기':False},30)[0])
 def test_worn_or_unknown_never_reopens_weapon_box(self):
  for worn in (None,True):self.assertNotIn(WEAPON,plan({'무기':worn},50)[0])
if __name__=='__main__':unittest.main()
