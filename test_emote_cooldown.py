import tempfile,unittest
from pathlib import Path
from owner_emote_cooldown import Rate,Pending

class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.now=1000.
 def rate(self,char='one'):return Rate(self.root,'scope',char,clock=lambda:self.now)
 def test_restart_preserves_limit_and_sixty_seconds_is_not_enough(self):
  self.rate().reserve('quest','smile');self.now+=60
  self.assertEqual(self.rate().remaining(),1)
  with self.assertRaises(Pending):self.rate().reserve('quest','smile')
  self.now+=1;self.rate().reserve('quest','smile');self.assertEqual(self.rate().attempts('quest'),2)
 def test_limit_shared_by_all_emotes_for_same_character(self):
  self.rate().reserve('first','smile')
  with self.assertRaises(Pending):self.rate().reserve('other','sleep')
  self.rate('two').reserve('first','smile')
 def test_attempts_are_bounded_without_claiming_completion(self):
  for _ in range(3):self.rate().reserve('quest','smile');self.now+=61
  with self.assertRaises(Pending):self.rate().reserve('quest','smile')
  self.assertEqual(self.rate().read()[1]['requests']['quest']['phase'],'input_intent_unverified')
 def test_backwards_clock_and_corruption_hold(self):
  self.rate().reserve('quest','smile');self.now-=60
  with self.assertRaises(Pending):self.rate().remaining()
  self.rate().path.write_text('broken',encoding='utf8')
  with self.assertRaises(Pending):self.rate().remaining()

if __name__=='__main__':unittest.main()
