"""Purple pillars and floor join the boss danger mask. Synthetic pixels; never a game test."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np,cv2
import owner_boss_purple as p


def rgb_of(h,s,v):return cv2.cvtColor(np.uint8([[[h,s,v]]]),cv2.COLOR_HSV2RGB)[0,0]


class Purple(unittest.TestCase):
    def test_pillar_and_floor_colours(self):
        img=np.zeros((100,100,3),np.uint8);img[:10]=rgb_of(140,120,240);img[20:30]=rgb_of(135,200,90);img[40:50]=rgb_of(60,200,200)
        pillar,floor=p.purple(img)
        self.assertTrue(pillar[:10].mean()>.9);self.assertTrue(floor[20:30].mean()>.9)
        self.assertFalse(pillar[40:50].any() or floor[40:50].any())
    def test_merged_keeps_the_mask_type(self):
        extra=np.zeros((4,4),bool);extra[0,0]=True
        self.assertTrue(p.merged(np.zeros((4,4),bool),extra)[0,0])
        self.assertEqual(p.merged(np.zeros((4,4),np.uint8),extra)[0,0],1)
        m=np.zeros((4,4),np.uint8);m[1,1]=255;self.assertEqual(p.merged(m,extra)[0,0],255)
        self.assertIs(p.merged(m,np.zeros((3,3),bool)),m)
    def test_pillars_mark_the_feet(self):
        from project_adapter.boss_floor import BossFloorAnalyzer
        original=BossFloorAnalyzer.danger_mask
        try:
            BossFloorAnalyzer.danger_mask=lambda self,rgb,hsv=None:np.zeros(rgb.shape[:2],bool)
            p.install();img=np.zeros((479,897,3),np.uint8);img[120:300,300:330]=rgb_of(140,120,240)
            mask=BossFloorAnalyzer.danger_mask(object.__new__(BossFloorAnalyzer),img)
            self.assertTrue(mask[250,448]);self.assertTrue(mask[200,310])
        finally:BossFloorAnalyzer.danger_mask=original
    def test_installed_on_the_native_analyzer(self):
        from project_adapter.boss_floor import BossFloorAnalyzer
        original=BossFloorAnalyzer.danger_mask
        try:
            p.install();self.assertTrue(BossFloorAnalyzer.danger_mask._owner_purple)
        finally:BossFloorAnalyzer.danger_mask=original


if __name__=='__main__':unittest.main()
