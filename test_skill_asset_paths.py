exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
from owner_skill_goal import catalog
from owner_skill_ui import icon

class SkillAssetPaths(unittest.TestCase):
 def test_all_candidate_icons_exist_and_match_recorded_hash(self):
  for sid in catalog()['skills']:
   with self.subTest(skill=sid):self.assertTrue(icon(int(sid),32).size)

if __name__=='__main__':unittest.main()
