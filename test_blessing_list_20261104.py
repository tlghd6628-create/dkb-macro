"""The worn list rule while a tile is selected. Fake rows, not a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from owner_blessing_native_candidate import worn_unchanged

A,B,C={'x':1},{'x':2},{'x':3}
BEFORE=[(1,A),(2,B),(3,C)]
def row(index,slot):return {'index':index,'slot':slot}

class Worn(unittest.TestCase):
    def test_the_selected_tile_may_lose_its_badge(self):
        self.assertTrue(worn_unchanged([row(2,B),row(3,C)],BEFORE,1))
    def test_the_selected_tile_may_keep_it(self):
        self.assertTrue(worn_unchanged([row(1,A),row(2,B),row(3,C)],BEFORE,1))
    def test_another_tile_losing_it_is_a_change(self):
        self.assertFalse(worn_unchanged([row(1,A),row(3,C)],BEFORE,1))
    def test_a_new_tile_is_a_change(self):
        self.assertFalse(worn_unchanged([row(2,B),row(3,C),row(4,A)],BEFORE,1))
    def test_a_moved_tile_is_a_change(self):
        self.assertFalse(worn_unchanged([row(2,C),row(3,C)],BEFORE,1))

class Title(unittest.TestCase):
    """The real title from the 17:39 hold, and what its allowance must still refuse."""
    def setUp(self):
        import numpy as np
        from PIL import Image
        import owner_blessing_native_candidate as b
        self.b=b;self.np=np
        self.frame=np.array(Image.open(Path(__file__).resolve().parent/'fixtures_image_scope/blessing_title.png').convert('RGB'))
        self.box=(327,65,133,18)
    def flip(self,count):
        f=self.frame.copy();x,y,w,h=self.box
        import cv2
        hsv=cv2.cvtColor(f[y:y+h,x:x+w],cv2.COLOR_RGB2HSV);ys,xs=self.np.where((hsv[:,:,1]<60)&(hsv[:,:,2]>170))
        for i in range(count):f[y+ys[i*7],x+xs[i*7]]=(20,20,20)
        return f
    def test_the_same_frame_passes_exactly(self):
        self.assertTrue(self.b.same_white_text(self.frame,self.frame,self.box))
    def test_one_flipped_pixel_passes_only_with_the_allowance(self):
        changed=self.flip(1)
        self.assertFalse(self.b.same_white_text(self.frame,changed,self.box))
        self.assertTrue(self.b.same_white_text(self.frame,changed,self.box,self.b.TITLE_TOLERANCE))
    def test_a_changed_digit_is_refused_even_with_the_allowance(self):
        changed=self.frame.copy();x,y,w,h=self.box
        # 장식3 -> the last glyph blanked out: far more than the allowance.
        changed[y:y+h,x+92:x+105]=(20,20,20)
        self.assertFalse(self.b.same_white_text(self.frame,changed,self.box,self.b.TITLE_TOLERANCE))

if __name__=='__main__':unittest.main()
