"""A click's place is asked for twice by the input guard; both answers must agree. Fake layouts; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from unittest.mock import patch
import owner_hd as hd


class Steady(unittest.TestCase):
    def setUp(self):hd._steady.clear()
    def test_same_place_while_the_map_changes(self):
        answers=iter([(100,200),(134,200)])
        with patch.object(hd,'to_real_point',side_effect=lambda x,y,l:next(answers)),patch.object(hd,'_click_layout',return_value=None):
            first=hd.steady_point((509,318));second=hd.steady_point((509,318))
        self.assertEqual(first,second)
    def test_fresh_after_the_window(self):
        answers=iter([(100,200),(134,200)]);clock=[1000.]
        with patch.object(hd,'to_real_point',side_effect=lambda x,y,l:next(answers)),patch.object(hd,'_click_layout',return_value=None),\
             patch.object(hd.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertEqual(hd.steady_point((509,318)),(100,200))
            clock[0]+=hd.STEADY+.1
            self.assertEqual(hd.steady_point((509,318)),(134,200))
    def test_other_places_are_their_own(self):
        with patch.object(hd,'to_real_point',side_effect=lambda x,y,l:(x*2,y*2)),patch.object(hd,'_click_layout',return_value=None):
            self.assertEqual(hd.steady_point((1,2)),(2,4));self.assertEqual(hd.steady_point((3,4)),(6,8))


if __name__=='__main__':unittest.main()
