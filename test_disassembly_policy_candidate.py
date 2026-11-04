import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_disassembly_policy_candidate import dismantle_decision as d
class Cases(unittest.TestCase):
 def test_exact_equipped_match_is_protected(self):
  item={'name':'푸른 부채','slot':'무기','verified':True};self.assertEqual(d(item,[dict(item,name='푸른부채')],equipped_scan_complete=True),'protect')
 def test_unverified_names_or_incomplete_scan_hold(self):
  item={'name':'푸른 부채','slot':'무기','verified':True};self.assertEqual(d(item,[],equipped_scan_complete=False),'hold');self.assertEqual(d(item,[{'name':None,'slot':'무기','verified':True}],equipped_scan_complete=True),'hold')
 def test_different_item_still_held_without_proven_native_exclusion(self):
  item={'name':'푸른 부채','slot':'무기','verified':True};equipped=[{'name':'붉은 부채','slot':'무기','verified':True}];self.assertEqual(d(item,equipped,equipped_scan_complete=True),'hold')
 def test_empty_equipped_list_does_not_authorize_dismantling(self):
  item={'name':'푸른 부채','slot':'무기','verified':True};self.assertEqual(d(item,[],equipped_scan_complete=True),'hold')
if __name__=='__main__':unittest.main()
