"""Ratio boxes show whole numbers. Plain values only; never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,unittest
from owner_starter_choice_candidate import whole_percent,percent_units,equal_display,ENERGIES


class Whole(unittest.TestCase):
 def test_a_third_each_still_totals_100(self):
  shown=whole_percent({'a':'33.33','b':'33.33','c':'33.34','d':'0.00'})
  self.assertEqual(sorted(shown.values()),['0','33','33','34']);self.assertEqual(shown['d'],'0')
 def test_whole_values_stay(self):
  self.assertEqual(whole_percent({'a':'50.00','b':'50.00'}),{'a':'50','b':'50'})
 def test_every_equal_split_is_accepted_when_saved(self):
  for size in (1,2,3,4):
   shown=whole_percent(equal_display(list(ENERGIES[:size])))
   self.assertTrue(all('.' not in value for value in shown.values()))
   self.assertEqual(sum(percent_units({n:shown[n] for n in ENERGIES}).values()),10000)


if __name__=='__main__':unittest.main()
