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


if __name__ == '__main__':
    unittest.main()
