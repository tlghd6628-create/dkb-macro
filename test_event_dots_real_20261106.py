"""A notification dot's holes and split parts, on a drawn array. Real screens are checked in the game, not here."""
import unittest
from types import SimpleNamespace as S

import numpy as np

import bootstrap  # noqa: F401
import owner_hd
import owner_reward_visual_guard as g


def frame_with(draw):
    real = np.full((768, 1366, 3), 70, dtype=np.uint8)
    draw(real)
    return S(hi=real, layout=owner_hd.default_layout())


def stamp(real, x, y, gap=None):
    """The real-size dot shape as red pixels, optionally with a row of its shine cutting it in two."""
    shape = g._real_dot_shape().astype('int16')
    h, w = shape.shape
    area = real[y - h // 2:y - h // 2 + h, x - w // 2:x - w // 2 + w]
    area[:, :, 0] = np.clip(70 + shape * 2, 0, 255)
    if gap is not None:
        area[h // 2 + gap, :, 0] = 70


class Dots(unittest.TestCase):
    def test_a_whole_dot_is_found(self):
        self.assertEqual(len(g.notice_dots(frame_with(lambda real: stamp(real, 913, 437)))), 1)

    def test_a_dot_cut_by_its_shine_is_one_dot(self):
        self.assertEqual(len(g.notice_dots(frame_with(lambda real: stamp(real, 913, 437, gap=0)))), 1)

    def test_a_large_red_area_is_not_a_dot(self):
        def draw(real):
            real[400:460, 880:960] = (254, 85, 57)
        self.assertEqual(g.notice_dots(frame_with(draw)), [])


class Prizes(unittest.TestCase):
    """Stand-in reader and drawn prizes. What the real panel reads as is checked in the game."""

    def run_on(self, total, column, colours):
        from unittest.mock import patch
        import owner_text
        real = np.zeros((768, 1366, 3), dtype=np.uint8)
        for y, colour in colours.items():
            real[y - 18:y + 18, 989:1025] = colour
        def read_area(root, area, *, left=0, top=0, **options):
            if left == g.POINT_TITLE[0]:
                return [{'text': '누적 포인트'}]
            if left == g.POINT_TOTAL[0]:
                return [{'text': str(total)}]
            return [{'text': str(need), 'ry': y} for need, y in column]
        with patch.object(owner_text, 'read_area', read_area):
            return g.open_prizes(S(hi=real))

    def test_earned_and_untaken_only(self):
        found = self.run_on(5, [(2, 420), (4, 483), (6, 545)], {420: 200, 483: 40, 545: 200})
        self.assertEqual(found, [(1007, 420)])

    def test_nothing_earned(self):
        self.assertEqual(self.run_on(1, [(2, 420)], {420: 200}), [])

    def test_no_real_pixels(self):
        self.assertEqual(g.open_prizes(np.zeros((479, 897, 3), dtype=np.uint8)), [])


class CutRow(unittest.TestCase):
    """The bar's brightness is drawn; what it reads as comes from a stand-in reader."""

    def run_on(self, bright, text):
        from unittest.mock import patch
        import owner_text
        real = np.zeros((768, 1366, 3), dtype=np.uint8)
        x, y, w, h = g.CUT_BAR
        real[y:y + h, x:x + w] = bright
        with patch.object(owner_text, 'read_area', lambda root, area, **o: [{'text': text}]):
            return g.cut_finished_row(S(hi=real))

    def test_bright_and_full(self):
        self.assertEqual(self.run_on(156, '200 / 200'), g.CUT_COIN)

    def test_taken_is_dimmer(self):
        self.assertIsNone(self.run_on(123, '200 / 200'))

    def test_not_finished(self):
        self.assertIsNone(self.run_on(156, '1 / 3'))


if __name__ == '__main__':
    unittest.main()
