import json,os,sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import owner_gear_hold_capture_candidate as target

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
  self.frame=np.zeros((479,897,3),dtype=np.uint8)
 def test_background_save_and_five_minute_dedup(self):
  self.assertTrue(target.enqueue(self.temp.name,'pending','동일 장비 미확인',(self.frame,self.frame),clock=lambda:1000.))
  self.assertFalse(target.enqueue(self.temp.name,'pending','동일 장비 미확인',(self.frame,),clock=lambda:1100.))
  target._queue.join();folders=list((Path(self.temp.name)/'logs/gear-holds').iterdir());self.assertEqual(len(folders),1)
  info=json.loads((folders[0]/'hold.json').read_text(encoding='utf8'));self.assertEqual(info['frame_count'],2)
  self.assertTrue((folders[0]/'1.png').is_file());self.assertTrue((folders[0]/'2.png').is_file())
  self.assertTrue(target.enqueue(self.temp.name,'pending','동일 장비 미확인',(self.frame,),clock=lambda:1301.));target._queue.join()
 def test_invalid_frames_never_queued(self):
  self.assertFalse(target.enqueue(self.temp.name,'x','y',(np.zeros((5,5,3),dtype=np.uint8),)))
 def test_existing_limit_keeps_old_evidence_and_skips_new(self):
  from unittest.mock import patch
  root=Path(self.temp.name)/'logs/gear-holds';root.mkdir(parents=True)
  (root/'existing.dat').write_bytes(b'x'*50)
  with patch.object(target,'MAX_BYTES',100):self.assertFalse(target._write(self.temp.name,'x','y',(self.frame,)))
  self.assertEqual((root/'existing.dat').read_bytes(),b'x'*50)
if __name__=='__main__':unittest.main()
