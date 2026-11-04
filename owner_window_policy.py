"""Inactive sessions may observe/attach HWND, never restore game geometry."""
from functools import wraps

def running(gui):
 return not gui.closed.is_set() and gui.session.snapshot().get('status')=='running'

def observe_connection(gui):
 gui._game_alive=gui.game_window.connected()
 gui._game_misses=0
 gui.game_state.set('연결' if gui._game_alive else '미연결')
 gui.game_hint.set('게임 연결 완료' if gui._game_alive else '게임 연결 필요')
 # No require_ready, window_state.attach, alignment, restore or z-order call.
 if gui._game_alive and hasattr(gui,'window_monitor'):gui.window_monitor.connected()

def install(gui):
 if getattr(gui,'_owner_inactive_geometry_policy',False) or gui.project.code!='DKB':return
 original_policy=gui.check_game_policy
 original_connected=gui.game_connected
 @wraps(original_policy)
 def policy():
  if not running(gui):
   gui._game_policy_status=gui.session.snapshot().get('status')
   return
  return original_policy()
 @wraps(original_connected)
 def connected(context=None):
  if not running(gui):
   if not gui.closed.is_set():observe_connection(gui)
   return
  return original_connected(context)
 gui.check_game_policy=policy
 gui.game_connected=connected
 gui._owner_inactive_geometry_policy=True
