"""World boss only at the user's power floor, even when its switch is on.

A power that cannot be read is not a pass. An entry already under way goes
through owner_special_contexts and is not stopped here.
"""
from functools import wraps
import logging,time

LOG=logging.getLogger('project_gui.DKB')
MINIMUM=150000
FRESH_SECONDS=120;DENIED_SECONDS=600

def allowed(adapter,context,inputs):
    from owner_progression import state
    from owner_quest_preflight import read_power
    progress=state(adapter);denied=getattr(adapter,'_owner_boss_denied',None)
    now=time.monotonic()
    # The native calendar asks again through the whole entry window. One look
    # in the inventory answers for that window, unless the power has changed.
    if denied is not None and now-denied[0]<DENIED_SECONDS and progress.power==denied[1]:return False
    if type(progress.power) is not int or now-progress.observed>FRESH_SECONDS:read_power(adapter,context,inputs)
    power=progress.power
    if type(power) is int and power>=MINIMUM:
        adapter._owner_boss_denied=None;return True
    adapter._owner_boss_denied=(time.monotonic(),power)
    text='월드보스 보류 · 전투력 %s · %s 미만이라 입장 안 함'%(format(power,',') if type(power) is int else '확인 불가',format(MINIMUM,','))
    LOG.info(text,extra={'gui_message':text})
    return False

def leaving(adapter,context,inputs):
    """The context whose waits touch the result table away; the plain context when no screen service can be made."""
    try:
        from owner_boss_exit import Leaving
        from project_adapter.town_services import TownServices
        return Leaving(context,TownServices(adapter,context,inputs,[]),exit_after=None)
    except Exception as exc:
        LOG.debug('필드 보스 결과 터치 준비 생략 · %s',exc);return context

def install(gui=None):
    from project_adapter._entry import Adapter
    if getattr(Adapter._run_field_boss_entry,'_owner_boss_gate',False):return
    ordinary=Adapter._run_field_boss_entry
    @wraps(ordinary)
    def entry(adapter,context,inputs,*args,**kwargs):
        context.checkpoint()
        if not allowed(adapter,context,inputs):return True
        # Late import: tests and the gate itself stay usable without the panel module.
        from owner_boss_range import loosen
        loosen(adapter,context,inputs)
        # The record stays open: 제자리 comes back on only at the saved hunting spot (owner_hunt), never where the boss
        # was, which may have no monsters (user 11-06).
        # The result table is left by a touch as soon as it shows; only the touch, never the exit, during a fight.
        return ordinary(adapter,leaving(adapter,context,inputs),inputs,*args,**kwargs)
    entry._owner_boss_gate=True;Adapter._run_field_boss_entry=entry
