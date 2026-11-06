"""A full remote potion limit is remembered on disk for an hour. Fake reads; never a game test."""
from pathlib import Path
from unittest.mock import patch
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_remote_potion_limit_candidate as m
import owner_hunt_here as h
import numpy as np
from types import SimpleNamespace as NS


class Hour(unittest.TestCase):
    def test_kept_an_hour_per_character_and_tier(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir()
            with patch('owner_hunt_rules_candidate.configured_identity',return_value='홍짱군'):
                self.assertFalse(m.recall_full(root,'1단물약',now=1000))
                self.assertTrue(m.note_full(root,'1단물약',now=1000))
                self.assertTrue(m.recall_full(root,'1단물약',now=1000+3599))
                self.assertFalse(m.recall_full(root,'1단물약',now=1000+3600))
                self.assertFalse(m.recall_full(root,'2단물약',now=1001))
            with patch('owner_hunt_rules_candidate.configured_identity',return_value='은짱군'):
                self.assertFalse(m.recall_full(root,'1단물약',now=1001))


class Auto(unittest.TestCase):
    def test_orange_ring_is_on(self):
        hi=np.zeros((768,1366,3),np.uint8);self.assertFalse(h.auto_lit(NS(hi=hi)))
        x,y,w,h_=h.AUTO_BOX;hi[y+5:y+10,x+5:x+20]=(240,160,40);self.assertTrue(h.auto_lit(NS(hi=hi)))
        self.assertFalse(h.auto_lit(NS(hi=None)))


if __name__=='__main__':unittest.main()
