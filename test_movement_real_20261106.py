"""Quest auto-move teleport at 1366 by the bar's words. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_movement as m


class Bar(unittest.TestCase):
    def read(self,words):return patch('owner_text.read',return_value=[dict(text=w) for w in words])
    def test_words_and_distance(self):
        with self.read(['자동 이동 중','895m','B']):self.assertEqual(m.real_moving(NS(hi=1)),895)
        with self.read(['자동 이동 중','895m']):self.assertIsNone(m.real_moving(NS(hi=1)))
        with self.read(['895m','B']):self.assertIsNone(m.real_moving(NS(hi=1)))
    def test_far_presses_b_near_does_not(self):
        keys=[]
        ui=NS(frame=lambda:NS(hi=1),context=NS(wait=lambda s:None),key=keys.append,wait=lambda *a,**k:None)
        with patch.object(m,'choice',return_value=False),patch.object(m,'real_moving',side_effect=[895,880]),patch.object(m,'confirm_choice',return_value=True):
            self.assertTrue(m.travel(ui))
        self.assertEqual(keys,[0x42])
        keys.clear()
        with patch.object(m,'choice',return_value=False),patch.object(m,'real_moving',side_effect=[120,110]):
            self.assertFalse(m.travel(ui))
        self.assertEqual(keys,[])


if __name__=='__main__':unittest.main()
