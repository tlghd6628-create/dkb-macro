"""The coin floor, on arrays and saved frames. Never a game test."""
from pathlib import Path
import sys,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
import numpy as np,cv2
from PIL import Image
import owner_hd as hd
hd.install_reading()
import owner_text,owner_coin_reserve as coin
owner_text.set_root(bootstrap.A)
FRAMES=HERE/'image_scope_20261104/hd_frames'


class Reading(unittest.TestCase):
 def test_compact_form_gives_its_least(self):
  self.assertLessEqual(coin.lower_bound('85.18K'),85180);self.assertGreater(coin.lower_bound('85.18K'),85000)
  self.assertGreaterEqual(coin.lower_bound('1.5M'),1400000)
 def test_a_seven_may_be_a_misread_one(self):
  self.assertLess(coin.lower_bound('740.78K'),141000);self.assertLess(coin.lower_bound('170.58K'),111000)
 def test_other_currency_shape_is_no_answer(self):
  self.assertIsNone(coin.lower_bound('1,221'));self.assertIsNone(coin.lower_bound('240'));self.assertIsNone(coin.lower_bound('08'))
 def test_floor_with_cost(self):
  self.assertTrue(coin.leaves_enough(140000,100000,40000));self.assertFalse(coin.leaves_enough(139000,100000,40000))
  self.assertFalse(coin.leaves_enough(70000,100000));self.assertFalse(coin.leaves_enough(None,100000))


class Saved(unittest.TestCase):
 def setUp(self):
  coin._last[0]=None;coin._recent[0]=None
  if not FRAMES.exists():self.skipTest('saved frames not on this PC')
 def frame(self,name):
  return hd.make_frame(np.asarray(Image.open(FRAMES/(name+'_hd.png')).convert('RGB')))
 def test_reads_the_real_amounts(self):
  self.assertGreater(coin.read_balance(self.frame('growth_enhance')),130000)
  coin._last[0]=None
  self.assertLess(coin.read_balance(self.frame('m_craft')),90000)
 def test_unknown_balance_spends_nothing(self):
  blank=hd.make_frame(np.zeros((768,1366,3),np.uint8))
  self.assertIsNone(coin.read_balance(blank));self.assertFalse(coin.can_spend(blank,'x',root=bootstrap.A))
 def test_a_screen_without_the_amount_uses_a_recent_read(self):
  coin._last[0]=90000;coin._last[1]=time.monotonic()
  self.assertEqual(coin.read_balance(hd.make_frame(np.zeros((768,1366,3),np.uint8))),90000)
  coin._last[1]=time.monotonic()-coin.REMEMBER-1
  self.assertIsNone(coin.read_balance(hd.make_frame(np.zeros((768,1366,3),np.uint8))))
 def test_old_size_frame_is_not_this_rules_business(self):
  self.assertTrue(coin.can_spend(np.zeros((479,897,3),np.uint8),'x'))


class Gate(unittest.TestCase):
 def setUp(self):
  self.needle=np.random.default_rng(1).integers(0,255,(13,20,3),dtype=np.uint8)
  self.real=np.random.default_rng(2).integers(0,255,(768,1366,3),dtype=np.uint8)
  key=hd.key_of(self.needle);hd._words={key:dict(key=key,name='버튼_성장_강화',spends=True)}
  x,y=round(800*1.6-69.2),160;cut=self.real[y:y+21,x:x+32].copy()
  hd._index={key:dict(key=key,file='x.png',x=x,y=y,w=32,h=21,rule='right')};hd._images[(key,False)]=cut
  self.addCleanup(hd.reload_index);self.addCleanup(lambda:setattr(hd,'_words',None));self.addCleanup(lambda:coin._recent.__setitem__(0,None))
  coin._last[0]=None
 def answer(self,balance):
  coin._recent[0]=True;coin._recent[1]=time.monotonic();coin._recent[2]=(balance,100000)
  return cv2.matchTemplate(hd.make_frame(self.real)[100:113,800:820],self.needle,cv2.TM_CCOEFF_NORMED)
 def test_button_is_not_there_below_the_floor(self):self.assertLess(float(self.answer(70000).max()),0)
 def test_button_is_there_above_the_floor(self):self.assertGreater(float(self.answer(150000).max()),.9)
 def test_unknown_balance_hides_it(self):self.assertLess(float(self.answer(None).max()),0)


if __name__=='__main__':unittest.main()
