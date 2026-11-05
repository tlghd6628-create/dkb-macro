"""Main quest gate text, without a game: parsing only, not a real run."""
import unittest
import bootstrap
from owner_mission_policy import QuestBook, normalize
from owner_mission_ui import side_story_gate


class Gate(unittest.TestCase):
    def test_a_side_story_objective_names_the_story(self):
        self.assertEqual(side_story_gate("임무 목표 외전 '기묘리의 방랑 도사' 완료하기"), normalize('기묘리의 방랑 도사'))

    def test_ordinary_objectives_are_not_gates(self):
        self.assertIsNone(side_story_gate('임무 목표 해월과 대화하기'))
        self.assertIsNone(side_story_gate('임무 목표 요귀 처치 10/10 완료 보상'))


class Chapter(unittest.TestCase):
    def book(self, **blocks):
        book = QuestBook.__new__(QuestBook)
        book.item = {'quests': {key: {'block': block} for key, block in blocks.items()}}
        book.commit = lambda: None
        return book

    def test_an_earlier_chapter_no_longer_holds(self):
        book = self.book(a={'reason': 'condition', 'detail': '실행 조건 [3장] 관청 병사의 전인 임무 완료 후'})
        self.assertTrue(book.chapter_reached(4))
        self.assertNotIn('block', book.item['quests']['a'])

    def test_the_current_chapter_still_holds(self):
        book = self.book(a={'reason': 'condition', 'detail': '[4장] 어떤 임무 완료 후'})
        self.assertFalse(book.chapter_reached(4))

    def test_other_holds_stay(self):
        book = self.book(a={'reason': 'death', 'detail': '[3장]'}, b={'reason': 'condition', 'detail': '[3장]', 'functional_hold': True}, c={'reason': 'condition', 'detail': '승천의 탑 10층'})
        self.assertFalse(book.chapter_reached(4))


if __name__ == '__main__':
    unittest.main()
