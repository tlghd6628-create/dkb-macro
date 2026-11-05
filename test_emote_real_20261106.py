"""The emote panel on the real screen, with stand-in words. Not a game test."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch

import numpy as np

import bootstrap  # noqa: F401
import owner_emote_dispatch as d
import owner_quest_emote_candidate as q


def frame():
    f = np.zeros((479, 897, 3), dtype=np.uint8).view(type('F', (np.ndarray,), {}))
    f.hi = np.zeros((768, 1366, 3), dtype=np.uint8)
    f.layout = None
    return f


class Panel(unittest.TestCase):
    def test_empty_input_allows_a_caret(self):
        f = frame()
        self.assertTrue(q.empty_chat(f))
        f.hi[730:745, 94] = 255
        self.assertTrue(q.empty_chat(f))

    def test_typed_text_is_not_empty(self):
        f = frame()
        f.hi[730:745, 100:180] = 255
        self.assertFalse(q.empty_chat(f))

    def rows(self, *words):
        return [{'text': t, 'rx': x, 'ry': y, 'score': .9} for t, x, y in words]

    def test_a_card_is_found_in_a_panel_column(self):
        with patch('owner_text.read_area', lambda *a, **k: self.rows(('웃음', 449, 594), ('놀람', 448, 687))):
            self.assertIsNotNone(d.real_card(frame(), '놀람'))
            self.assertIsNone(d.real_card(frame(), '화남'))

    def test_scenery_words_are_not_cards(self):
        with patch('owner_text.read_area', lambda *a, **k: self.rows(('화남', 676, 562))):
            self.assertIsNone(d.real_card(frame(), '화남'))

    def test_two_looks_at_a_still_card_agree(self):
        with patch('owner_text.read_area', lambda *a, **k: self.rows(('놀람', 448, 687))):
            first = d.real_card(frame(), '놀람')
        with patch('owner_text.read_area', lambda *a, **k: self.rows(('놀람', 450, 688))):
            self.assertEqual(first, d.real_card(frame(), '놀람'))


if __name__ == '__main__':
    unittest.main()
