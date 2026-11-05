"""Two states the native AUTO check does not handle.

A character fighting on the sleep screen already has AUTO on.

Leaving spirit training returns to the sleep screen when it was entered from there. The native
AUTO check looks for a button that screen does not show, fails twice, then wakes the game and
travels back to the hunting spot: about a minute lost every 12 minutes (real log 11-05 03:26).

The II icon is a paused AUTO: the character stands still beside monsters. Pressing it gives the white
AUTO, and pressing that gives the gold one that fights (seen live 11-05 10:10). The native check counts II
as on, but this icon scores only about .90 to .95 against its .95 floor, so it sees no AUTO at all and
gives up on the dungeon after 30 seconds. Pressing II once leaves the white state it knows how to handle.
"""
import logging
from functools import wraps
from pathlib import Path

LOG=logging.getLogger('project_gui.DKB')
SLEEP,FIGHTING='체크_절전모드중','체크_절전모드_전투중'
PAUSED='버튼_AUTO_일시정지';RUNNING='버튼_AUTO_활성2';OFF='버튼_AUTO_비활성2'

def fighting_asleep(detector,frame):
    return bool(detector.find(SLEEP,frame,threshold=.95) and detector.find(FIGHTING,frame,threshold=.95))

def paused_hit(detector,frame):
    """The II icon, when neither AUTO icon is there. The floor is for this one icon; the others keep theirs."""
    hit=detector.find(PAUSED,frame,threshold=.90)
    if hit and not detector.find(RUNNING,frame,threshold=.90) and not detector.find(OFF,frame,threshold=.90):return hit
    return None

def press(actions,hit):
    click=getattr(actions,'click_hit',None)
    if callable(click):click(hit)
    # Two frames just proved the icon. Its own re-check at .90 can miss while it animates, and that
    # raises through the whole run, which is too much to pay for a helper (tower TEST 11-05 14:02).
    else:actions.click(PAUSED,hit,threshold=.90,pre_wait=.1,revalidate_template=False)

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
        if paused_hit(detector,frame):
            context.wait(.12);context.checkpoint()
            hit=paused_hit(detector,capture())
            if hit:
                LOG.info('자동전투 일시정지 해제')
                from biol_base.session import Cancelled
                try:press(actions,hit)
                except Cancelled:raise
                except Exception as exc:LOG.warning('자동전투 일시정지 해제 입력 실패 · %s',exc)
                context.wait(.6);context.checkpoint()
                options.pop('frame',None)
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
        if not cache:cache.append(RoiDetector(root/'profiles/DKB',[SLEEP,FIGHTING,PAUSED,RUNNING,OFF]))
        return cache[0]
    original=auto_mode.ensure_auto_active
    guarded=wrap(original,detector)
    auto_mode.ensure_auto_active=guarded
    _rebind_aliases((secret_exploration,favorite_hunt,field_boss),original,guarded)
