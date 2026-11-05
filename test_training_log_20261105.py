"""Training log score text, without a game: parsing only, not a real run."""
import unittest
import bootstrap
from owner_training_log import FIRST_REWARD, parse_score


class Score(unittest.TestCase):
    def test_the_label_and_thousands_are_handled(self):
        self.assertEqual(parse_score('전체 누적 점수:1,306점'), 1306)
        self.assertEqual(parse_score('전체 누적 점수 : 90점'), 90)

    def test_a_row_without_the_unit_is_not_a_score(self):
        self.assertIsNone(parse_score('전체 누적 점수'))

    def test_first_reward_matches_the_game_screen(self):
        self.assertEqual(FIRST_REWARD, 8000)


if __name__ == '__main__':
    unittest.main()
