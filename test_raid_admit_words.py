"""매칭 입장 popup by its words at 1366x768. Fake frames and fake reads; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import numpy as np
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_real_marks as m
import owner_image_scope as scope

TITLE={'text':'매칭 입장','x':448,'y':139,'rx':682,'ry':223}
OK={'text':'확인','x':511,'y':330,'rx':778,'ry':529}
NO={'text':'취소','x':381,'y':330,'rx':580,'ry':529}


def reads(title,buttons):
    def read(root,frame,box,**kw):return title if box==m.RAID_ADMIT_TITLE else buttons
    return read


class RaidAdmit(unittest.TestCase):
    def frame(self):return S(hi=np.zeros((768,1366,3),np.uint8),layout=None)
    def run_with(self,title,buttons,fn):
        with patch('owner_text.read',side_effect=reads(title,buttons)),\
             patch('owner_text.logical_bounds',side_effect=lambda r,f:(r['x']-5,r['y']-5,r['x']+5,r['y']+5)):
            return fn(self.frame())
    def test_confirm_is_the_ok_word(self):
        self.assertEqual(self.run_with([TITLE],[NO,OK],m.raid_admit_confirm),(511,330,(506,325,516,335)))
    def test_title_answers(self):
        self.assertEqual(self.run_with([TITLE],[NO,OK],m.raid_admit_title)[:2],(448,139))
    def test_cancel_alone_is_never_taken(self):
        self.assertIsNone(self.run_with([TITLE],[NO],m.raid_admit_confirm))
    def test_without_title_nothing(self):
        self.assertIsNone(self.run_with([{'text':'레이드','x':1,'y':1}],[NO,OK],m.raid_admit_confirm))
        self.assertIsNone(self.run_with([],[NO,OK],m.raid_admit_title))
    def test_old_frame_reads_nothing(self):
        with patch('owner_text.read',side_effect=AssertionError('no read')):
            self.assertIsNone(m.raid_admit_confirm(S()))
    def test_wired_as_real_words(self):
        self.assertEqual(scope.REAL_WORDS['체크_레이드_매칭입장'],'raid_admit_title')
        self.assertEqual(scope.REAL_WORDS['버튼_레이드_매칭입장확인'],'raid_admit_confirm')


if __name__=='__main__':unittest.main()
