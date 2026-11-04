"""Send result may be a dialogue, not a field; mocked inputs only."""
import json,unittest
from unittest.mock import patch
import bootstrap
import owner_emote_dispatch as d
import owner_quest_emote_candidate as n
import test_quest_recovery_cleanup as base
from owner_emote_cooldown import Rate

class Result(unittest.TestCase):
 enter=base.CleanupResult.enter
 worker=base.CleanupResult.worker
 def test_native_dialogue_after_send_closes_receipt_without_resending(self):
  ui,book,row,root=self.worker()
  ui.execution_dialogue_pair=lambda:ui.kind=='dialogue'
  with patch.object(d,'close_chat',side_effect=lambda u,_:setattr(u,'kind','dialogue')):
   self.assertTrue(d.run(ui,book,'q'))
  self.assertEqual(len(ui.actions),1)
  record=json.loads(n._marker_path(root).read_text(encoding='utf8'))
  self.assertEqual(record['phase'],'closed');self.assertEqual(record['next_view'],'dialogue')
  self.assertIs(record['field_verified'],False)
  self.assertEqual(row['emote_attempt']['phase'],'input_intent_unverified')
  self.assertGreater(Rate(root,'scope','char').remaining(),60)
  from owner_mission_controller import native_emote_request,emote_failure_clock
  self.assertEqual(ui.adapter._owner_emote_request_consumed,'q')
  self.assertFalse(native_emote_request(ui.adapter,'q'))
  self.assertIsNone(emote_failure_clock(ui,'q',False,1,120))
  self.assertEqual(row['emote_attempt']['next_view'],'dialogue')
 def test_unknown_transition_after_send_still_blocks_next_input(self):
  ui,book,row,root=self.worker()
  ui.execution_dialogue_pair=lambda:False
  with patch.object(d,'close_chat',side_effect=lambda u,_:setattr(u,'kind','unknown')):
   self.assertTrue(d.run(ui,book,'q'))
  self.assertEqual(len(ui.actions),1)
  self.assertEqual(json.loads(n._marker_path(root).read_text(encoding='utf8'))['phase'],'cleanup_pending')
  self.assertTrue(ui._owner_emote_cleanup_pending)
 def test_normal_field_is_distinct_from_dialogue(self):
  ui,book,row,root=self.worker()
  self.assertTrue(d.run(ui,book,'q'))
  record=json.loads(n._marker_path(root).read_text(encoding='utf8'))
  self.assertEqual(record['phase'],'closed');self.assertEqual(record['next_view'],'field')
  self.assertIs(record['field_verified'],True)

if __name__=='__main__':unittest.main()
