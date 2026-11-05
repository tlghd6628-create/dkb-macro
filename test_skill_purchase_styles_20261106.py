"""Which skills the story's purchase step wants, without a game. Not a real purchase."""
import unittest
from unittest.mock import patch

import bootstrap  # noqa: F401
import owner_skill_goal as g

CATALOG = {'all_skill_names': {
    '화염구': {'id': 1, 'style': '파멸'}, '대폭발': {'id': 2, 'style': '파멸', 'ultimate': True},
    '내려치기': {'id': 3, 'style': '강타'}, '내려찍기': {'id': 4, 'style': '절명'},
    '암습': {'id': 5, 'style': '절명', 'ultimate': True}, '사격': {'id': 6, 'style': '저격'},
    '난타': {'id': 7, 'style': '연타'}}}


class Styles(unittest.TestCase):
    def test_all_four_styles_without_ultimates(self):
        with patch.object(g, 'catalog', return_value=CATALOG):
            self.assertEqual(g.desired_learning_ids(), {1, 3, 4, 6})


if __name__ == '__main__':
    unittest.main()
