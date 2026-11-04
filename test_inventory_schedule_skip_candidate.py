import bootstrap
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_timetable as timetable,owner_schedule_priority as priority

class InventoryScheduleSkip(unittest.TestCase):
 def test_timetable_hold_returns_native_success_and_marks_skip(self):
  adapter=NS(project=NS(root='x'),values={},mode='auto_mode')
  plan=NS(state={'inventory':{}},values={},reason=lambda key:'나중에 실행')
  with patch.object(timetable,'planner',return_value=plan),patch.object(timetable,'config',return_value={}),patch.object(timetable,'enabled',return_value=True):
   self.assertIs(timetable.scheduled_call(lambda: self.fail('called'), '인벤토리 사용',(),{},adapter),True)
  self.assertEqual(adapter._owner_inventory_skip_generation,1)
 def test_boss_hold_returns_native_success_and_marks_skip(self):
  adapter=NS(project=NS(root='x'),values={})
  with patch.object(priority,'hold_reason',return_value='보스 대기'):
   self.assertIs(priority.service_wrapper(lambda *_:self.fail('called'),'인벤토리 사용')(adapter),True)
  self.assertEqual(adapter._owner_inventory_skip_generation,1)

if __name__=='__main__':unittest.main()
