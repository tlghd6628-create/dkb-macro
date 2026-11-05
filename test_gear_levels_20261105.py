"""Enhance order, without a game: the rule only, not a real enhance."""
import unittest
from owner_gear_levels import STEP, ceiling_for, lowest_first


def row(index, grade='흰'):
    return {'index': index, 'grade': grade}


class Order(unittest.TestCase):
    def test_lowest_goes_first(self):
        rows = [row(2), row(3), row(4)]
        self.assertEqual([r['index'] for r in lowest_first(rows, {2: 31, 3: 5, 4: 0})], [4, 3, 2])

    def test_ties_keep_the_priority_then_the_grid(self):
        rows = [row(1), row(2), row(9)]
        self.assertEqual([r['index'] for r in lowest_first(rows, {1: 0, 2: 0, 9: 0}, {9: 0})], [9, 1, 2])

    def test_a_turn_stops_just_past_the_next_lowest(self):
        rows = [row(2), row(3), row(4)]
        self.assertEqual(ceiling_for(rows[2], rows, {2: 31, 3: 5, 4: 0}), 5 + STEP)

    def test_equal_items_take_short_turns(self):
        rows = [row(3), row(4)]
        self.assertEqual(ceiling_for(rows[0], rows, {3: 0, 4: 0}), STEP)

    def test_other_grades_do_not_set_the_limit(self):
        rows = [row(1, '파랑'), row(3)]
        self.assertIsNone(ceiling_for(rows[1], rows, {1: 0, 3: 0}))

    def test_water_fill_evens_out(self):
        levels = {2: 31, 3: 5, 4: 0, 5: 0}
        rows = [row(i) for i in levels]
        for _ in range(40):
            chosen = lowest_first(rows, levels)[0]
            levels[chosen['index']] = ceiling_for(chosen, rows, levels)
        self.assertLessEqual(max(levels.values()) - min(levels.values()), STEP)


if __name__ == '__main__':
    unittest.main()
