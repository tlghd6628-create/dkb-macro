"""Clan battle start as one time. Strings only; not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import owner_clan_time as t


class Parse(unittest.TestCase):
    def test_one_time_after_the_deadline(self):
        self.assertEqual(t.parse('진행시간토요일20:28전투시작'),('토',20,28))
        self.assertEqual(t.parse('진행 시간 토요일 20:28 전투 시작'),('토',20,28))
    def test_native_answer_is_kept(self):
        self.assertEqual(t.parse('토요일20:00-20:30전투시작',lambda s:('토',20,0)),('토',20,0))
    def test_nonsense_is_none(self):
        self.assertIsNone(t.parse('신청기간매주일요일05:00부터'))
        self.assertIsNone(t.parse('토요일25:28전투시작'))
    def test_installed_over_the_native_parser(self):
        import project_adapter.clan_boss_request as native
        t.install()
        self.assertEqual(native.parse_combat_start('토요일20:00-20:30전투시작'),('토',20,0))
        self.assertEqual(native.parse_combat_start('진행시간토요일20:28전투시작'),('토',20,28))


if __name__=='__main__':unittest.main()
