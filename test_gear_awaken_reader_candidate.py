"""Stored real frames only; no real game input or success simulation."""
import sys,unittest
from pathlib import Path
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_gear_awaken_reader_candidate import read_zero_to_one,paired_zero_to_one,read_observed_transition

class Tests(unittest.TestCase):
    def frame(self,name):
        path=Path(__file__).parent/'live_fixtures'/name
        return np.asarray(Image.open(path).convert('RGB').crop((1,31,898,510))).copy()
    def test_validated_base_transition_is_distinct_from_maximum(self):
        for kind in ('gear_awaken_hat','blessing_awaken_slot1'):
            first=self.frame(kind+'_1.jpg');second=self.frame(kind+'_2.jpg')
            self.assertIsNotNone(read_observed_transition(first));self.assertIsNotNone(read_observed_transition(second))
            self.assertEqual(paired_zero_to_one(first,second)['current'],0)
            self.assertEqual(read_zero_to_one(first)['next'],1)
    def test_other_views_and_changed_line_are_unknown(self):
        for name in ('blessing_rabbit_slot1_1.jpg','gear_awaken_list_20261101.jpg','gear_break_empty_20261101.jpg'):
            self.assertIsNone(read_zero_to_one(self.frame(name)),name)
        frame=self.frame('gear_awaken_hat_1.jpg');frame[130:142,354:431]=0
        self.assertIsNone(read_observed_transition(frame))
    def test_pair_requires_both_frames(self):
        first=self.frame('gear_awaken_hat_1.jpg')
        self.assertIsNone(paired_zero_to_one(first,np.zeros_like(first)))

if __name__=='__main__':unittest.main()
