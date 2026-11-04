import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_story_threshold_candidate import *
class Cases(unittest.TestCase):
 def test_explicit_numeric(self):self.assertEqual(read_recommended([{'text':'135,000','score':.99}]),135000)
 def test_ambiguous_or_missing_values_are_unknown(self):
  self.assertIsNone(read_recommended([{'text':'적합','score':.99}]));self.assertIsNone(read_recommended([{'text':'51000','score':.97},{'text':'61000','score':.98}]));self.assertIsNone(read_recommended([{'text':'51000','score':.9}]))
 def test_transition_only_on_evidence(self):
  e={'new':{'required':120000,'power_proven':True},'unknown':{'required':120000},'done':{'required':120000,'power_proven':True,'completed':True}}
  self.assertEqual(newly_reachable(e,119000,120000),['new']);self.assertEqual(newly_reachable(e,None,130000),[])
 def test_incomplete_catalog_rechecks_on_growth_only(self):
  self.assertTrue(needs_recheck({},100000,100001,False));self.assertFalse(needs_recheck({},100000,100000,False));self.assertFalse(needs_recheck({},None,100001,False))
 def test_known_threshold_and_unknown_case(self):
  e={'a':{'required':120000,'power_proven':True},'b':{'completed':True}}
  self.assertFalse(needs_recheck(e,110000,119999,True));self.assertTrue(needs_recheck(e,119999,120000,True))
  e['x']={};self.assertTrue(needs_recheck(e,110000,110001,True))
if __name__=='__main__':unittest.main()
