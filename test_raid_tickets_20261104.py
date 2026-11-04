"""Raid ticket reading with a fake reader, on the real raid page. Not a live raid."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_raid_tickets as t
import project_adapter.boss_raid as raid
from roi_runtime import RoiDetector

FRAME=Path(__file__).resolve().parent/'fixtures_image_scope/raid_page.png'
def frame():return np.array(Image.open(FRAME).convert('RGB'))

class Parse(unittest.TestCase):
    def test_reads_what_the_real_ocr_returned_on_the_page(self):
        self.assertEqual(t.parse([('5/10',.988)]),5)
    def test_zero_is_a_real_zero(self):
        self.assertEqual(t.parse([('0/10',.95)]),0)
    def test_ten_of_ten(self):
        self.assertEqual(t.parse([('10/10',.95)]),10)
    def test_low_confidence_noise_and_other_totals_are_not_a_count(self):
        for rows in ([('5/10',.5)],[('W:5/10',.98)],[('5/20',.99)],[('11/10',.99)],[],[('5/10',.99),('6/10',.99)]):
            self.assertIsNone(t.parse(rows),rows)

class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        t.install();cls.frame=frame()
        cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(raid.NAMES))
    def flow(self):
        f=raid.RaidFlow.__new__(raid.RaidFlow)
        f.adapter=S(project=S(root=None));f.context=S(wait=lambda s:None,checkpoint=lambda:None)
        f.detector=self.detector;f.detectors=[self.detector];f.service=S(capture=lambda:self.frame)
        return f
    def run_find(self,reads,on_page=True):
        reads=list(reads);calls=[];f=self.flow()
        def once(root,fr,context):
            calls.append(1);return reads.pop(0)
        def plain(flow,name,fr,*a,**k):return (1,1,(0,0,2,2)) if name==raid.MATCH and on_page else ('native',name)
        with patch.object(t,'read_once',once),patch.object(raid.RaidFlow,'find',plain):
            t.install()
            hit=raid.RaidFlow.find(f,raid.NO_TICKET,self.frame)
            hit2=raid.RaidFlow.find(f,raid.NO_TICKET,self.frame)
        return hit,hit2,calls
    def test_five_tickets_does_not_stop(self):
        hit,again,calls=self.run_find([5,5])
        self.assertIsNone(hit);self.assertIsNone(again);self.assertEqual(len(calls),2)  # same frame is not read twice over
    def test_zero_tickets_stops(self):
        hit,_,_=self.run_find([0,0])
        self.assertEqual(hit[:2],(777,411))
    def test_a_cold_first_read_does_not_stop_it(self):
        hit,_,calls=self.run_find([None,5,5]);self.assertIsNone(hit);self.assertEqual(len(calls),3)
    def test_reads_that_never_agree_stop_before_matching(self):
        with self.assertRaises(raid.RaidPending):self.run_find([5,0,5,0])
    def test_unread_stops_before_matching(self):
        with self.assertRaises(raid.RaidPending):self.run_find([None,None,None,None])
    def test_other_images_keep_the_native_path(self):
        f=self.flow()
        def plain(flow,name,fr,*a,**k):return ('native',name)
        with patch.object(raid.RaidFlow,'find',plain):
            t.install()
            self.assertEqual(raid.RaidFlow.find(f,raid.MATCH,self.frame),('native',raid.MATCH))
    def test_off_the_raid_page_nothing_is_read(self):
        calls=[]
        def plain(flow,name,fr,*a,**k):return None
        with patch.object(t,'read_once',lambda *a:calls.append(1)),patch.object(raid.RaidFlow,'find',plain):
            t.install()
            self.assertIsNone(raid.RaidFlow.find(self.flow(),raid.NO_TICKET,self.frame))
        self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
