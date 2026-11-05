"""Training log words, without a game: parsing and choosing only, not a real run."""
import unittest
import bootstrap
import numpy as np
from owner_training_log import ICON_LEFT, ICON_RIGHT, has_red_dot, parse_score, reward_rows, score_of, to_claim


def word(text, ry=100, right=1190):
    return {'text': text, 'ry': ry, 'rx': right - 40, 'bounds': (right - 80, ry - 8, right, ry + 8)}


def real_with(lights):
    image = np.full((768, 1366, 3), 40, dtype=np.uint8)
    for height, light in lights.items():
        image[height - 27:height + 27, ICON_LEFT:ICON_RIGHT] = light
    return image


class Words(unittest.TestCase):
    def test_score(self):
        self.assertEqual(parse_score('전체 누적 점수 : 10,630점'), 10630)
        self.assertEqual(score_of([word('임무를 수행하여'), word('전체 누적 점수:1,306점')]), 1306)
        self.assertIsNone(parse_score('전체 누적 점수'))

    def test_two_scores_are_no_score(self):
        self.assertIsNone(score_of([word('누적 점수:90점'), word('누적 점수:80점')]))

    def test_steps_as_one_word_or_two(self):
        rows = [word('1단계 8,000점', 643), word('2단계', 533), word('20,000점', 533), word('보상 정보', 85)]
        self.assertEqual(reward_rows(rows), {1: (8000, 643), 2: (20000, 533)})


class Choosing(unittest.TestCase):
    rewards = {1: (8000, 643), 2: (20000, 533), 3: (40000, 423)}

    def test_a_reached_bright_icon_is_claimed(self):
        self.assertEqual(to_claim(real_with({643: 120, 533: 120, 423: 120}), self.rewards, 10630), [1])

    def test_a_paid_icon_is_left(self):
        self.assertEqual(to_claim(real_with({643: 40, 533: 120, 423: 120}), self.rewards, 10630), [])

    def test_steps_not_reached_are_left(self):
        self.assertEqual(to_claim(real_with({643: 120, 533: 120, 423: 120}), self.rewards, 2062), [])

    def test_lowest_goes_first(self):
        self.assertEqual(to_claim(real_with({643: 120, 533: 120, 423: 120}), self.rewards, 25000), [1, 2])

    def test_unread_score_claims_nothing(self):
        self.assertEqual(to_claim(real_with({643: 120}), self.rewards, None), [])


class Dot(unittest.TestCase):
    def test_red_beside_the_words(self):
        image = np.full((768, 1366, 3), 40, dtype=np.uint8)
        tab = word('누적 점수 보상', 126)
        self.assertFalse(has_red_dot(image, tab))
        image[110:118, 1192:1200] = (220, 40, 40)
        self.assertTrue(has_red_dot(image, tab))


if __name__ == '__main__':
    unittest.main()
