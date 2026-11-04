"""Simulated selection repair; no game input or installed state writes."""
import unittest,copy
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import owner_mission_controller as c
from owner_skill_goal import Pending
from biol_base.session import Cancelled

class Mismatch(unittest.TestCase):
 def case(self):
  self.calls=[]
  context=S(checkpoint=lambda:self.calls.append('checkpoint'),wait=lambda n:self.calls.append(('wait',n)))
  adapter=S(_owner_restore_story_once=True,_owner_emote_requested='selected',
            run_town_return=lambda *a:self.fail('no Home for a different tracked quest'))
  book={'active':'selected','quests':{'selected':{'completed':False,'deaths':1},'tracked':{'completed':False}}}
  ui=S(adapter=adapter,context=context,inputs=S(),normal=lambda:True)
  return ui,book
 def test_mismatch_reselects_without_changing_progress_or_returning_home(self):
  ui,book=self.case();before=copy.deepcopy(book)
  with patch('owner_quest_emote_candidate.normalize_after_stop') as cleanup:
   c.reselect_mismatched_emote(ui,Pending('selected != tracked'))
  cleanup.assert_called_once_with(ui.adapter,ui.context,ui.inputs)
  self.assertEqual(book,before)
  self.assertFalse(ui.adapter._owner_restore_story_once)
  self.assertIsNone(ui.adapter._owner_emote_requested)
  self.assertEqual(ui.adapter._owner_emote_binding_errors,1)
 def test_repeated_mismatch_is_bounded_without_fabricated_completion(self):
  ui,book=self.case();before=copy.deepcopy(book)
  with patch('owner_quest_emote_candidate.normalize_after_stop'):
   c.reselect_mismatched_emote(ui,Pending('different'))
   c.reselect_mismatched_emote(ui,Pending('different'))
   with self.assertRaisesRegex(RuntimeError,'3회'):c.reselect_mismatched_emote(ui,Pending('different'))
  self.assertEqual(book,before)
  self.assertEqual(sum(isinstance(x,tuple) for x in self.calls),2)
 def test_user_stop_propagates_before_cleanup_or_reselection(self):
  ui,_=self.case();ui.context.checkpoint=lambda:(_ for _ in ()).throw(Cancelled('stop'))
  with patch('owner_quest_emote_candidate.normalize_after_stop') as cleanup:
   with self.assertRaises(Cancelled):c.reselect_mismatched_emote(ui,Pending('different'))
  cleanup.assert_not_called()
  self.assertTrue(ui.adapter._owner_restore_story_once)
 def test_uncertain_chat_cleanup_blocks_reselection(self):
  ui,_=self.case()
  with patch('owner_quest_emote_candidate.normalize_after_stop',side_effect=Pending('draft unknown')):
   with self.assertRaises(Pending):c.reselect_mismatched_emote(ui,Pending('different'))
  self.assertTrue(ui.adapter._owner_restore_story_once)
  self.assertFalse(hasattr(ui.adapter,'_owner_emote_binding_errors'))
 def test_unknown_field_after_cleanup_does_not_open_missions(self):
  ui,_=self.case();ui.normal=lambda:False
  with patch('owner_quest_emote_candidate.normalize_after_stop'):
   with self.assertRaises(c.EmoteCleanupPending):c.reselect_mismatched_emote(ui,Pending('different'))
  self.assertEqual(self.calls,['checkpoint'])

if __name__=='__main__':unittest.main()
