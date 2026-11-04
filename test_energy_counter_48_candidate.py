import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from owner_energy_counter_glyph_candidate import load_observed_atlas,read_pair
from owner_energy_choice_reader_candidate import read_open_pair,read_pair as strict_pair
P=Path(__file__).parent/'live_fixtures'
def image(name):return np.asarray(Image.open(P/name).convert('RGB'))
class Tests(unittest.TestCase):
 def test_held_out_actual_denominator_eight(self):
  a=image('energy_counter_1_of48_holdout1.png');b=image('energy_counter_1_of48_holdout2.png');self.assertEqual(read_pair(a,b,load_observed_atlas()),(1,48))
  self.assertEqual(read_open_pair(a,b)['available_count'],48);self.assertIsNone(strict_pair(a,b))
 def test_missing_or_changed_eight_never_counts_48(self):
  a=image('energy_counter_1_of48_holdout1.png');b=image('energy_counter_1_of48_holdout2.png').copy();b[319:334,453:458]=0
  self.assertNotEqual(read_pair(a,b,load_observed_atlas()),(1,48));self.assertIsNone(read_open_pair(a,b))
if __name__=='__main__':unittest.main()
