"""The saved list's own count adds rows the native pictures miss. Fake reads; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_town_return as m


class Count(unittest.TestCase):
    def test_count_extends_native_slots(self):
        with patch.object(m,'saved_count',return_value=3):
            self.assertEqual(m.wrap_slots(lambda *a,**k:[0,1])(NS(),None,None),[0,1,2])
    def test_unread_count_keeps_native(self):
        with patch.object(m,'saved_count',return_value=None):
            self.assertEqual(m.wrap_slots(lambda *a,**k:[0,1])(NS(),None,None),[0,1])
            with self.assertRaises(m.MissingFavorite):m.wrap_slots(lambda *a,**k:[])(NS(),None,None)
    def test_reads_n_of_ten(self):
        with patch('owner_text.read',return_value=[{'text':'3/10'}]),patch('owner_text.clean',side_effect=lambda s:s):
            self.assertEqual(m.saved_count(NS(capture=lambda:NS(hi=1))),3)
        with patch('owner_text.read',return_value=[{'text':'12/10'}]),patch('owner_text.clean',side_effect=lambda s:s):
            self.assertIsNone(m.saved_count(NS(capture=lambda:NS(hi=1))))


if __name__=='__main__':unittest.main()
