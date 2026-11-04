"""Actual saved inventory pair and a repeated growth frame; no game input."""
import sys,unittest
from pathlib import Path
from PIL import Image
import numpy as np
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native
from owner_gear_priority_candidate import priority_indices

class Tests(unittest.TestCase):
    def frame(self,name):return np.asarray(Image.open(Path(__file__).parent/'live_fixtures'/name).convert('RGB').crop((1,31,898,510))).copy()
    def test_actual_pair_and_one_growth_frame_match_three_priority_icons(self):
        a=self.frame('inventory_worn_1.jpg');b=self.frame('inventory_worn_2.jpg');growth=self.frame('gear_list_20261101.jpg')
        detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES));rows=native.inspect_growth_equipment(detector,growth)
        out=priority_indices((a,b),(growth,growth),rows,{'무기':True,'팔찌':True,'반지':True})
        self.assertEqual(out,{'무기':1,'팔찌':9,'반지':8})
    def test_unverified_slot_never_selected_as_priority(self):
        a=self.frame('inventory_worn_1.jpg');growth=self.frame('gear_list_20261101.jpg')
        detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES));rows=native.inspect_growth_equipment(detector,growth)
        out=priority_indices((a,a),(growth,growth),rows,{'무기':False,'팔찌':None,'반지':True})
        self.assertEqual(out,{'반지':8})
    def test_actual_inventory_pair_and_independent_native_growth_pair(self):
        a=self.frame('inventory_worn_1.jpg');b=self.frame('inventory_worn_2.jpg')
        folder=Path(__file__).parent/'live_fixtures'
        first=np.asarray(Image.open(folder/'gear_list_native_1.png').convert('RGB')).copy()
        second=np.asarray(Image.open(folder/'gear_list_native_2.png').convert('RGB')).copy()
        detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES))
        rows=native.inspect_growth_equipment(detector,first)
        self.assertEqual(priority_indices((a,b),(first,second),rows,{'무기':True,'팔찌':True,'반지':True}),{'무기':1,'팔찌':9,'반지':8})
    def test_all_four_native_png_frames_with_real_equipped_badges(self):
        import owner_equipment_boxes as boxes
        folder=Path(__file__).parent/'live_fixtures'
        def load(n):return np.asarray(Image.open(folder/n).convert('RGB')).copy()
        a,b=load('inventory_worn_native_1.png'),load('inventory_worn_native_2.png')
        first,second=load('gear_list_native_1.png'),load('gear_list_native_2.png')
        assets=[np.asarray(Image.open(p).convert('RGB')) for p in sorted((bootstrap.A.parent.parent/'owner/assets').glob('equipped_badge_*.png'))]
        self.assertTrue(assets)
        with patch.object(boxes,'badge',return_value=assets):verified=boxes.agree(a,b)
        self.assertTrue(all(verified.get(p) is True for p in ('무기','팔찌','반지')))
        detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES));rows=native.inspect_growth_equipment(detector,first)
        self.assertEqual(priority_indices((a,b),(first,second),rows,verified),{'무기':1,'팔찌':9,'반지':8})

if __name__=='__main__':unittest.main()
