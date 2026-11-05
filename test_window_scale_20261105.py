"""Larger game window: sizes, points, frames and reader crops, on arrays only. Never a game test."""
from pathlib import Path
import sys,os
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
import numpy as np
from PIL import Image
import owner_window_scale as ws
from owner_progression import resized

LIVE=HERE/'image_scope_20261104/live'


class Sizes(unittest.TestCase):
 def test_factor(self):
  self.assertEqual(ws.factor_of((897,479)),1.0);self.assertAlmostEqual(ws.factor_of((1346,719)),1.5,2);self.assertEqual(ws.factor_of((1794,958)),2.0)
 def test_a_different_shape_is_not_scaled(self):
  self.assertEqual(ws.factor_of((1000,479)),1.0);self.assertEqual(ws.logical_of((1000,479)),(1000,479))
 def test_logical_stays_the_old_size(self):
  self.assertEqual(ws.logical_of((1346,719)),(897,479));self.assertEqual(ws.logical_of((897,479)),(897,479))
 def test_points(self):
  self.assertEqual(ws.scaled_point((100,200),1.5),(150,300));self.assertEqual(ws.scaled_point((0,0),1.5),(0,0));self.assertEqual(ws.scaled_point((100,200),1.0),(100,200))
 def test_screen_choice(self):
  os.environ.pop('DKB_WINDOW_SCALE',None)
  self.assertEqual(ws.wanted_scale((1920,1009)),1.5);self.assertEqual(ws.wanted_scale((1366,728)),1.0);self.assertEqual(ws.wanted_scale((1920,600)),1.0)


class Frames(unittest.TestCase):
 def test_frame_is_old_size_and_keeps_the_real_one_through_copy(self):
  real=np.zeros((719,1346,3),np.uint8)
  frame=ws.scale_down(real)
  self.assertEqual(frame.shape,(479,897,3));self.assertIs(frame.hi,real);self.assertIs(frame.copy().hi,real)
 def test_reader_gets_the_same_size_and_place_either_way(self):
  real=np.zeros((719,1346,3),np.uint8);real[300:330,600:750]=255
  frame=ws.scale_down(real);plain=np.asarray(frame)
  self.assertEqual(resized(frame,(400,200,100,20)).shape,resized(plain,(400,200,100,20)).shape)
  both=resized(frame,(400,200,100,20))[...,0]>128;low=resized(plain,(400,200,100,20))[...,0]>128
  self.assertGreater(float((both==low).mean()),.95)
 def test_a_plain_frame_still_reads(self):
  self.assertEqual(resized(np.zeros((479,897,3),np.uint8),(10,10,20,20)).shape,((20+16)*4,(20+16)*4,3))


class RealShop(unittest.TestCase):
 def test_the_text_that_failed_reads_right_at_the_larger_size(self):
  path=LIVE/'size_15x.png'
  if not path.exists():self.skipTest('saved frame not on this PC')
  from tools.ocr_support import get_paddle_engine
  engine=get_paddle_engine(bootstrap.A,language='korean')
  frame=ws.scale_down(np.asarray(Image.open(path).convert('RGB')))
  text=' '.join(t for page in engine.predict(resized(frame,(44,61,153,370))) for t in page['rec_texts'])
  self.assertIn('절명 도술 강화 요령서',text);self.assertIn('(0/50)',text)


if __name__=='__main__':unittest.main()
