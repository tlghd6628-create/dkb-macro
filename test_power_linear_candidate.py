exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf-8'))
import sys,unittest
from unittest.mock import patch
import owner_progression as p
class FakeEngine:
 def __init__(self,*answers):self.answers=iter(answers)
 def predict(self,_):
  text,score=next(self.answers);return [{'rec_texts':[text],'rec_scores':[score]}]
class Tests(unittest.TestCase):
 def setUp(self):
  import numpy as np
  self.frame=np.zeros((479,897,3),dtype='uint8')
 def test_new_linear_requires_strong_confidence_and_agreement(self):
  with patch.object(p,'inventory_parts',return_value=(True,True)):
   self.assertEqual(p.read_inventory_power(FakeEngine(('123,456',.94),('123,456',.981)),self.frame),123456)
   self.assertIsNone(p.read_inventory_power(FakeEngine(('123,456',.94),('123,457',.99),('123,457',.91),('123,457',.81)),self.frame))
   self.assertIsNone(p.read_inventory_power(FakeEngine(('123,456',.94),('123,456',.979),('123,456',.91),('123,456',.97)),self.frame))
 def test_old_cubic_and_orange_behavior_stays(self):
  with patch.object(p,'inventory_parts',return_value=(True,True)):
   self.assertEqual(p.read_inventory_power(FakeEngine(('123,456',.91),('123,456',.91),('123,456',.93)),self.frame),123456)
   self.assertEqual(p.read_inventory_power(FakeEngine(('123,456',.9),('123,456',.9),('123,456',.91),('123,456',.99)),self.frame),123456)
 def test_unknown_inventory_never_uses_alternate(self):
  with patch.object(p,'inventory_parts',return_value=(False,True)):
   self.assertIsNone(p.read_inventory_power(FakeEngine(('123,456',.94),('123,456',.91)),self.frame))
if __name__=='__main__':unittest.main(verbosity=2)

