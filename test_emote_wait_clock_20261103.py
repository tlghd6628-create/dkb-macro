"""Replay the real 24-second rate wait -> false 30-second recovery timing."""
import tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace as S
import bootstrap
from owner_mission_controller import emote_failure_clock
from owner_emote_cooldown import Rate
import owner_quest_position_recovery as r
import test_diagnostic_0913_recovery as base

class Clock(unittest.TestCase):
 def ui(self,until=61):return S(adapter=S(_owner_emote_requested='q'),_owner_emote_cooldown_until=until)
 def test_server_wait_does_not_age_the_failure_clock(self):
  ui=self.ui();since=None
  for tick in (24,39,54,60):since=emote_failure_clock(ui,'q',False,since,tick);self.assertIsNone(since)
  since=emote_failure_clock(ui,'q',False,since,62)
  self.assertEqual(since,62)
  self.assertLess(90-emote_failure_clock(ui,'q',False,since,90),30)
  self.assertEqual(92-emote_failure_clock(ui,'q',False,since,92),30)
 def test_success_and_a_new_goal_reset_prior_failure_time(self):
  ui=self.ui(0)
  self.assertIsNone(emote_failure_clock(ui,'q',True,10,39))
  ui.adapter._owner_emote_requested=None
  self.assertIsNone(emote_failure_clock(ui,'q',False,10,39))
 def test_real_unreadable_request_still_reaches_thirty_seconds(self):
  ui=self.ui(0);since=emote_failure_clock(ui,'q',False,None,10)
  self.assertEqual(40-emote_failure_clock(ui,'q',False,since,40),30)
 def test_cooldown_beginning_after_a_previous_failure_resets_it(self):
  self.assertIsNone(emote_failure_clock(self.ui(100),'q',False,10,60))

class Recovery(unittest.TestCase):
 setup_case=base.RecoveryTests.setup_case
 bindings=base.RecoveryTests.bindings
 def test_previous_quest_rate_blocks_home_for_a_new_quest_without_an_attempt(self):
  ui,book=self.setup_case()
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as tmp:
   ui.adapter.project.root=Path(tmp)
   Rate(tmp,'scope','char').reserve('previous','화남')
   self.assertNotIn('emote_attempt',self.row)
   with self.bindings():self.assertEqual(r.recover(ui,book,'q',base.REASON),'waiting_emote')
  self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
