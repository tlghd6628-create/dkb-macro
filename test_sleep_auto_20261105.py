"""Saved real frames with fake actions. No game input."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
from types import SimpleNamespace as S
from unittest.mock import Mock
from roi_runtime import RoiDetector
import owner_sleep_auto as sleep

HERE=Path(__file__).resolve().parent
LIVE=HERE/'image_scope_20261104/live'
def image(path):return np.array(Image.open(path).convert('RGB'))

@unittest.skipUnless((LIVE/'spirit_return_0.png').exists(),'saved screens are local to the first PC')
class Sleep(unittest.TestCase):
    def setUp(self):
        self.d=RoiDetector(bootstrap.A/'profiles/DKB',[sleep.SLEEP,sleep.FIGHTING])
        self.context=S(wait=lambda s:None,checkpoint=lambda:None);self.original=Mock(return_value='native')
    def run_on(self,frames):
        seq=iter(frames)
        return sleep.wrap(self.original,lambda:self.d)(S(capture=lambda:next(seq)),self.context,None,post_click_wait=1)
    def test_fighting_asleep_counts_as_auto_on(self):
        f=image(LIVE/'spirit_return_0.png')
        self.assertTrue(self.run_on([f,f]));self.original.assert_not_called()
    def test_the_field_goes_to_the_native_check(self):
        f=image(HERE/'fixtures_image_scope/hunt_field.png')
        self.assertEqual(self.run_on([f]),'native');self.original.assert_called_once()
    def test_one_lone_frame_is_not_enough(self):
        a=image(LIVE/'spirit_return_0.png');b=image(HERE/'fixtures_image_scope/hunt_field.png')
        self.assertEqual(self.run_on([a,b]),'native')
    def test_no_capture_keeps_the_native_path(self):
        self.assertEqual(sleep.wrap(self.original,lambda:self.d)(S(),self.context,None),'native')

if __name__=='__main__':unittest.main()
