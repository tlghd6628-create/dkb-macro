"""Mock OCR with actual named reward backgrounds; no input or fake live proof."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
from PIL import Image
import numpy as np
from owner_energy_reward_candidate import quantity,matches
class Tests(unittest.TestCase):
 def setUp(self):
  self.frame=np.asarray(Image.open(bootstrap.A/'logs/energy-claim-evidence/d55113d063ef46cb80813f0e575cc7ca/after-05.png').convert('RGB')).copy()
 def test_actual_one_receipt_stays_fast_and_exact(self):
  with patch('tools.ocr_support.get_paddle_engine',side_effect=AssertionError('one needs no OCR')):
   self.assertEqual(quantity(self.frame,'생명'),1);self.assertTrue(matches(self.frame,'생명',1));self.assertFalse(matches(self.frame,'생명',16))
 def test_N_parser_matches_observed_quantity_not_requested_quantity(self):
  self.frame[150:162,433:467]=0
  engine=S(predict=lambda image:[{'rec_texts':['16'],'rec_scores':[.999]}])
  with patch('tools.ocr_support.get_paddle_engine',return_value=engine):
   self.assertEqual(quantity(self.frame,'생명'),16);self.assertFalse(matches(self.frame,'생명',15))
 def test_unknown_low_confidence_duplicate_and_wrong_name_reject(self):
  self.frame[150:162,433:467]=0
  for texts,scores in ((['16개'],[.999]),(['16'],[.97]),(['16','16'],[.999,.999]),(['0'],[.999])):
   engine=S(predict=lambda image,t=texts,s=scores:[{'rec_texts':t,'rec_scores':s}])
   with patch('tools.ocr_support.get_paddle_engine',return_value=engine):self.assertIsNone(quantity(self.frame,'생명'))
  self.assertIsNone(quantity(self.frame,'여명'));self.assertIsNone(quantity(self.frame,'홍염'))
if __name__=='__main__':unittest.main()
