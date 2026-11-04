import sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from owner_blessing_equip_candidate import read_worn_detail,_single_detail_controls

class Tests(unittest.TestCase):
 def test_two_real_worn_frames(self):
  folder=Path(__file__).parent/'live_fixtures'
  for n in (1,2):
   frame=np.asarray(Image.open(folder/f'blessing_worn_filter1_native_{n}.png').convert('RGB')).copy()
   self.assertEqual(read_worn_detail(bootstrap.A,frame),{'pattern':'토끼','slot':1,'grade':'희귀','verified':True})
   frame[120:131,427:438]=0
   self.assertIsNone(_single_detail_controls(frame))
if __name__=='__main__':unittest.main()
