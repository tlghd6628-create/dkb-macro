"""Callback reentry tests; no UI/game input and no resource operation."""
import bootstrap
import unittest
from unittest.mock import Mock,patch
import owner_task_flow as flow
import owner_mission_controller as mission
import owner_timetable as timetable

class Ownership(unittest.TestCase):
 def setUp(self):
  self.before=getattr(flow.LOCAL,'servicing',False);flow.LOCAL.servicing=True
 def tearDown(self):flow.LOCAL.servicing=self.before
 def test_nested_dispatch_does_not_take_or_modify_pending_work(self):
  original=Mock()
  with patch.object(flow,'pending',side_effect=AssertionError('queue must not be touched')):
   self.assertFalse(flow.dispatch(object(),object(),original))
  original.assert_not_called()
 def test_quest_callback_does_not_start_a_second_service(self):
  self.assertFalse(mission.safe_jobs(object(),object(),object()))
 def test_b_teleport_is_blocked_while_another_menu_owns_input(self):
  with patch('owner_movement.travel',side_effect=AssertionError('no B during service')):
   self.assertFalse(mission.teleport(object()))
 def test_idle_callback_does_not_touch_planner_while_servicing(self):
  with patch.object(timetable,'planner',side_effect=AssertionError('no nested appointment')):
   self.assertFalse(timetable.idle_once(object(),object(),object()))
 def test_normal_teleport_still_uses_existing_guarded_path(self):
  flow.LOCAL.servicing=False
  with patch('owner_movement.travel',return_value=True) as travel:
   target=object();self.assertTrue(mission.teleport(target));travel.assert_called_once_with(target)

if __name__=='__main__':unittest.main()
