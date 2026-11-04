import unittest,threading
from types import SimpleNamespace as S
from unittest.mock import Mock
from owner_window_policy import install

class WindowPolicy(unittest.TestCase):
 def make(self,status):
  self.status=status
  gui=S(project=S(code='DKB'),closed=threading.Event(),session=S(snapshot=lambda:{'status':self.status}),
   game_window=S(connected=lambda:True,require_ready=Mock(side_effect=AssertionError('resize'))),
   check_game_policy=Mock(),game_connected=Mock(),game_state=Mock(),game_hint=Mock(),window_monitor=Mock())
  self.policy=gui.check_game_policy;self.connected=gui.game_connected;install(gui);return gui
 def test_stopped_timer_never_resizes(self):
  g=self.make('stopped');g.check_game_policy();self.policy.assert_not_called()
 def test_paused_timer_never_resizes(self):
  g=self.make('paused');g.check_game_policy();self.policy.assert_not_called()
 def test_startup_connection_is_read_only(self):
  g=self.make('stopped');g.game_connected();self.connected.assert_not_called();g.game_window.require_ready.assert_not_called()
  self.assertTrue(g._game_alive)
 def test_running_keeps_native_size_guard(self):
  g=self.make('running');g.check_game_policy();g.game_connected();self.policy.assert_called_once();self.connected.assert_called_once()
 def test_stopped_then_running_preserves_transition(self):
  g=self.make('stopped');g.check_game_policy();self.assertEqual(g._game_policy_status,'stopped')
  self.status='running';g.check_game_policy();self.policy.assert_called_once()
 def test_closed_never_reconnects(self):
  g=self.make('running');g.closed.set();g.game_connected();self.connected.assert_not_called()

if __name__=='__main__':unittest.main()
