import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import owner_energy_counter_glyph_candidate as g
from owner_energy_choice_reader_candidate import read_open_pair

P=Path(__file__).parent/'live_fixtures'
def image(s):return np.asarray(Image.open(P/('energy_counter_1_of47_'+s+'.png')).convert('RGB'))

class Tests(unittest.TestCase):
 def test_independent_native_holdouts(self):
  a,b=image('holdout1'),image('holdout2')
  self.assertEqual(g.read_pair(a,b,g.load_observed_atlas()),(1,47))
  self.assertEqual(read_open_pair(a,b)['available_count'],47)
 def test_missing_last_digit_cannot_authorize(self):
  a,b=image('holdout1'),image('holdout2').copy();b[319:334,453:458]=0
  self.assertIsNone(g.read_pair(a,b,g.load_observed_atlas()))
  self.assertIsNone(read_open_pair(a,b))
 def test_transient_slash_still_holds_without_lowering_confidence(self):
  self.assertIsNone(g.read_pair(image('transient'),image('holdout2'),g.load_observed_atlas()))
 def test_denominator_sample_not_eligible_for_numerator(self):
  atlas=g.load_observed_atlas();row=next(e for e in atlas.entries['7'] if e.region=='denominator')
  self.assertEqual(atlas.classify(row.pixels,denominator=True),'7')
  self.assertNotEqual(atlas.classify(row.pixels,denominator=False),'7')

if __name__=='__main__':unittest.main()
