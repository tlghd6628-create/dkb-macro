import bootstrap
import unittest,copy,logging,queue
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from datetime import timedelta
from test_followup14 import Startup
import owner_timetable as t
from owner_manual_diagnostics import transfer_caption,log_transfer
from owner_mission_controller import after_reward_idle,QuestBoundary
from user_log import LogQueue

class Catchup(Startup):
 def test_shifted_past_due_job_is_due_now(self):
  self.p.cfg['jobs']['daily_dungeon']={'time':'06:00'}
  row=self.row('daily_dungeon','pending',at=(self.at+timedelta(hours=2)).isoformat())
  self.p.startup_recheck(self.at)
  self.assertTrue(row['startup_recheck']);self.assertLess(t.parse_at(row['at']),self.at+timedelta(minutes=1))
 def test_finish_does_not_push_catchup_queue_hours_later(self):
  self.row('guide','running');row=self.row('mail','pending',startup_recheck=True)
  when=row['at'];self.p.finish('guide',True,self.at,unverified=True)
  self.assertEqual(row['at'],when)

class RewardBoundary(unittest.TestCase):
 def setup_case(self,normal=True,dialogue=False):
  ctx=S(checkpoint=Mock(),wait=Mock());ui=S(context=ctx,normal=Mock(return_value=normal),execution_dialogue_pair=Mock(return_value=dialogue))
  return S(_owner_reward_seen_at=100,_owner_reward_idle_since=101),S(_owner_mission_ui=ui),ctx
 def test_reward_then_settled_idle_returns_to_list_without_completion_claim(self):
  runner,adapter,ctx=self.setup_case()
  with patch('owner_mission_controller.time.monotonic',return_value=103):
   with self.assertRaises(QuestBoundary):after_reward_idle(runner,adapter,ctx)
  self.assertIsNone(runner._owner_reward_seen_at)
 def test_dialogue_not_interrupted(self):
  runner,adapter,ctx=self.setup_case(dialogue=True)
  with patch('owner_mission_controller.time.monotonic',return_value=103):self.assertTrue(after_reward_idle(runner,adapter,ctx))
 def test_loading_waits_without_blank_click(self):
  runner,adapter,ctx=self.setup_case(normal=False)
  with patch('owner_mission_controller.time.monotonic',return_value=103):self.assertTrue(after_reward_idle(runner,adapter,ctx))
 def test_no_reward_does_not_interrupt_normal_chapter(self):
  runner,adapter,ctx=self.setup_case();runner._owner_reward_seen_at=None
  self.assertFalse(after_reward_idle(runner,adapter,ctx));adapter._owner_mission_ui.normal.assert_not_called()

class Transfer(unittest.TestCase):
 def test_completion_caption_persists(self):self.assertEqual(transfer_caption({'phase':'sent'}),'진단 전송 완료')
 def test_counts_are_visible_while_sending(self):self.assertIn('화면 3/20',transfer_caption({'phase':'sending','pictures_sent':3,'pictures':20}))
 def test_actual_gui_queue_contains_receipt(self):
  q=queue.Queue();handler=LogQueue(q);logger=logging.getLogger('followup15');logger.setLevel(logging.INFO);logger.addHandler(handler)
  try:
   log_transfer(logger,{'phase':'sent','logs':215,'pictures':20,'id':'test'})
   self.assertIn('서버 수신 확인',q.get_nowait())
  finally:logger.removeHandler(handler)

if __name__=='__main__':unittest.main()
