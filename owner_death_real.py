"""Death during a quest at 1366x768, by its own words: 사망 상태 at the top and 나가기 at the bottom.

pc1 11-06 13:51: killed by 화미공, the native runner kept moving to safe spots and dodging for minutes, since its
체크_사망상태 picture read 58% at 1366 (pc2 saw the same, deaths=0). Both words on two looks are the proof; 나가기 is then
pressed and the quest loop records the death by its existing rule (a second death holds the quest).
"""
import logging,time
import owner_hd as hd
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
TITLE=(520,18,330,44)      # real: 사망 상태
EXIT=(590,700,190,52)      # real: 나가기 (683,726)


def dead(frame):
    if getattr(frame,'hi',None) is None:return False
    top=''.join(text.clean(r['text']) for r in text.read(None,frame,TITLE,scale=2,minimum=.6))
    return '사망상태' in top and exit_word(frame) is not None


def exit_word(frame):
    rows=[r for r in text.read(None,frame,EXIT,scale=2,minimum=.6) if text.clean(r['text'])=='나가기']
    return rows[0] if len(rows)==1 else None


def recover(ui,seconds=20.):
    """True when the death screen showed on two looks and 나가기 was pressed."""
    first=ui.frame()
    if not dead(first):return False
    ui.context.wait(.3)
    second=ui.frame()
    if not dead(second):return False
    row=exit_word(second)
    ui.context.checkpoint()
    ui.service.click_hit(hd.real_hit(round(row['rx']),round(row['ry'])))
    LOG.warning('사망 감지 · 1366 사망 상태 화면 · 나가기')
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        ui.context.wait(1.)
        if not dead(ui.frame()):break
    return True
