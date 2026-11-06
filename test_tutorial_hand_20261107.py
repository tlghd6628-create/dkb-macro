"""The tutorial hand needs the glove and its hint arrow. Synthetic pixels; real frames checked by hand (pc1 11-07)."""
from pathlib import Path
from types import SimpleNamespace as NS
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_tutorial_hand as h


def scene(arrow=True):
    a=np.zeros((768,1366,3),np.uint8)
    a[500:540,1200:1230]=250;a[510:530,1212:1230]=0     # a glove-sized white piece, about 70% filled
    if arrow:a[508:532,1100:1116]=230;a[512:528,1100:1108]=0   # an arrow-sized piece, about 65% filled
    return a


class Hand(unittest.TestCase):
    def test_glove_with_its_arrow(self):self.assertEqual(h.hand(scene()),(1204,502))
    def test_white_piece_without_an_arrow_is_not_a_hand(self):self.assertIsNone(h.hand(scene(False)))
    def test_follow_clicks_then_stops(self):
        shots=[NS(hi=scene()),NS(hi=scene(False)),NS(hi=scene(False)),NS(hi=scene(False))];clicks=[]
        n=h.follow(NS(capture=lambda:shots.pop(0),click_hit=lambda hit:clicks.append(hit[:2])),NS(checkpoint=lambda:None,wait=lambda s:None))
        self.assertEqual(n,1);self.assertEqual(len(clicks),2)


if __name__=='__main__':unittest.main()
