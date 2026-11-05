"""Plain menus named by title words, on frames saved from the game. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
from types import SimpleNamespace as S
import numpy as np
from PIL import Image
from owner_start_menu import plain_menu

L=HERE/'image_scope_20261104'


class Frames(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from roi_runtime import RoiDetector
  cls.service=S(detector=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_나가기']),adapter=S(project=S(root=bootstrap.A)))
 def read(self,name):
  path=L/(name+'.png')
  if not path.exists():self.skipTest('saved frame not on this PC')
  return plain_menu(self.service,np.asarray(Image.open(path).convert('RGB')))
 def test_mail_is_a_plain_menu(self):self.assertEqual(self.read('f1/tower1'),'우편함')
 def test_boss_menu_is_a_plain_menu(self):self.assertEqual(self.read('live/q4'),'보스토벌')
 def test_shop_is_a_plain_menu(self):self.assertIn(self.read('live/look_shop'),('잡화상점',))
 def test_field_and_dungeon_are_not(self):
  self.assertIsNone(self.read('f1/shop_t3'));self.assertIsNone(self.read('f1/d_05'))
 def test_a_menu_not_named_is_left_alone(self):self.assertIsNone(self.read('f1/pre8'))


if __name__=='__main__':unittest.main()
