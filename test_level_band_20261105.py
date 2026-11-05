"""Level-band choice, without a game: this is the rule only, not a real run at those levels."""
import bootstrap,tempfile,unittest
from pathlib import Path
from owner_progression import Progress


class Band(unittest.TestCase):
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
  (Path(self.dir.name)/'settings').mkdir()
  self.p=Progress(self.dir.name);self.p.accept(1,1000,'c')
 def at(self,level):self.p.accept(level,1000,'c');return self.p.due()
 def test_below_the_first_band_nothing_is_due(self):self.assertIsNone(self.at(19))
 def test_each_band_on_its_own(self):
  for level,band in ((20,20),(30,30),(40,40),(45,45)):
   self.assertEqual(self.at(level),band);self.p.attempted(band)
   self.assertIsNone(self.p.due())
 def test_a_skipped_band_is_caught_by_the_highest_passed(self):
  self.assertEqual(self.at(33),30);self.p.attempted(30)
  self.assertIsNone(self.p.due())
  self.assertEqual(self.at(47),45)
 def test_nothing_is_marked_until_attempted(self):
  self.assertEqual(self.at(33),30);self.assertEqual(self.at(33),30)


if __name__=='__main__':unittest.main()
