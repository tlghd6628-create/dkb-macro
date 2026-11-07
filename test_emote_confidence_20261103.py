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

class Pieces(unittest.TestCase):
    def test_a_heading_read_in_pieces(self):
        """짱군네 15:09: '[외전]', '산길의', '|호환10' (.937) apart."""
        import owner_emote_requirements as r
        rows=[{'text':'[외전]','score':.998,'rx':700},{'text':'산길의','score':.996,'rx':740},{'text':'|호환10','score':.937,'rx':790}]
        self.assertEqual(r.stage_of(rows),'10');self.assertTrue(r.quest_id(rows).endswith('|10'))
        rows[2]['score']=.9;self.assertIsNone(r.stage_of(rows))

if __name__=='__main__':unittest.main()
