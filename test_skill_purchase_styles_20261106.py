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
    def test_three_styles_without_ultimates(self):
        # User 11-06: 절명 has no merchant; 저격, 파멸 and 강타 are bought.
        with patch.object(g, 'catalog', return_value=CATALOG):
            self.assertEqual(g.desired_learning_ids(), {1, 3, 6})


class LearnAll(unittest.TestCase):
    """Stand-in screen: the button shows twice, then is gone."""

    def test_pressed_until_the_button_is_gone(self):
        from types import SimpleNamespace as S
        from owner_skill_ui import SkillUI, Pending
        calls, shown = [], [True, True, False]

        def word(text, box, minimum=.9):
            if shown.pop(0):
                return {'x': 1, 'y': 2}
            raise Pending('gone')
        ui = S(open_skills=lambda: calls.append('open'), context=S(checkpoint=lambda: None, wait=lambda s: None), word=word,
               click=lambda x, y, proof: calls.append('button'), click_word=lambda text, box, proof, minimum=.9: calls.append(text))
        self.assertEqual(SkillUI.learn_all(ui), 2)
        self.assertEqual(calls, ['open', 'button', '확인', 'button', '확인'])


if __name__ == '__main__':
    unittest.main()
