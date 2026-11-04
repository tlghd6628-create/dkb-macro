"""Saved-frame checks only; no live game or actual input."""
import sys,unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
import project_adapter.market_inventory as native
from owner_gear_resource_candidate import NativeResources


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names=[native.GROWTH_EQUIPMENT_TAB,*native.GROWTH_EXEC_BUTTONS,native.GROWTH_MATERIAL_RANGE]
        cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',names);cls.probe=NativeResources(native,cls.detector)
        cls.root=bootstrap.A/'logs/scene-corpus/20261101'
    def frame(self,id):return np.asarray(Image.open(self.root/id/'screen.png').convert('RGB')).copy()
    def test_bright_and_dimmed_button_distinguished(self):
        active=self.probe(self.frame('20261101T162242-cdf1cd68'))
        self.assertTrue(active['verified']);self.assertEqual(active['mode'],'native_active');self.assertIsNone(active['balance'])
        self.assertFalse(self.probe(self.frame('20261101T162244-75f3203c'))['verified'])
    def test_other_tab_does_not_authorize(self):
        raw=Image.open(Path(__file__).parent/'live_fixtures/blessing_growth_20261101.jpg').convert('RGB')
        self.assertFalse(self.probe(np.asarray(raw.crop((1,31,898,510))).copy())['verified'])
    def test_enabled_button_does_not_depend_on_material_counter(self):
        with patch.object(native,'inspect_growth_materials',side_effect=AssertionError('material OCR is not permission')):
            result=self.probe(self.frame('20261101T162242-cdf1cd68'))
        self.assertTrue(result['verified']);self.assertTrue(result['active'])
        self.assertIsNone(result['materials'])
    def test_saved_19_to_20_opening_has_different_button_and_no_material_counter(self):
        frame=self.frame('20261101T012807-18a28cf8')
        opening=self.probe(frame)
        self.assertTrue(opening['verified']);self.assertTrue(opening['opening'])
        self.assertEqual(opening['button_name'],native.GROWTH_EXEC_BUTTONS[1])
        self.assertNotEqual(native.inspect_growth_materials(self.detector,frame).get('status'),'재료 충분')

if __name__=='__main__':unittest.main()
