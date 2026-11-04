import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_blessing_priority_candidate import compare,collect_rank_fields

class Priority(unittest.TestCase):
 def row(self,grade,pattern,slot=1,verified=True):
  return {'grade':grade,'pattern':pattern,'slot':slot,'verified':verified}
 def test_grade_precedes_pattern(self):
  self.assertEqual(compare(self.row('희귀','봉황'),self.row('영웅','토끼'),['봉황','토끼']),'replace')
  self.assertEqual(compare(self.row('영웅','토끼'),self.row('희귀','봉황'),['봉황','토끼']),'keep')
 def test_user_order_only_for_equal_grade(self):
  a,b=self.row('희귀','봉황'),self.row('희귀','나비')
  self.assertEqual(compare(a,b,['나비','봉황']),'replace')
  self.assertEqual(compare(a,b,['봉황','나비']),'keep')
  self.assertEqual(compare(a,b,[]),'hold')
  self.assertEqual(compare(a,b,['나비']),'hold')
 def test_never_guess_bad_proof_or_slot(self):
  a=self.row('희귀','봉황')
  self.assertEqual(compare(a,self.row('영웅','나비',slot=2),[]),'hold')
  self.assertEqual(compare(a,self.row('영웅','나비',verified=False),[]),'hold')
  self.assertEqual(compare(a,self.row('미확인','나비'),[]),'hold')
 def test_missing_and_duplicate_rank_rejected(self):
  self.assertEqual(collect_rank_fields(['나비','봉황','','','']),['나비','봉황'])
  with self.assertRaises(ValueError):collect_rank_fields(['나비','','봉황','',''])
  with self.assertRaises(ValueError):collect_rank_fields(['나비','나비','','',''])

if __name__=='__main__':unittest.main()
