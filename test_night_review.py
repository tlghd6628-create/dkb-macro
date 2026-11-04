from pathlib import Path
import tempfile,unittest,sys
sys.path.insert(0,str(Path(__file__).parent))
from night_review import analyze,new_lines

class Cases(unittest.TestCase):
 def test_incremental_offsets_and_midnight_new_file(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'a.log';p.write_bytes(b'old\nnew\n')
   lines,offset,clipped=new_lines(p,4)
   # An exact line-boundary offset must keep the complete first new line.
   self.assertEqual(lines,['new']);self.assertEqual(offset,8);self.assertFalse(clipped)
   p.write_bytes(b'reset\n');self.assertEqual(new_lines(p,offset)[0],['reset'])
 def test_classification_does_not_claim_combat_or_completion(self):
  r=analyze(['ERROR bad']+['임무 판독 보류 수치1']*3)
  self.assertEqual(len(r['errors']),1);self.assertEqual(r['repeated_holds'][0]['count'],3)
  self.assertNotIn('game_alive',r);self.assertNotIn('complete',r)

if __name__=='__main__':unittest.main()
