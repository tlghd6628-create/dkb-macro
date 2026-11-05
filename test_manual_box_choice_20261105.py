"""The 요령서 box choice, without a game: settings, the split and the record. Not a real box opening."""
import json
import tempfile
import unittest
from pathlib import Path

import bootstrap  # noqa: F401
from owner_skill_box import MANUALS, ManualJournal, _settle_manual, manual_plan
from owner_starter_choice_candidate import Choices, manual_units


def units(**shares):
    return dict(dict.fromkeys(MANUALS, 0), **shares)


class Settings(unittest.TestCase):
    def test_nothing_chosen_opens_nothing(self):
        self.assertEqual(manual_units({}), {})
        self.assertEqual(manual_units({'manual_percentages': None}), {})

    def test_the_old_single_choice_does_not_count(self):
        self.assertEqual(manual_units({'manual': '파멸'}), {})

    def test_shares_must_total_100(self):
        self.assertEqual(manual_units({'manual_percentages': {'파멸': '50', '강타': '50'}})['파멸'], 5000)
        with self.assertRaises(ValueError):
            manual_units({'manual_percentages': {'파멸': '60', '강타': '50'}})

    def test_an_unknown_manual_is_refused(self):
        with self.assertRaises(ValueError):
            manual_units({'manual_percentages': {'파멸': '100', '없는것': '0'}})

    def test_a_missing_file_has_no_manual(self):
        with tempfile.TemporaryDirectory() as root:
            data, _ = Choices(root, 'profile').snapshot()
            self.assertEqual(manual_units(data), {})


class Split(unittest.TestCase):
    def test_even_split(self):
        self.assertEqual(manual_plan(10, units(파멸=5000, 강타=5000), {}), {'강타': 5, '파멸': 5})

    def test_a_ratio(self):
        self.assertEqual(manual_plan(10, units(파멸=7000, 강타=3000), {}), {'강타': 3, '파멸': 7})

    def test_what_was_opened_counts(self):
        self.assertEqual(manual_plan(5, units(파멸=5000, 강타=5000), {'파멸': 5}), {'강타': 5})

    def test_one_box_at_a_time_comes_out_even(self):
        ratio, opened = units(파멸=5000, 강타=5000), {}
        for _ in range(10):
            name, = manual_plan(1, ratio, opened)
            opened[name] = opened.get(name, 0) + 1
        self.assertEqual(opened, {'강타': 5, '파멸': 5})

    def test_nothing_chosen_or_no_box(self):
        self.assertEqual(manual_plan(10, units(), {}), {})
        self.assertEqual(manual_plan(0, units(파멸=10000), {}), {})


class Record(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = ManualJournal(self.temp.name, 'character')
        self.state = self.journal.read()
        self.state['pending'] = {'name': '파멸', 'amount': 5, 'boxes_before': 10}

    def test_the_count_dropping_proves_it(self):
        _settle_manual(self.journal, self.state, 5)
        saved = json.loads(Path(self.journal.path).read_text(encoding='utf8'))
        self.assertEqual((saved['opened'], saved['pending']), ({'파멸': 5}, None))

    def test_an_unchanged_count_opened_nothing(self):
        _settle_manual(self.journal, self.state, 10)
        self.assertEqual(self.state['opened'], {})

    def test_any_other_count_stops(self):
        from owner_skill_goal import Pending
        with self.assertRaises(Pending):
            _settle_manual(self.journal, self.state, 7)


if __name__ == '__main__':
    unittest.main()
