"""A character fighting on the sleep screen already has AUTO on.

Leaving spirit training returns to the sleep screen when it was entered from there. The native
AUTO check looks for a button that screen does not show, fails twice, then wakes the game and
travels back to the hunting spot: about a minute lost every 12 minutes (real log 11-05 03:26).
"""
import logging
from functools import wraps
from pathlib import Path

LOG=logging.getLogger('project_gui.DKB')
SLEEP,FIGHTING='체크_절전모드중','체크_절전모드_전투중'

def fighting_asleep(detector,frame):
    return bool(detector.find(SLEEP,frame,threshold=.95) and detector.find(FIGHTING,frame,threshold=.95))

def wrap(original,detector_factory):
    @wraps(original)
    def ensure(actions,context,log=None,**options):
        capture=getattr(actions,'capture',None)
        if not callable(capture):return original(actions,context,log,**options)
        detector=detector_factory()
        frame=options.get('frame')
        if frame is None:frame=capture()
        if fighting_asleep(detector,frame):
            context.wait(.12);context.checkpoint()
            if fighting_asleep(detector,capture()):
                LOG.info('절전 화면 전투 중 · AUTO 켜짐으로 판단 · 재이동 없음')
                return True
        return original(actions,context,log,**options)
    ensure._owner_sleep_auto=True
    return ensure

def install(gui):
    from project_adapter import auto_mode,secret_exploration,favorite_hunt,field_boss
    if getattr(auto_mode.ensure_auto_active,'_owner_sleep_auto',False):return
    from owner_gear_native_install_candidate import _rebind_aliases
    from roi_runtime import RoiDetector
    root=Path(gui.project.root);cache=[]
    def detector():
        if not cache:cache.append(RoiDetector(root/'profiles/DKB',[SLEEP,FIGHTING]))
        return cache[0]
    original=auto_mode.ensure_auto_active
    guarded=wrap(original,detector)
    auto_mode.ensure_auto_active=guarded
    _rebind_aliases((secret_exploration,favorite_hunt,field_boss),original,guarded)
