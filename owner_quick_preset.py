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


WHITE=200;WHITE_PIXELS=30;HALF=16

def _real_lit(real):
    """The one circle holding a white letter that reads as its own letter.

    The circles are see-through, so what is behind them differs by character and by deck: a closed menu's A spot
    measures 70 and an open one's 103 from the skill icons alone. Unlit letters are too dim to read (D read as B at .98),
    so only a white one is read, and art behind a closed menu does not read as this exact letter.
    """
    import owner_hd
    from owner_text import read_area,clean
    found=[]
    for name,y in LETTERS.items():
        cx,cy=round(X*owner_hd.F+owner_hd.SHIFT_RIGHT),round(y*owner_hd.F)
        crop=real[cy-HALF:cy+HALF,cx-HALF:cx+HALF]
        if int((crop.min(axis=2)>WHITE).sum())<WHITE_PIXELS:continue
        rows=read_area(None,crop,left=cx-HALF,top=cy-HALF,scale=4,minimum=.6)
        if any(clean(row['text'])==name for row in rows):found.append(name)
    return found[0] if len(found)==1 else None


def lit_letter(frame):
    """The lit letter, or None when the menu is not open. Each circle's darkest channel: lit about 105, others 50 to 57."""
    if getattr(frame,'shape',None)!=(479,897,3):return None
    real=getattr(frame,'hi',None)
    if real is not None:return _real_lit(real)
    levels={name:float(frame[y-8:y+9,X-8:X+9].min(axis=2).mean()) for name,y in LETTERS.items()}
    ranked=sorted(levels,key=levels.get,reverse=True)
    return ranked[0] if levels[ranked[0]]>=85 and levels[ranked[0]]-levels[ranked[1]]>=30 else None


def _letter_hit(frame,letter):
    """A fixed place. The column stands at the right edge, but the screen map put D and E 34 px off it, beside the circle (real click 11-06)."""
    y=LETTERS[letter]
    if getattr(frame,'hi',None) is None:return (X,y,(X-9,y-9,X+10,y+10))
    import owner_hd
    return owner_hd.real_hit(round(X*owner_hd.F+owner_hd.SHIFT_RIGHT),round(y*owner_hd.F))


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
    service.click_hit(_letter_hit(service.capture(),letter))
    # Picking closes the menu, slowly: a key pressed while it slides is lost or reopens it.
    service.context.wait(1.5)
    service.check()
    # Open it once more: only the lit letter says the switch took.
    shown=lit_letter(service.capture())
    if shown is None:
        service.key(KEY_H);shown=_wait_open(service,4)
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
    # A new character's B also swaps gear to an empty preset 2; set it to skills only the first time (user 11-06).
    from owner_preset_compose import ensure
    ensure(adapter,context,inputs,letter)
    service=TownServices(adapter,context,inputs,[])
    context.checkpoint()
    # Any letter but A is noted first, so the next field start goes back to A (owner_single_preset.resume). Only the
    # raid noted it; after the 21:00 field boss the hunt went on with B (user 11-06).
    from owner_single_preset import mark
    if letter!='A':mark(adapter,True)
    done=select(service,letter)
    if done:
        LOG.info('스킬 프리셋 %s 적용',letter)
        if letter=='A':mark(adapter,False)
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
