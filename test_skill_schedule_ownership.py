"""No game input: wrapper ownership must precede any skill inspection."""
from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_skill_goal as goal
import owner_timetable as timetable

class Ownership(unittest.TestCase):
 def test_active_schedule_or_native_visit_prevents_earlier_skill_wrapper(self):
  for field in ('job','native_job'):
   with self.subTest(field=field):
    before={k:getattr(timetable.LOCAL,k,None) for k in ('job','native_job')}
    try:
     timetable.LOCAL.job=None;timetable.LOCAL.native_job=None
     setattr(timetable.LOCAL,field,'existing-job')
     adapter=S();context=S(input_depth=0);inputs=S(held=())
     with patch('owner_schedule_priority.hold_reason',return_value=None),patch('owner_progression.state',side_effect=AssertionError('nested skill inspection')):
      self.assertFalse(goal.execute(adapter,context,inputs,force=True))
     self.assertFalse(hasattr(adapter,'_owner_skill_checked'))
    finally:
     for key,value in before.items():setattr(timetable.LOCAL,key,value)

if __name__=='__main__':unittest.main()
