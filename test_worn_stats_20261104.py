"""Reading all worn gear. A real inventory for the badges, fakes for the rest. Never a game test."""
import sys,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_worn_stats as w
import owner_equipment_boxes as boxes

F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))

class Badges(unittest.TestCase):
    def test_every_worn_slot_shows_worn_on_the_real_inventory(self):
        boxes.badge.cache_clear()
        found=boxes.inspect(load('worn_inventory'))
        self.assertEqual({k:v for k,v in found.items() if v is not True},{})
    def test_grey_tiles_are_included(self):
        boxes.badge.cache_clear()
        found=boxes.inspect(load('worn_inventory'))
        self.assertIs(found['목걸이'],True);self.assertIs(found['귀걸이'],True)

class Stale(unittest.TestCase):
    def table(self,**slots):
        rows={}
        for slot,(values,age) in slots.items():rows['worn-slot:'+slot]={'slot':slot,'values':values,'at_epoch':1000000-age}
        return {'equipment':rows}
    def run_it(self,**slots):
        with patch('owner_growth_current.display_snapshot',return_value=self.table(**slots)):
            return w.stale_slots('r','p',now=1000000)
    FULL={'enhance':50,'opening':5,'breakthrough':3,'awaken':1}
    def test_nothing_read_means_every_slot(self):
        self.assertEqual(set(self.run_it()),set(boxes.SLOTS))
    def test_a_full_recent_reading_is_fresh(self):
        self.assertNotIn('무기',self.run_it(무기=(self.FULL,60)))
    def test_a_partial_reading_is_stale(self):
        self.assertIn('반지',self.run_it(반지=({'enhance':50,'opening':5},60)))
    def test_an_old_reading_is_stale(self):
        self.assertIn('무기',self.run_it(무기=(self.FULL,w.STALE_SECONDS+1)))
    def test_a_reading_of_zero_counts(self):
        self.assertNotIn('무기',self.run_it(무기=({'enhance':0,'opening':0,'breakthrough':0,'awaken':0},60)))

class Refresh(unittest.TestCase):
    def setUp(self):
        self.adapter=S(project=S(root='r'));self.context=object()
        for p in (patch('owner_hunt_rules_candidate.configured_identity',return_value='p'),):p.start();self.addCleanup(p.stop)
    def test_once_per_start(self):
        with patch.object(w,'stale_slots',return_value=['무기']),patch.object(w,'inspect_equipped') as read:
            self.assertTrue(w.refresh_when_stale(self.adapter,self.context,None))
            self.assertFalse(w.refresh_when_stale(self.adapter,self.context,None))
        read.assert_called_once()
    def test_nothing_stale_opens_nothing(self):
        with patch.object(w,'stale_slots',return_value=[]),patch.object(w,'inspect_equipped') as read:
            self.assertFalse(w.refresh_when_stale(self.adapter,self.context,None))
        read.assert_not_called()
    def test_a_failure_never_stops_the_hunt(self):
        with patch.object(w,'stale_slots',return_value=['무기']),patch.object(w,'inspect_equipped',side_effect=RuntimeError('x')):
            self.assertFalse(w.refresh_when_stale(self.adapter,self.context,None))
    def test_a_stop_still_passes_through(self):
        class Stop(BaseException):pass
        with patch.object(w,'stale_slots',return_value=['무기']),patch.object(w,'inspect_equipped',side_effect=Stop()),self.assertRaises(Stop):
            w.refresh_when_stale(self.adapter,self.context,None)

class Settle(unittest.TestCase):
    def test_waits_for_the_closing_popup(self):
        frames=iter(['closing','closing','ready']);parts={'closing':(False,False),'ready':(True,True)}
        service=S(check=lambda:None,capture=lambda:next(frames));context=S(checkpoint=lambda:None,wait=lambda s:None)
        with patch('owner_progression.inventory_parts',side_effect=lambda f:parts[f]),patch.object(w,'popup',return_value=False):
            self.assertTrue(w.settle_after_popup(service,context))
    def test_a_budget_covers_every_slot(self):
        self.assertGreaterEqual(w.FULL_SECONDS,len(boxes.SLOTS)*7)

if __name__=='__main__':unittest.main()
