"""A target bar that never changes is not a fight. Fake frames; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import numpy as np
from types import SimpleNamespace as S
import owner_mission_controller as mc

def frame(level):
    a=np.zeros((768,1366,3),dtype=np.uint8);a[73:80,620:620+level]=(134,23,23);return S(hi=a)

class StillBar(unittest.TestCase):
    def test_unchanged_bar_stops_counting_as_a_fight_after_20_s(self):
        idle={};f=frame(140)
        self.assertFalse(mc.still_bar(idle,f,0.));self.assertFalse(mc.still_bar(idle,f,10.))
        self.assertTrue(mc.still_bar(idle,f,21.))
    def test_a_slow_fight_moving_one_column_is_a_fight(self):
        idle={}
        for t,level in ((0,140),(8,139),(16,138),(24,137),(32,136)):self.assertFalse(mc.still_bar(idle,frame(level),float(t)))
    def test_a_bar_that_drops_is_a_fight(self):
        idle={}
        for t,level in ((0,140),(8,120),(16,100),(24,80),(32,60)):self.assertFalse(mc.still_bar(idle,frame(level),float(t)))

class AutoMove(unittest.TestCase):
    def test_the_move_pill_counts_as_moving(self):
        from unittest.mock import patch
        f=S(hi=np.zeros((768,1366,3),dtype=np.uint8))
        with patch('owner_text.read_area',return_value=[{'text':'”자동 이동중'},{'text':'660m'}]):self.assertTrue(mc.auto_moving(f))
        with patch('owner_text.read_area',return_value=[]):self.assertFalse(mc.auto_moving(f))
        self.assertFalse(mc.auto_moving(S(hi=None)))

if __name__=='__main__':unittest.main()
