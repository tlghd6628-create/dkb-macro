"""Actual saved static ROI + delayed fake OCR, no real game actions."""
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import bootstrap
from test_gear_native_observer_candidate import Service,NativeFake,Context,Clock
from owner_gear_native_observer_candidate import Observer


class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  root=bootstrap.A/'logs/scene-corpus/20261101'
  cls.pre=np.asarray(Image.open(root/'20261101T162240-7afa44af/screen.png').convert('RGB'))
  cls.post=np.asarray(Image.open(root/'20261101T162242-cdf1cd68/screen.png').convert('RGB'))
 def setUp(self):
  self.clock=Clock();self.ctx=Context(self.clock);self.service=Service(self.pre,self.post);self.native=NativeFake(self.service)
  def detail(*args,**kwargs):self.clock.value+=2.;return {'enhancement':26,'materials':'재료 충분'}
  self.native.read_growth_equipment_detail=detail
  self.resources=lambda f:dict(verified=True,active=True,currency='엽전',cost=3000,balance=4416)
  self.o=Observer(self.service,self.ctx,'test',self.native,lambda *a:'icon',self.resources,clock=self.clock)
  self.o.prepare_and_select(9)
 def test_slow_ocr_requires_two_new_actual_capture_receipts(self):
  out=self.o.read_pair();self.assertTrue(out['screen_proof'],self.o.last_reason)
  a,b=out['first'],out['second'];self.assertGreaterEqual(a.sequence,5)
  self.assertLessEqual(self.clock()-a.captured_at,1.5);self.assertEqual(a.enhancement,26)
  self.assertTrue(self.o.last_timings['refreshed_after_ocr']);self.assertEqual(self.service.clicks,[])
 def test_number_change_during_refresh_never_reuses_old_value(self):
  original=self.service.capture;count=[0]
  def capture():
   count[0]+=1;f=original()
   if count[0]>=3:
    box=self.o._number_box(f);x,y,w,h=box;f[y:y+h,x:x+w]=0
   return f
  self.service.capture=capture
  self.assertFalse(self.o.read_pair()['screen_proof']);self.assertEqual(self.service.clicks,[])
 def test_resource_change_during_refresh_is_held(self):
  count=[0]
  def resources(f):
   count[0]+=1;return dict(verified=True,active=count[0]<3,currency='엽전',cost=3000,balance=4416)
  self.o.resources_reader=resources
  self.assertFalse(self.o.read_pair()['screen_proof']);self.assertIn('재료',self.o.last_reason)
 def test_final_input_check_reuses_only_the_matching_fresh_number_roi(self):
  out=self.o.read_pair();self.assertTrue(out['screen_proof'])
  self.native.read_growth_equipment_detail=lambda *a,**kw:self.fail('full OCR at commit boundary')
  self.assertTrue(self.o.verify_final(self.post,out,'enhance'))
  changed=self.post.copy();x,y,w,h=self.o._number_box(changed);changed[y:y+h,x:x+w]=0
  self.assertFalse(self.o.verify_final(changed,out,'enhance'));self.assertEqual(self.service.clicks,[])
 def test_same_numeric_value_from_different_pixels_is_not_authority(self):
  original=self.service.capture;count=[0]
  def capture():
   count[0]+=1;frame=original()
   if count[0]>=3:
    x,y,w,h=self.o._number_box(frame);frame[y:y+h,x:x+w]=np.roll(frame[y:y+h,x:x+w],1,axis=1)
   return frame
  self.service.capture=capture
  self.assertFalse(self.o.read_pair()['screen_proof'])
 def test_stop_during_new_capture_prevents_refresh(self):
  original=self.service.capture;count=[0]
  def capture():
   count[0]+=1;frame=original()
   if count[0]==2:self.ctx.stopped=True
   return frame
  self.service.capture=capture
  with self.assertRaisesRegex(RuntimeError,'cancelled'):self.o.read_pair()
  self.assertEqual(self.service.clicks,[])
 def test_actual_16_glyphs_stay_identical_while_clipped_rim_animates(self):
  root=bootstrap.A/'logs/gear-holds/20261103T151736-daffcd82'
  a,b=[np.asarray(Image.open(root/f'{i}.png').convert('RGB')).copy() for i in (1,2)]
  box=self.o._number_box(a);self.assertEqual(box,(317,123,70,24))
  self.assertTrue(self.o._same_number_pixels(a,b,box))
  # Change one real digit stroke; unchanged scenery/rim cannot rescue it.
  changed=b.copy();x,y,w,h=box;changed[y+9:y+17,x+56:x+59]=0
  self.assertFalse(self.o._same_number_pixels(a,changed,box))
  blank=b.copy();blank[y:y+h,x:x+w]=0
  self.assertFalse(self.o._same_number_pixels(blank,blank,box))


if __name__=='__main__':unittest.main()
