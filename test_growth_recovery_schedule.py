from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
import unittest
import owner_timetable as t

class Tests(unittest.TestCase):
 def test_receipt_only_reaches_native_without_planner_or_attempt_changes(self):
  adapter=NS(_owner_growth_reconcile_only=True)
  call=Mock(return_value='receipt-only')
  with patch.object(t,'planner',side_effect=AssertionError('timed attempt touched')):
   self.assertEqual(t.scheduled_call(call,'성장 장비·가호',('a',),{'proof':True},adapter),'receipt-only')
  call.assert_called_once_with('a',proof=True)
 def test_normal_growth_still_uses_existing_retry_fence(self):
  adapter=NS(_owner_growth_reconcile_only=False,project=NS(root=Path('unused')),mode='sub_quest')
  plan=NS(state={'gear':{}},values={'auto_growth.equipment.enabled':True},reason=lambda key:'retry limit')
  call=Mock()
  with patch.object(t,'planner',return_value=plan),patch.object(t,'config',return_value={}),patch.object(t,'enabled',return_value=True):
   self.assertIs(t.scheduled_call(call,'성장 장비·가호',(),{},adapter),True)
  call.assert_not_called()
if __name__=='__main__':unittest.main()
