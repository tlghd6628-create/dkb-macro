"""Reward/cleanup admission in a dungeon; reuse original markers and timer."""
import time

LABELS=frozenset(('길라잡이','이벤트','이벤트·출석','우편','업적','도사 수행록','거래소','거래소 등록','장비 분해'))
JOBS=frozenset(('guide','events','mail','achievement','training_log','market','disassembly'))
DUNGEONS=frozenset(('비경탐험','비경탐험(일일-24시간)','전래동화 비경','비경·던전'))
MIN_REMAINING=600
CLOCK_REUSE=300


def read_remaining(service):
    """Use the entry TEST's shared duration reader on two fresh HUD crops.

    Read-only on the existing worker. Keep the three-second observation bound,
    current-context cache and ten-minute admission rule; never infer zero.
    """
    from tools import time_ocr
    from owner_dungeon_map import inside as dungeon_frame
    from owner_startup_stage import DUNGEON,EXIT
    context=service.context;adapter=service.adapter
    previous=getattr(adapter,'_owner_stage_ocr_job',None)
    if previous is not None and previous.is_alive():return None
    frames=[]
    for index in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if (getattr(frame,'shape',None)!=(479,897,3)
            or not dungeon_frame(service.detector,frame)):return None
        frames.append(frame[98:111,3:58].copy())
        if index==0:context.wait(.15)
    captured=time.monotonic();deadline=captured+3;values=[]
    try:
        for crop in frames:
            context.checkpoint()
            result=time_ocr.read_time_image(crop,adapter.project.root,context,deadline=deadline)
            if not result.ok or type(result.seconds) is not int or not 0<=result.seconds<=86400:return None
            values.append(result.seconds)
    except time_ocr.TimeOCRTimeout:return None
    context.checkpoint();service.check();now=time.monotonic()
    if now>deadline or not 0<=values[0]-values[1]<=2:return None
    frame=service.capture()
    if not dungeon_frame(service.detector,frame):return None
    seconds=max(0,values[-1]-(now-captured))
    adapter._owner_reward_dungeon_clock={'context':context,'at':now,'seconds':seconds}
    return seconds


def admit(adapter,context,inputs,*,service=None):
    from owner_schedule_priority import LOCAL
    from owner_startup_stage import DUNGEON,EXIT
    from owner_dungeon_map import inside as dungeon_frame
    context.checkpoint()
    now=time.monotonic();cached=getattr(adapter,'_owner_reward_admission',None)
    if cached and cached['context'] is context and now-cached['at']<1:
        remaining=cached.get('remaining')
        if remaining is not None:remaining=max(0,remaining-(now-cached['at']))
        return decision(cached['in_dungeon'],remaining)
    if service is None:
        from project_adapter.town_services import TownServices
        service=TownServices(adapter,context,inputs,[DUNGEON,EXIT])
    markers=[]
    from owner_chore_transition import unavailable_frame
    for index in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if unavailable_frame(frame):return {'allowed':False,'in_dungeon':False,'remaining':None,'reason':'화면 전환 중 · 보상·정리 시작 보류'}
        markers.append(dungeon_frame(service.detector,frame))
        if index==0:context.wait(.12)
    if markers[0]!=markers[1]:return {'allowed':False,'in_dungeon':False,'remaining':None,'reason':'화면 전환 중 · 보상·정리 시작 보류'}
    inside=markers[1] or getattr(LOCAL,'combat',None) in DUNGEONS
    remaining=None
    if inside:
        clock=getattr(adapter,'_owner_reward_dungeon_clock',None)
        now=time.monotonic()
        # Reuse a proved countdown while both current dungeon markers remain.
        # Leaving to a proved field invalidates it in publish(); new Stop/Start
        # contexts cannot inherit it. Time spent in menus is subtracted.
        if (clock and clock['context'] is context and 0<=now-clock['at']<=CLOCK_REUSE
            and (markers[1] or now-clock['at']<=30)):
            remaining=max(0,clock['seconds']-(now-clock['at']))
        else:remaining=read_remaining(service)
    elif getattr(adapter,'_owner_reward_dungeon_clock',None) is not None:
        adapter._owner_reward_dungeon_clock=None
    adapter._owner_reward_admission={'context':context,'at':time.monotonic(),'in_dungeon':inside,'remaining':remaining}
    return decision(inside,remaining)


def decision(inside,remaining):
    reason=None
    if inside and remaining is None:reason='비경 남은 시간 판독 필요 · 보상·정리 시작 보류'
    elif inside and remaining<=MIN_REMAINING:reason='비경 종료까지 10분 이하 · 보상·정리 시작 보류'
    return {'allowed':reason is None,'in_dungeon':inside,'remaining':remaining,'reason':reason}
