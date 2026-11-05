"""1 or 7 by the glyph's shape (owner_digit_shape) and its use in every OCR read. Drawn glyphs from pc1's real frames; no game."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_digit_shape as shape

ONE=['#####','#####','..###','..###','..###','..###','..###','..###','..###','..###','..###','..###']        # 귀걸이 1 >> 2, 05:10
SEVEN=['#######','#######','.....##','....##.','....##.','...##..','...##..','..##...','..##...','.##....']  # a real 7, 05:08
ZERO=['..#####..','.#######.','###...###','##.....##','##.....##','##.....##','##.....##','##.....##','##.....##','###...###','.#######.','..#####..']


def draw(*glyphs,gap=3,height=16):
    width=sum(len(g[0]) for g in glyphs)+gap*(len(glyphs)+1)
    area=np.full((height,width,3),30,np.uint8);x=gap
    for g in glyphs:
        for r,row in enumerate(g):
            for c,v in enumerate(row):
                if v=='#':area[2+r,x+c]=(235,235,235)
        x+=len(g[0])+gap
    return area


def mask(g):return np.array([[v=='#' for v in row] for row in g])


class Shape(unittest.TestCase):
    def test_the_fonts_one_and_seven(self):
        self.assertEqual(shape.one_or_seven(mask(ONE)),'1');self.assertEqual(shape.one_or_seven(mask(SEVEN)),'7')
    def test_other_digits_are_left_to_the_engine(self):
        self.assertIsNone(shape.one_or_seven(mask(ZERO)))


class Settle(unittest.TestCase):
    def test_a_seven_that_is_a_one(self):
        self.assertEqual(shape.settle('7',draw(ONE)),'1');self.assertEqual(shape.settle('47',draw(ZERO,ONE)),'41')
    def test_a_real_seven_stays(self):
        self.assertEqual(shape.settle('7',draw(SEVEN)),'7');self.assertEqual(shape.settle('17',draw(ONE,SEVEN)),'17')
    def test_glyphs_that_do_not_line_up_change_nothing(self):
        self.assertEqual(shape.settle('77',draw(ONE)),'77')
    def test_words_are_not_touched(self):
        self.assertEqual(shape.settle('장식7',draw(ONE)),'장식7')
    def test_a_lone_one(self):
        self.assertTrue(shape.lone_one(draw(ONE)));self.assertFalse(shape.lone_one(draw(SEVEN)));self.assertFalse(shape.lone_one(draw(ONE,ZERO)))


class EveryRead(unittest.TestCase):
    def test_the_shared_reader_settles_numbers(self):
        import owner_text as text
        area=draw(ONE)
        h,w=area.shape[:2]
        self.assertEqual(text.digit_shapes(area,[('7',.95,w/2,h/2,0.,0.,float(w),float(h))],'number')[0][0],'1')
        self.assertEqual(text.digit_shapes(area,[('T',.4,w/2,h/2,0.,0.,float(w),float(h))],'korean')[0][0],'1')
    def test_a_missed_lone_one_is_put_back_for_numbers_only(self):
        import owner_text as text
        self.assertEqual([r[0] for r in text.digit_shapes(draw(ONE),[],'number')],['1'])
        self.assertEqual(text.digit_shapes(draw(ONE),[],'korean'),[])
        self.assertEqual(text.digit_shapes(draw(ZERO),[],'number'),[])


class Next(unittest.TestCase):
    def test_the_next_step_carries_an_unsteady_left_side(self):
        from owner_growth_words import next_pair
        right=[dict(text='5+',score=.99)]
        self.assertEqual(next_pair([],right),(4,5))
        self.assertEqual(next_pair([dict(text='4',score=.55)],right),(4,5))
        self.assertIsNone(next_pair([dict(text='7',score=.6)],right))      # the left says otherwise: no read
        self.assertIsNone(next_pair([],[dict(text='5+',score=.5)]))         # an unclear next step: no read
        self.assertIsNone(next_pair([],[]))


class Panel(unittest.TestCase):
    def test_one_to_two_reads_by_shape(self):
        from types import SimpleNamespace as NS
        import owner_growth_words as words
        real=np.full((768,1366,3),30,np.uint8);x,y,w,h=words.BLESSING_LEVEL
        real[y+8:y+8+16,x+40:x+40+draw(ONE).shape[1]]=draw(ONE)
        self.assertEqual(words.lone_one_pair(NS(hi=real),[dict(text='2+',score=.99)]),(1,2))
        self.assertIsNone(words.lone_one_pair(NS(hi=real),[dict(text='3+',score=.99)]))


if __name__=='__main__':unittest.main()
