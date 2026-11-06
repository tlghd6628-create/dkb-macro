"""The skip question's 오늘 하루 안 보기 is ticked once a game day. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from contextlib import nullcontext
from datetime import datetime
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_dialogue as d


class Today(unittest.TestCase):
    def test_once_a_day(self):
        clicks=[]
        runner=NS(adapter=NS(),context=NS(checkpoint=lambda:None,wait=lambda s:None),
                  inputs=NS(transaction=nullcontext,click=lambda x,y,bounds=None:clicks.append((x,y))))
        row=dict(text='오늘 하루 안 보기',bounds=(640,416,740,436),ry=426)
        with patch('owner_text.read',return_value=[row]),patch('owner_timetable.now',return_value=datetime(2026,11,6,12)):
            self.assertTrue(d.tick_today(runner,NS(hi=1)));self.assertFalse(d.tick_today(runner,NS(hi=1)))
        with patch('owner_text.read',return_value=[row]),patch('owner_timetable.now',return_value=datetime(2026,11,7,12)):
            self.assertTrue(d.tick_today(runner,NS(hi=1)))
        self.assertEqual(len(clicks),2)
    def test_no_words_no_click(self):
        runner=NS(adapter=NS(),context=NS(checkpoint=lambda:None,wait=lambda s:None),inputs=NS(transaction=nullcontext,click=lambda *a,**k:self.fail('click')))
        with patch('owner_text.read',return_value=[]):self.assertFalse(d.tick_today(runner,NS(hi=1)))
        self.assertFalse(d.tick_today(runner,NS()))


if __name__=='__main__':unittest.main()
