"""Let a loading screen finish before the native menu-return wait gives up.

Only the black loading screen extends the wait, and nothing is sent while it
lasts. Any other screen fails as the native wait already does.
"""
from functools import wraps
import logging,time

LOG=logging.getLogger('project_gui.DKB')
LIMIT_SECONDS=120
TIMEOUT_TEXT='전체메뉴 복귀 확인 시간초과'

def loading_frame(frame):
    """Black everywhere except the small loading mark in the bottom-right corner."""
    import numpy as np
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
    rest=frame.copy();rest[430:,840:]=0
    return int(rest.max())<=8 and float(rest.mean())<=1.

def wrap(original):
    @wraps(original)
    def wait_menu(service,stage=None):
        started=time.monotonic();told=False
        while True:
            try:return original(service,stage)
            except RuntimeError as exc:
                if TIMEOUT_TEXT not in str(exc):raise
                context=service.context
                context.checkpoint();service.check()
                if not loading_frame(service.capture()):raise
                if not told:LOG.info('로딩 화면 대기 · 입력 없음 · 최대 %d초',LIMIT_SECONDS);told=True
                while True:
                    if time.monotonic()-started>=LIMIT_SECONDS:raise
                    context.wait(1);context.checkpoint();service.check()
                    if not loading_frame(service.capture()):break
    wait_menu._owner_town_wait=True
    return wait_menu

def install():
    from project_adapter.town_services import TownServices
    if not getattr(TownServices.wait_menu,'_owner_town_wait',False):TownServices.wait_menu=wrap(TownServices.wait_menu)
