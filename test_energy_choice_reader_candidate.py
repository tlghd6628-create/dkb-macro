exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf8'))
import unittest
import numpy as np
from PIL import Image
import owner_energy_choice_reader_candidate as reader

class ReaderTests(unittest.TestCase):
 def setUp(self):
  self.frames=[np.asarray(Image.open(C/'live_fixtures'/f'energy_box_select_native_{n}.png').convert('RGB')) for n in (1,2)]
 def test_actual_two_frames_read_selection_quantity_but_not_receipt(self):
  result=reader.read_pair(*self.frames)
  self.assertEqual(result['selected'],'생명');self.assertEqual(result['rows'],list(reader.NAMES))
  self.assertEqual((result['quantity'],result['available_count']),(1,50));self.assertIs(result['receipt'],False)
 def test_changed_icon_title_or_second_frame_does_not_authorize(self):
  a,b=self.frames;changed=b.copy();changed[195:215,365:385]=a[231:251,365:385]
  self.assertIsNone(reader.read_pair(a,changed))
  changed=b.copy();changed[108:120,417:481]=0
  self.assertIsNone(reader.read_pair(a,changed))
  self.assertIsNone(reader.read_pair(a,a))
 def test_background_highlight_never_guesses_selection(self):
  a,b=self.frames;changed=b.copy();changed[152:155,363:535]=0
  self.assertIsNone(reader.read_pair(a,changed))
 def test_changed_count_never_reuses_known_glyph(self):
  a,b=self.frames;changed=b.copy();changed[321:332,436:468]=0
  self.assertIsNone(reader.read_pair(a,changed))
  self.assertIsNone(reader.read_pair(changed.copy(),changed.copy()))
 def test_actual_observed_counters_and_excluded_holdout_images(self):
  for n in (1,2,3,5,6,7,8,10):
   with self.subTest(n=n):
    a=np.asarray(Image.open(C/'live_fixtures'/f'energy_counter_{n}_of49_native_1.png').convert('RGB'))
    result=reader.read_pair(a.copy(),a.copy())
    self.assertEqual((result['quantity'],result['available_count'],result['selected']),(n,49,'여명'))
  for n in (1,2):
   a,b=[np.asarray(Image.open(C/'live_fixtures'/f'energy_counter_{n}_of49_native_{i}.png').convert('RGB')) for i in (1,2)]
   result=reader.read_pair(a,b);self.assertEqual((result['quantity'],result['available_count']),(n,49))
 def test_five_six_distinct_and_unknown_screenshot_cannot_authorize(self):
  import owner_energy_counter_glyph_candidate as counter
  a=counter.load_observed_atlas()
  self.assertEqual(a.classify(a.entries['5'][0].pixels),'5')
  self.assertEqual(a.classify(a.entries['6'][0].pixels),'6')
  self.assertGreater(counter._distance(a.entries['5'][0].pixels,a.entries['6'][0].pixels),.20)
  self.assertIsNone(reader.read_pair(self.frames[0],self.frames[0]))

if __name__=='__main__':unittest.main(verbosity=2)
