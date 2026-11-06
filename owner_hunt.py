"""Curated guide candidates with a live power gate; never random fallback."""
from pathlib import Path
import logging,time
from functools import wraps,lru_cache
from owner_progression import state,resized,texts
LOG=logging.getLogger('project_gui.DKB');ASSETS=Path(__file__).parent/'assets'
# Coordinates are valid ONLY after the 897x479 guide title and name row proof.
CANDIDATES=(('안개 기슭 1',37000,(265,357)),('안개 기슭 2',38500,(321,357)),
            ('안개 기슭 지하',51000,(380,357)),('산신의 영역 1',68000,(436,357)),('산신의 영역 2',84500,(492,324)))

@lru_cache(maxsize=2)
def asset(name):
    import numpy as np
    from PIL import Image
    value=np.asarray(Image.open(ASSETS/name).convert('RGB'));value.setflags(write=False)
    return value


def choose(power,excluded=()):
    if not isinstance(power,int):return None
    allowed=[entry for entry in CANDIDATES if entry[1]<=int(power*.85) and entry[1] not in excluded]
    return max(allowed,key=lambda entry:entry[1]) if allowed else None


def title_valid(frame):
    import cv2,numpy as np
    if frame.shape!=(479,897,3):return False
    needle=asset('guide-title.png')
    patch=frame[78:94,423:475]
    return float(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)[0,0])>=.97


def row_valid(frame):
    import numpy as np
    reference=asset('guide-low-row.png')[23:37]
    patch=frame[363:377,233:520]
    def white(image):return (image.min(axis=2)>150)&((image.max(axis=2).astype('int16')-image.min(axis=2))<30)
    expected=white(reference);current=white(patch)
    return int(expected.sum())>=100 and float((expected&current).sum())/int(expected.sum())>=.92


def parsed_required(pages):
    import re
    values=set()
    for text,score in texts(pages):
        clean=re.sub(r'[\s,.:×X]','',text)
        if score>=.97 and clean.isdigit() and 100<=int(clean)<=10_000_000:values.add(int(clean))
    return next(iter(values)) if len(values)==1 else None


def run(adapter,context,inputs):
    from project_adapter.town_services import TownServices
    from project_adapter import guide_rewards,favorite_hunt,market_inventory
    from tools.ocr_support import get_paddle_engine
    from owner_progression import observe_inventory
    adapter.exit_sleep_mode(context,inputs)
    service=TownServices(adapter,context,inputs,list(dict.fromkeys(guide_rewards.NAMES+favorite_hunt.NAMES+market_inventory.INVENTORY_USE_NAMES)))
    # Refresh level/power through the ordinary inventory entry, then close it.
    if market_inventory.open_inventory(service) is False:raise RuntimeError('사냥터 선택 전 인벤토리 확인 실패')
    observe_inventory(service)
    service.button('버튼_X_인벤',required=False);context.wait(.3)
    progress=state(adapter)
    if time.monotonic()-progress.observed>120:raise RuntimeError('현재 전투력을 확인하지 못해 랜덤 사냥터 이동을 보류했습니다.')
    from owner_hunt_memory import guide_excluded,set_route
    candidate=choose(progress.power,guide_excluded(adapter,progress.power))
    if candidate is None:raise RuntimeError('현재 전투력에서 검증된 안전 사냥터 후보를 확인할 수 없습니다.')
    service.key(0x74);context.wait(.4)
    def wait_for(test,seconds=5):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            service.check();frame=service.capture()
            if test(frame):return frame
            context.wait(.1)
        raise RuntimeError('길라잡이 사냥터 화면 확인 시간이 초과되었습니다.')
    wait_for(title_valid)
    # Click the tab only while the exact guide title is present.
    service.click_hit((449,115,(417,105,480,124)));context.wait(.2)
    frame=wait_for(lambda image:title_valid(image) and row_valid(image))
    name,required,point=candidate
    service.click_hit((point[0],point[1],(point[0]-6,point[1]-6,point[0]+7,point[1]+7)));context.wait(.25)
    number=get_paddle_engine(adapter.project.root,language='number');verified=[]
    for _ in range(2):
        frame=wait_for(title_valid)
        verified.append(parsed_required(number.predict(resized(frame,(542,185,55,24)))))
        context.wait(.1)
    if verified!=[required,required]:raise RuntimeError('선택 사냥터 권장 전투력 판독 불일치 · 이동을 보류했습니다.')
    context.checkpoint();fresh=service.capture()
    if not title_valid(fresh) or not row_valid(fresh):raise RuntimeError('이동 직전 사냥터 화면이 바뀌었습니다.')
    LOG.info('사냥터 선택 · %s · 권장=%d · 현재=%d · 검증 후보 중 15%% 여유 기준',name,required,progress.power)
    service.click_hit((607,385,(542,374,678,397)))
    context.wait(1)
    wait_for(lambda image:not title_valid(image),seconds=10)
    # Preserve native AUTO stability proof and bounded sleep-entry handling.
    if favorite_hunt.ensure_auto_active(service.actions,context,LOG,post_click_wait=1,poll_seconds=.5) is False:
        raise RuntimeError('선택 사냥터 AUTO 활성 3초 유지 확인 실패')
    result=adapter.enter_sleep_mode(context,inputs)
    if result is False:raise RuntimeError('선택 사냥터 자동사냥 상태를 확인하지 못했습니다.')
    LOG.info('전투력 기준 사냥터 자동사냥 시작 · %s',name)
    adapter._owner_hunt_ready=True
    set_route(adapter,'guide:'+str(required),name)
    return True


def at_spot(adapter,context,inputs):
    """Back at the hunting spot after OFF·30m: 제자리 ON·5m set here, then AUTO made sure of so it holds this spot.
    Turned on anywhere else it can stay where no monster comes (user 11-06)."""
    from owner_boss_range import pending,restore
    if adapter.mode!='auto_mode' or getattr(adapter,'_owner_temporary_work',None) or not pending(adapter.project.root):return False
    if not restore(adapter,context,inputs):return False
    from project_adapter.town_services import TownServices
    from project_adapter import favorite_hunt
    service=TownServices(adapter,context,inputs,[])
    if favorite_hunt.ensure_auto_active(service.actions,context,LOG,post_click_wait=1,poll_seconds=.5) is False:
        LOG.warning('제자리 복원 뒤 AUTO 확인 실패');return False
    LOG.info('사냥터 도착 · 제자리 5m 설정 후 사냥 계속')
    return True


def install(gui):
    from project_adapter._entry import Adapter
    if getattr(Adapter.run_favorite_hunt,'_owner_guide_hunt',False):return
    ordinary=Adapter.run_favorite_hunt
    @wraps(ordinary)
    def hunt(adapter,context,inputs):
        progress=state(adapter)
        # A boss or raid left on preset B goes back to A before hunting (user 11-06 21:10).
        if adapter.mode=='auto_mode' and not getattr(adapter,'_owner_temporary_work',None):
            from owner_single_preset import resume as preset_return
            try:preset_return(adapter,context,inputs)
            except Exception as exc:
                from biol_base.session import Cancelled
                if isinstance(exc,Cancelled):raise
                LOG.info('사냥 전 프리셋 A 복귀 보류 · %s',str(exc)[:80])
        from owner_town_return import MissingFavorite,require_hunting_location
        from owner_hunt_here import already_there
        try:result=True if already_there(adapter,context,inputs) else ordinary(adapter,context,inputs)
        except MissingFavorite:
            LOG.info('지정 사냥터 미등록 · 둘러보기 추천 후보를 전투력 기준으로 확인합니다.')
            result=run(adapter,context,inputs)
        if result is True:require_hunting_location(adapter,context,inputs)
        if result is True or result in ('HUNTING_RESUMED','HUNTING_STARTED'):
            at_spot(adapter,context,inputs)
            from owner_hunt_here import seen_at_spot
            seen_at_spot(adapter)
        if not getattr(adapter,'_owner_temporary_work',None) and (result is True or result in ('HUNTING_RESUMED','HUNTING_STARTED')):
            context.checkpoint();progress.begin_work('auto_mode')
            # Native preparation calls favorite hunt for side effects, so
            # growth re-evaluation is restricted to actual auto-mode hunting.
            if adapter.mode=='auto_mode' and progress.has_blocks() and not getattr(adapter,'_owner_catalog_enabled',False) and not getattr(adapter,'_owner_stationary_mode',False):
                if time.monotonic()-progress.observed>300:
                    from owner_quest_preflight import read_power
                    read_power(adapter,context,inputs)
                target=progress.choose_mode('auto_mode')
                if target!='auto_mode':
                    from owner_work_resume import ResumeWork
                    progress.grant_retry(target)
                    raise ResumeWork(target)
        return result
    hunt._owner_guide_hunt=True;Adapter.run_favorite_hunt=hunt;gui._owner_guide_hunt=True
