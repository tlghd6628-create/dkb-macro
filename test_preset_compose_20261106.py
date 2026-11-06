"""Preset letter B set to skills only. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_preset_compose as c


class Reading(unittest.TestCase):
    def test_picked_button_has_a_white_bottom_edge(self):
        real=np.zeros((768,1366,3),np.uint8);x,y=c.BUTTON_X[1],234
        self.assertFalse(c.picked(real,x,y))
        real[y+19,x-60:x+60]=255;self.assertTrue(c.picked(real,x,y))
        real2=np.zeros((768,1366,3),np.uint8);real2[y+4,x-20:x+20]=255
        self.assertFalse(c.picked(real2,x,y))
    def test_headers_by_their_words(self):
        rows=[dict(word='장비프리셋',ry=191),dict(word='가호프리셋',ry=360),dict(word='도술프리셋',ry=528)]
        with patch.object(c,'words',return_value=rows):
            self.assertEqual(c.headers(None),{'장비프리셋':191,'가호프리셋':360,'도술프리셋':528})
    def test_only_b_is_composed(self):
        self.assertEqual(c.wanted('B'),{'장비프리셋':1,'가호프리셋':1,'도술프리셋':2,'의복프리셋':1})
        self.assertIsNone(c.wanted('A'));self.assertIsNone(c.wanted('C'))


class Once(unittest.TestCase):
    def test_remembered_per_character(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir()
            self.assertFalse(c.done(root,'홍짱군','B'))
            c.remember(root,'홍짱군','B')
            self.assertTrue(c.done(root,'홍짱군','B'));self.assertFalse(c.done(root,'은짱군','B'))
    def test_ensure_runs_once_and_a_failure_does_not_stop_the_switch(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'settings').mkdir();calls=[]
            adapter=NS(project=NS(root=root))
            class Fake:
                def __init__(self,ui):pass
                def run(self,letter):calls.append(letter)
            with patch('owner_hunt_rules_candidate.configured_identity',return_value='홍짱군'),patch('owner_mission_ui.MissionUI',lambda *a:None),patch.object(c,'Compose',Fake):
                self.assertTrue(c.ensure(adapter,None,None,'B'));self.assertTrue(c.ensure(adapter,None,None,'B'))
                self.assertFalse(c.ensure(adapter,None,None,'A'))
            self.assertEqual(calls,['B'])
            class Broken(Fake):
                def run(self,letter):raise RuntimeError('도술프리셋 줄 미확인')
            with patch('owner_hunt_rules_candidate.configured_identity',return_value='은짱군'),patch('owner_mission_ui.MissionUI',lambda *a:None),patch.object(c,'Compose',Broken):
                self.assertFalse(c.ensure(adapter,None,None,'B'))
            self.assertFalse(c.done(root,'은짱군','B'))


if __name__=='__main__':unittest.main()
