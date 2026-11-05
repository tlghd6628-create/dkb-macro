"""Main quest gate text, without a game: parsing only, not a real run."""
import unittest
import bootstrap
from owner_mission_policy import normalize
from owner_mission_ui import side_story_gate


class Gate(unittest.TestCase):
    def test_a_side_story_objective_names_the_story(self):
        self.assertEqual(side_story_gate("임무 목표 외전 '기묘리의 방랑 도사' 완료하기"), normalize('기묘리의 방랑 도사'))

    def test_ordinary_objectives_are_not_gates(self):
        self.assertIsNone(side_story_gate('임무 목표 해월과 대화하기'))
        self.assertIsNone(side_story_gate('임무 목표 요귀 처치 10/10 완료 보상'))


if __name__ == '__main__':
    unittest.main()
