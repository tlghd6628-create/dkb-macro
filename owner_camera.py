"""Zoom the camera fully out when work starts, by the user's request.

Real game: wheel down zooms out, and 40 notches cover the whole range. A town's camera is
fixed and ignores the wheel, so hunting arrival asks once more. It only moves the camera,
so a failure is logged and never stops the work.
"""
import logging
LOG=logging.getLogger('project_gui.DKB')
NOTCHES=40;AT=(456,180)

def zoom_out(adapter,context,inputs):
    from owner_mission_ui import MissionUI
    from owner_boss_range import panel_open
    try:
        MissionUI(adapter,context,inputs).wheel(-1,NOTCHES,at=AT,scene=lambda frame:not panel_open(frame),verify_cursor=True)
        LOG.info('카메라 최대 줌아웃');return True
    except (RuntimeError,ValueError,OSError) as exc:
        LOG.warning('카메라 줌아웃 생략 · %s',str(exc)[:100]);return False

def zoom_once(adapter,context,inputs):
    """Once per start, at the hunting spot."""
    if getattr(adapter,'_owner_camera_context',None) is context:return False
    adapter._owner_camera_context=context
    return zoom_out(adapter,context,inputs)
