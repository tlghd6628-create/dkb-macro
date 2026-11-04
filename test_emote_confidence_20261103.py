"""Fresh title/stage evidence must retain the established OCR confidence gate."""
import unittest
import bootstrap
from owner_emote_requirements import stage_of

class Confidence(unittest.TestCase):
 def test_low_confidence_stage_does_not_authorize_packaged_quest(self):
  for score in (0,.5,.949):
   self.assertIsNone(stage_of([{'text':'[외전] 항아리를 옮긴 자 8','score':score}]))
 def test_missing_confidence_is_not_proof(self):
  self.assertIsNone(stage_of([{'text':'[외전] 항아리를 옮긴 자 8'}]))
 def test_confident_stage_agreement(self):
  self.assertEqual(stage_of([{'text':'[외전] 항아리를 옮긴 자 8','score':.95}]),'8')
 def test_conflicting_confident_stages_are_unverified(self):
  self.assertIsNone(stage_of([{'text':'항아리 8','score':.99},{'text':'항아리 9','score':.99}]))

if __name__=='__main__':unittest.main()
