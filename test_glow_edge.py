"""Clipped glow boxes on fake frames. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import numpy as np
from types import SimpleNamespace as S
import owner_glow_edge as ge

class Edge(unittest.TestCase):
    def test_a_box_cut_by_the_frame_edge_is_not_a_sparkle(self):
        calls=[];self_=S(mask=np.zeros((34,40),np.uint8))
        checked=ge.guard(lambda s,f,b:calls.append(1) or True)
        frames=[np.zeros((479,897,3),np.uint8)]*2
        self.assertFalse(checked(self_,frames,(800,456,840,490)));self.assertEqual(calls,[])
        self.assertTrue(checked(self_,frames,(100,100,140,134)));self.assertEqual(calls,[1])

if __name__=='__main__':unittest.main()
