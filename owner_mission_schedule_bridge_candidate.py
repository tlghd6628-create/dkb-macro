"""Candidate bridge for paired daily/weekly native mission entry.

Install *outside* the membership wrapper so its quota checks see the same mask.
Never creates another worker, never clicks, and never edits saved settings.
Native MissionQuests.run still requires real-game verification.
"""
from functools import wraps
import logging,sys
LOG=logging.getLogger('project_gui.DKB')
OPTIONS=(('daily_missions','auto_schedule.daily_quest.enabled'),
         ('weekly_missions','auto_schedule.weekly_quest.enabled'))

def dispatch(original,adapter,context,inputs):
    from owner_timetable import LOCAL,BY_KEY,planner,scheduled_call
    # Timetable.invoke already masks the selected native job and owns receipt.
    # A matching in-progress job likewise must not recursively double-schedule.
    if getattr(LOCAL,'native_job',None) or getattr(LOCAL,'job',None) in ('daily_missions','weekly_missions'):
        return original(adapter,context,inputs)
    plan=planner(adapter);old=adapter.values;attempted=False
    try:
        for key,setting in OPTIONS:
            if old.get(setting) is not True:continue
            context.checkpoint()
            if key not in plan.state or not plan.values.get(setting,False):
                LOG.warning('자동 기능 보류 · %s · 시간표 설정 동기화 확인 필요',BY_KEY[key].label);continue
            reason=plan.reason(key)
            if reason:
                LOG.info('자동 기능 보류 · %s · %s',BY_KEY[key].label,reason);continue
            isolated=dict(old)
            for _,flag in OPTIONS:isolated[flag]=(flag==setting)
            adapter.values=isolated
            attempted=True
            try:result=scheduled_call(original,BY_KEY[key].label,(adapter,context,inputs),{},adapter)
            finally:adapter.values=old
            # Unknown or failed UI outcome may have left an intermediate
            # screen; don't issue an unrelated second mission operation.
            if result is None or result is False:return result
        return True
    finally:adapter.values=old

def install():
    from project_adapter import mission_quests
    original=mission_quests.run_mission_quests
    if getattr(original,'_owner_mission_schedule_bridge',False):return original
    @wraps(original)
    def bridge(adapter,context,inputs):return dispatch(original,adapter,context,inputs)
    bridge._owner_mission_schedule_bridge=True
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for attr,value in tuple(vars(module).items()):
                if value is original:setattr(module,attr,bridge)
    return bridge
