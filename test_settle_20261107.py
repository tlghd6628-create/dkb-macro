"""Settle ends once the screen holds still. Fake frames; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_settle as s


class Settle(unittest.TestCase):
    def test_still_screen_returns_early(self):
        frames=[np.zeros((64,64,3),np.uint8)]*10;waited=[]
        took=s.settle(NS(capture=lambda:frames.pop(0)),NS(wait=waited.append),1.5)
        self.assertLess(sum(waited),1.0)
    def test_moving_screen_waits_up_to_the_old_time(self):
        import itertools
        counter=itertools.count();waited=[]
        def capture():return np.full((64,64,3),(next(counter)*40)%250,np.uint8)
        clock=[0.0]
        def wait(x):waited.append(x);clock[0]+=x
        orig=s.time.monotonic;s.time.monotonic=lambda:clock[0]
        try:s.settle(NS(capture=capture),NS(wait=wait),1.0)
        finally:s.time.monotonic=orig
        self.assertGreaterEqual(sum(waited),1.0)
    def test_no_capture_is_a_plain_wait(self):
        waited=[];s.settle(NS(),NS(wait=waited.append),1.2);self.assertEqual(waited,[1.2])


if __name__=='__main__':unittest.main()
