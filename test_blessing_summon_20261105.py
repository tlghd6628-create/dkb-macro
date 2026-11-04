"""Saved real frames with the real detector. No game input."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_image_scope as scope

LIVE=Path(__file__).resolve().parent/'image_scope_20261104/live'
NAMES=['버튼_가호_즉시확인','버튼_가호_소환_나가기']
def frame(name):return np.array(Image.open(LIVE/name).convert('RGB'))

@unittest.skipUnless((LIVE/'summon_before.png').exists(),'saved screens are local to the first PC')
class Summon(unittest.TestCase):
    def setUp(self):self.d=RoiDetector(bootstrap.A/'profiles/DKB',NAMES)
    def test_result_screen_gets_a_margin_press(self):
        hit=scope.summon_already_shown(self.d,NAMES[0],frame('summon_before.png'))
        self.assertEqual(hit[:2],(850,440))
    def test_summon_tab_without_results_gets_nothing(self):
        self.assertIsNone(scope.summon_already_shown(self.d,NAMES[0],frame('summon_after.png')))
    def test_other_names_are_untouched(self):
        self.assertIsNone(scope.summon_already_shown(self.d,NAMES[1],frame('summon_before.png')))

if __name__=='__main__':unittest.main()
