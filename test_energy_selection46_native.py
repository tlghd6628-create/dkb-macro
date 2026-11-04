"""Two independently captured native PNGs; offline reader checks, no inputs."""
from pathlib import Path
import unittest
import bootstrap
from PIL import Image
import numpy as np
from owner_energy_choice_reader_candidate import read_pair,read_open_pair,layout_variant

SOURCES=('20261102_133851_c1d8f6b8.png','20261102_133914_c293e976.png')
class Tests(unittest.TestCase):
 def setUp(self):
  self.a,self.b=[np.asarray(Image.open(bootstrap.A/'logs/manual-captures'/n).convert('RGB')).copy() for n in SOURCES]
 def test_independent_native_pair_has_exact_life_one_of46_selection(self):
  self.assertIsNot(self.a,self.b);self.assertFalse(np.shares_memory(self.a,self.b))
  result=read_pair(self.a,self.b)
  self.assertEqual((result['selected'],result['quantity'],result['available_count']),('생명',1,46))
  self.assertFalse(result['receipt']);self.assertEqual([layout_variant(f) for f in (self.a,self.b)],[0,0])
 def test_same_capture_is_not_a_pair(self):
  self.assertIsNone(read_pair(self.a,self.a))
 def test_missing_energy_option_never_authorizes_selection(self):
  self.b[195:215,365:385]=0
  self.assertIsNone(read_pair(self.a,self.b))
 def test_unknown_counter_never_authorizes_selection(self):
  self.b[319:334,436:467]=0
  self.assertIsNone(read_pair(self.a,self.b))
 def test_changed_selected_border_does_not_reuse_old_target(self):
  self.b[152:155,363:535]=0
  self.assertIsNone(read_open_pair(self.a,self.b))

if __name__=='__main__':unittest.main()
