"""Switch skill preset from the H menu, in place of the native routine that stopped finding it.

H opens a column of letters over the skill bar, A at the bottom to E at the top, with the current one lit.
The native routine reported '스킬 프리셋 진입 미감지' every time (real raid 11-05 14:40), so a raid or a
world boss kept the everyday deck. Seen live: picking B swaps the bar at once and the menu closes.
"""
import logging
from functools import wraps

LOG=logging.getLogger('project_gui.DKB')
LETTERS={'A':412,'B':385,'C':356,'D':328,'E':300}
KEY_H=0x48;X=738;COMMON='common.skill_preset'


def lit_letter(frame):
    """The lit letter, or None when the menu is not open. Each circle's darkest channel: lit about 105, others 50 to 57."""
    if getattr(frame,'shape',None)!=(479,897,3):return None
    levels={name:float(frame[y-8:y+9,X-8:X+9].min(axis=2).mean()) for name,y in LETTERS.items()}
    ranked=sorted(levels,key=levels.get,reverse=True)
    return ranked[0] if levels[ranked[0]]>=85 and levels[ranked[0]]-levels[ranked[1]]>=30 else None


def _wait_open(service,seconds=2.5):
    """The lit letter once two frames in a row agree. Presses nothing."""
    import time
    end=time.monotonic()+seconds;last=None
    while time.monotonic()<end:
        service.check();now=lit_letter(service.capture())
        if now and now==last:return now
        last=now;service.context.wait(.15)
    return None


def select(service,letter):
    """True once the menu, opened again, shows this letter lit. Always leaves the menu closed."""
    if letter not in LETTERS:return False
    current=lit_letter(service.capture())
    if current is None:
        service.key(KEY_H);current=_wait_open(service)
    if current is None:
        LOG.warning('스킬 프리셋 메뉴 확인 안 됨 · %s',letter);return False
    if current==letter:
        service.key(KEY_H);service.context.wait(.2);return True
    y=LETTERS[letter];service.click_hit((X,y,(X-9,y-9,X+10,y+10)));service.context.wait(.6)
    service.check()
    # Picking closes the menu. Open it once more: only the lit letter says the switch took.
    if lit_letter(service.capture()) is None:service.key(KEY_H)
    shown=_wait_open(service)
    if shown is not None:service.key(KEY_H);service.context.wait(.2)
    if shown!=letter:
        LOG.warning('스킬 프리셋 전환 확인 안 됨 · 목표 %s · 화면 %s',letter,shown);return False
    return True


def run_skill_preset(adapter,context,inputs,*,enabled_key=COMMON+'.enabled',choice_key=COMMON+'.choice'):
    """Same call as the native routine: off does nothing, and a failure never stops the content."""
    values=getattr(adapter,'values',{})
    if values.get(enabled_key) is not True:return False
    letter=values.get(choice_key)
    from project_adapter.town_services import TownServices
    service=TownServices(adapter,context,inputs,[])
    context.checkpoint()
    done=select(service,letter)
    if done:LOG.info('스킬 프리셋 %s 적용',letter)
    return done


def install():
    """Every module that imported the native routine by name gets this one."""
    import sys
    from project_adapter import skill_preset
    original=skill_preset.run_skill_preset
    if getattr(original,'_owner_quick_preset',False):return
    @wraps(run_skill_preset)
    def replacement(*args,**kwargs):return run_skill_preset(*args,**kwargs)
    replacement._owner_quick_preset=True
    for name,module in list(sys.modules.items()):
        if (name.startswith('project_adapter') or name.startswith('owner_')) and module is not None and getattr(module,'run_skill_preset',None) is original:
            module.run_skill_preset=replacement
    skill_preset.run_skill_preset=replacement
