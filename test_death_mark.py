"""체크_사망상태 by words, gated by the red title. Fake frames; not a live claim."""
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

class DeathMark(unittest.TestCase):
    def test_no_red_title_reads_nothing(self):
        f=S(hi=np.zeros((768,1366,3),np.uint8))
        with patch('owner_death_real.dead',side_effect=AssertionError('no read')):self.assertIsNone(m.death_mark(f))
    def test_red_title_and_words_answer(self):
        a=np.zeros((768,1366,3),np.uint8);a[22:58,600:780]=(200,40,40);f=S(hi=a,layout=None)
        row={'text':'사망 상태','x':455,'y':26,'rx':683,'ry':40,'bounds':(640,30,730,50)}
        with patch('owner_death_real.dead',return_value=True),patch('owner_text.read',return_value=[row]),patch('owner_text.logical_bounds',return_value=(422,15,489,38)):
            self.assertEqual(m.death_mark(f),(455,26,(422,15,489,38)))
        with patch('owner_death_real.dead',return_value=False):self.assertIsNone(m.death_mark(f))
    def test_wired_as_a_real_word(self):
        self.assertEqual(scope.REAL_WORDS['체크_사망상태'],'death_mark')

if __name__=='__main__':unittest.main()
