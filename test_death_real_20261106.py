"""Death at 1366 by the death screen's own words. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_death_real as d
import owner_hd as hd


class Dead(unittest.TestCase):
    def reads(self,top,bottom):
        def read(root,frame,box,**k):
            if box==d.TITLE:return [dict(text=w) for w in top]
            return [dict(text=w,rx=683,ry=726) for w in bottom]
        return patch('owner_text.read',read)
    def test_both_words_are_needed(self):
        with self.reads(['사망 상태'],['나가기']):self.assertTrue(d.dead(NS(hi=1)))
        with self.reads(['사망 상태'],[]):self.assertFalse(d.dead(NS(hi=1)))
        with self.reads([],['나가기']):self.assertFalse(d.dead(NS(hi=1)))
        self.assertFalse(d.dead(NS()))
    def test_two_looks_then_exit_once(self):
        clicks=[];looks=iter([True,True,False])
        ui=NS(frame=lambda:NS(hi=1),context=NS(wait=lambda s:None,checkpoint=lambda:None),service=NS(click_hit=lambda h:clicks.append(h[:2])))
        with patch.object(d,'dead',side_effect=lambda f:next(looks)),patch.object(d,'exit_word',return_value=dict(rx=683,ry=726)):
            self.assertTrue(d.recover(ui))
        self.assertEqual(clicks,[hd.real_hit(683,726)[:2]])
    def test_one_look_is_not_enough(self):
        looks=iter([True,False]);ui=NS(frame=lambda:NS(hi=1),context=NS(wait=lambda s:None,checkpoint=lambda:None),service=NS(click_hit=lambda h:self.fail('no click')))
        with patch.object(d,'dead',side_effect=lambda f:next(looks)):self.assertFalse(d.recover(ui))


if __name__=='__main__':unittest.main()
