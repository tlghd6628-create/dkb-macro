"""The potion story at the coin floor, without a game: it waits and nothing is bought. Not a real purchase."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

import bootstrap  # noqa: F401
import owner_quest_purchase as q


def scene():
    book = Mock()
    book.item = {'active': 'k', 'quests': {'k': {'mode': 'sub_quest', 'group': True, 'title': '메마른 늪', 'completed': False}}}
    adapter = S(project=S(root='.'), run_potion_purchase=Mock(), _owner_potion_full_at=0)
    return S(adapter=adapter, context=Mock(), inputs=Mock(), frame=Mock(), close_known=Mock(), normal=Mock(return_value=True), service=Mock()), book


class Floor(unittest.TestCase):
    def test_at_the_floor_the_story_waits_before_the_trip(self):
        ui, book = scene()
        with patch.object(q, 'observe_stage', return_value={'stage': 2, 'done': 0}), patch('owner_coin_reserve.can_spend', return_value=False):
            self.assertTrue(q.execute(ui, book, 'k'))
        book.defer.assert_called_once()
        ui.adapter.run_potion_purchase.assert_not_called()
        ui.close_known.assert_not_called()

    def test_the_buy_press_is_refused_before_it_is_recorded(self):
        ui, _ = scene()
        receipt = {'phase': 'preflight'}
        commit = Mock()
        with patch('owner_coin_reserve.can_spend', return_value=False):
            with q.native_purchase_watch(ui.adapter, ui.context, ui, receipt, commit, Mock(return_value=True)):
                from project_adapter.town_services import TownServices
                with self.assertRaises(q.NoCoins):
                    TownServices.button(S(context=ui.context), '버튼_물약상인_구매')
        self.assertEqual(receipt['phase'], 'preflight')
        commit.assert_not_called()

    def test_above_the_floor_it_goes_on(self):
        ui, _ = scene()
        with patch('owner_coin_reserve.can_spend', return_value=True):
            self.assertTrue(q.coins_allow(ui))


if __name__ == '__main__':
    unittest.main()
