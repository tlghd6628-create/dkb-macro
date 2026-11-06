"""One shop item a game day. Temporary folder; never a game test."""
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_shop_runtime_candidate as s


class Day(unittest.TestCase):
    def test_marked_today_then_not_tomorrow(self):
        with tempfile.TemporaryDirectory() as root:
            day=datetime(2026,11,6,12,0)
            with patch('owner_timetable.now',return_value=day):
                self.assertIsNone(s._shop_day(root,'p'))
                s._mark_shop_day(root,'p','영웅 장비 강화 비법서')
                self.assertEqual(s._shop_day(root,'p'),'영웅 장비 강화 비법서')
                self.assertIsNone(s._shop_day(root,'other'))
            with patch('owner_timetable.now',return_value=datetime(2026,11,7,12,0)):
                self.assertIsNone(s._shop_day(root,'p'))


if __name__=='__main__':unittest.main()
