import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_learned_skills_candidate import LearnedSkills,remember_verified_owned
class Tests(unittest.TestCase):
 def test_survives_restart_but_not_shared_between_characters(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
   LearnedSkills(root,'a').observed('생명의 흐름',verified=True)
   self.assertTrue(LearnedSkills(root,'a').known('생명의 흐름'));self.assertFalse(LearnedSkills(root,'b').known('생명의 흐름'))
 def test_weak_or_unknown_evidence_never_saved(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
   with self.assertRaises(ValueError):LearnedSkills(root,'a').observed('방패 밀기',verified=False)
   self.assertFalse(LearnedSkills(root,'a').path.exists())
 def test_corrupt_data_is_never_overwritten(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
   path=Path(root)/'settings/owner-learned-skills.json';path.parent.mkdir();path.write_text('invalid')
   with self.assertRaises(ValueError):LearnedSkills(root,'a')
   self.assertEqual(path.read_text(),'invalid')
 def test_existing_owned_scan_records_only_observed_for_current_character(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
   class Ledger:pass
   ledger=Ledger();ledger.character='a';ledger.path=Path(root)/'settings/owner-skill-goal.json'
   remember_verified_owned(ledger,{84,68})
   first=LearnedSkills(root,'a');second=LearnedSkills(root,'b')
   self.assertTrue(first.known('생명의 흐름'));self.assertTrue(first.known('방패 밀기'))
   self.assertFalse(first.known('공간 결계'));self.assertFalse(second.known('생명의 흐름'))
   remember_verified_owned(ledger,{89});self.assertTrue(LearnedSkills(root,'a').known('공간 결계'))
 def test_unknown_owned_never_writes(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
   class Ledger:pass
   ledger=Ledger();ledger.character='a';ledger.path=Path(root)/'settings/owner-skill-goal.json'
   with self.assertRaises(ValueError):remember_verified_owned(ledger,None)
   self.assertFalse((Path(root)/'settings/owner-learned-skills.json').exists())
if __name__=='__main__':unittest.main()
