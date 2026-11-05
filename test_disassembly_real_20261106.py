"""장비 분해 at 1366x768: control states, the marked-tile check and the bag count. Fake frames; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_disassembly_real as d
from owner_upgrade_equip import BAG_X,BAG_Y


def screen(lit=(),box=False):
    im=np.full((768,1366,3),40,np.uint8)
    for name,(x,y) in d.BUTTONS:im[y-10:y+10,x-28:x+28]=140 if name in lit else 70
    x,y=d.BOX;im[y-9:y+9,x-9:x+9]=72 if box else 24
    return im


def service(im):return NS(capture=lambda:NS(hi=im),context=NS(wait=lambda t:None))


class States(unittest.TestCase):
    def test_lit_dark_and_the_box(self):
        self.assertEqual(d.states(service(screen(('일반','희귀'),True))),({'일반':True,'희귀':True,'영웅':False},True))
        self.assertEqual(d.states(service(screen())),({'일반':False,'희귀':False,'영웅':False},False))
    def test_between_is_no_answer(self):
        im=screen();x,y=d.BUTTONS[1][1];im[y-10:y+10,x-28:x+28]=105
        with self.assertRaises(d.Hold):d.states(service(im))


class Marked(unittest.TestCase):
    def tile(self,im,place,colour):
        x,y=place;im[y-24:y+24,x-24:x+24]=colour;im[y-10:y+10,x-10:x+10]=(220,220,220)
    def test_the_changed_tiles_and_their_grade_before(self):
        before=np.full((768,1366,3),(52,47,45),np.uint8)
        grey,blue=(BAG_X[0],BAG_Y[0]),(BAG_X[1],BAG_Y[0])
        self.tile(before,grey,(81,76,69));self.tile(before,blue,(51,102,139))
        after=before.copy();x,y=grey;after[y-24:y+24,x-24:x+24]//=3       # the mark darkens the tile
        self.assertEqual(d.changed_tiles(before,after),[grey]);self.assertEqual(d.grade_colour(before,grey),'일반')
        after[blue[1]-24:blue[1]+24,blue[0]-24:blue[0]+24]//=3
        self.assertEqual([d.grade_colour(before,p) for p in d.changed_tiles(before,after)],['일반','높음'])


class Count(unittest.TestCase):
    def test_two_looks_of_the_count(self):
        rows=iter([[dict(text='127/400',score=.9,rx=1121,ry=129)]]*2)
        with patch('owner_text.read_area',side_effect=lambda *a,**k:next(rows)):
            self.assertEqual(d.bag_count(service(np.zeros((768,1366,3),np.uint8))),127)


if __name__=='__main__':unittest.main()
