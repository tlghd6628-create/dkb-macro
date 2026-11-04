import bootstrap
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from owner_growth_material_contract import inspect_materials

class Materials(unittest.TestCase):
 def test_translucent_real_roi_requires_high_confidence_normalized_agreement(self):
  from PIL import Image
  detector=NS(entries={'범위_성장_장비_재료수량':dict(type='rect',x=332,y=395,w=122,h=14)},find=lambda *a,**k:True)
  frame=np.asarray(Image.open(bootstrap.A/'logs/gear-holds/20261103T131410-3b78c5ad/1.png').convert('RGB'))
  native=NS(inspect_growth_materials=lambda *a:{'status':'판별 불가'})
  def page(text,score):return [{'rec_texts':[text],'rec_scores':[score]}]
  for normalized,score,expected in (('793/2',.997,'재료 충분'),('794/2',.999,'판별 불가'),('793/2',.97,'판별 불가')):
   with self.subTest(normalized=normalized,score=score),patch('tools.ocr_support.get_paddle_engine',return_value=NS(predict=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=[page('793/2',.90),page(normalized,score)]))):
    self.assertEqual(inspect_materials(native,detector,frame,bootstrap.A)['status'],expected)
 def classify(self,text,score=.99,extra=None):
  detector=NS(entries={'범위_성장_장비_재료수량':dict(type='rect',x=332,y=395,w=122,h=14)},find=lambda *a,**k:True)
  native=NS(inspect_growth_materials=lambda *a:{'status':'판별 불가'})
  page={'rec_texts':[text],'rec_scores':[score]}
  if extra:page['rec_texts'].append(extra);page['rec_scores'].append(.99)
  with patch('tools.ocr_support.get_paddle_engine',return_value=NS(predict=lambda f:[page])):
   return inspect_materials(native,detector,np.zeros((479,897,3),dtype=np.uint8),bootstrap.A)
 def test_multidigit_and_large_counts(self):
  r=self.classify('323/4');self.assertEqual((r['status'],r['current'],r['required']),('재료 충분',323,4))
  self.assertEqual(self.classify('1,234/5')['current'],1234)
 def test_zero_is_shortage_and_zero_denominator_is_unknown(self):
  self.assertEqual(self.classify('0/5')['status'],'재료 부족')
  self.assertEqual(self.classify('3/0')['status'],'판별 불가')
 def test_ambiguous_low_confidence_and_bad_separator_are_held(self):
  for text in ('323','3,,23/4','323/4/5','32.3/4'):
   self.assertEqual(self.classify(text)['status'],'판별 불가')
  self.assertEqual(self.classify('323/4',.97)['status'],'판별 불가')
  self.assertEqual(self.classify('323/4',extra='322/4')['status'],'판별 불가')
 def test_native_confirmed_result_never_invokes_ocr(self):
  original={'status':'재료 부족','reason':'native'}
  with patch('tools.ocr_support.get_paddle_engine',side_effect=AssertionError('no OCR')):
   self.assertEqual(inspect_materials(NS(inspect_growth_materials=lambda *a:original),None,None,None),original)

if __name__=='__main__':unittest.main()
