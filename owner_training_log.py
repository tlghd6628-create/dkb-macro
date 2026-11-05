"""Weekly training log: claim the cumulative score rewards, found by their words.

A reached reward waits on its own icon. Pressing it pays out at once, then the icon darkens under a check and the red
dots go. The rank rewards on the other tab are paid by the game at the end of the season, so they are left alone.
"""
import logging,re,time
import numpy as np
import owner_hd as hd
import owner_text as text
LOG=logging.getLogger('project_gui.DKB')
NAME='도사 수행록'
# Real pixels. Words are looked for inside these, and nothing is pressed by its place alone.
MENU=(930,60,436,640);SIDE=(18,62,120,70);REWARD_PANEL=(1075,110,270,540);SCORE=(1075,705,270,30);TOAST=(560,130,250,50)
ICON_LEFT=1262;ICON_RIGHT=1320;ICON_HALF=27
RED_SPREAD=80;RED_PIXELS=4
MOST_CLAIMS=5


def parse_score(words):
    found=re.search(r'([\d,]+)\s*점\s*$',str(words))
    return int(found[1].replace(',','')) if found else None


def score_of(rows):
    values={parse_score(row['text']) for row in rows}-{None}
    return values.pop() if len(values)==1 else None


def reward_rows(rows):
    """{step: (points, height)} from words such as 1단계 8,000점, which can arrive as one word or two."""
    found={}
    for row in rows:
        match=re.fullmatch(r'(\d)\s*단계\s*([\d,]+)\s*점',str(row['text']).strip())
        if match:found[int(match[1])]=(int(match[2].replace(',','')),row['ry']);continue
        match=re.fullmatch(r'(\d)\s*단계',str(row['text']).strip())
        if match:
            beside=[other for other in rows if other is not row and abs(other['ry']-row['ry'])<=8 and parse_score(other['text']) is not None]
            if len(beside)==1:found[int(match[1])]=(parse_score(beside[0]['text']),row['ry'])
    return found


def has_red_dot(real,row):
    """The tab's red dot sits just past its words at the top: a colour against its surroundings, not a fixed picture."""
    _,top,right,_=row['bounds']
    part=np.asarray(real)[max(0,top-12):top+6,right-4:right+18].astype(np.int16)
    if not part.size:return False
    return int((part[:,:,0]-np.maximum(part[:,:,1],part[:,:,2])>RED_SPREAD).sum())>=RED_PIXELS


def icon_light(real,height):
    part=np.asarray(real)[max(0,height-ICON_HALF):height+ICON_HALF,ICON_LEFT:ICON_RIGHT]
    return float(part.mean()) if part.size else 0.


def to_claim(real,rewards,score):
    """Reached steps not yet paid, lowest first. A paid icon is far darker than the other icons in the same column."""
    if not rewards or score is None:return []
    lights={step:icon_light(real,height) for step,(_,height) in rewards.items()}
    waiting=[lights[step] for step,(points,_) in rewards.items() if points>score]
    # Steps not reached yet are never dark, so they show what an unpaid icon looks like. With every step reached the
    # brightest one does; a column where all are paid is told by the missing red dot before this is asked.
    bright=max(waiting or lights.values())
    return [step for step,(points,_) in sorted(rewards.items()) if points<=score and lights[step]>=bright*.6]


def _first(rows,words):
    found=text.find(rows,words)
    return found[0] if found else None


def run(adapter,context,inputs):
    """True when nothing is left waiting here. False keeps the job open."""
    from owner_start_menu import normalize
    from owner_skill_ui import SkillUI
    from project_adapter.town_services import TownServices
    ui=SkillUI(adapter,context,inputs)
    try:
        outcome=visit(adapter,context,ui)
    finally:
        try:normalize(TownServices(adapter,context,inputs,['버튼_나가기']))
        except RuntimeError as exc:LOG.info('도사 수행록 닫기 보류 · %s',exc)
    adapter._owner_reward_last_outcome=outcome
    return outcome in ('claimed','none')


def _wait_title(ui,seconds=5):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        frame=ui.frame()
        if text.shows_title(frame,NAME):return frame
        ui.context.wait(.25)
    return None


def visit(adapter,context,ui):
    root=adapter.project.root
    ui.click(875,20,lambda f:True);context.wait(1.2)
    entry=_first(text.read(root,ui.frame(),MENU),NAME)
    if entry is None:
        ui.click(875,20,lambda f:True)
        LOG.info('도사 수행록 메뉴 미확인 · 다음 일정에 다시 확인');return 'failed'
    ui.click(entry['x'],entry['y'],lambda f:True)
    frame=_wait_title(ui)
    if frame is None:
        LOG.info('도사 수행록 화면 미확인 · 다음 일정에 다시 확인');return 'failed'
    context.wait(.6);frame=ui.frame()
    # Cumulative rewards belong to the 전체 side tab.
    side=_first(text.read(root,frame,SIDE),'전체')
    if side is not None:ui.click(side['x'],side['y'],lambda f:True);context.wait(.6)
    return claim_all(root,context,ui)


def claim_all(root,context,ui):
    claimed=0
    for _ in range(MOST_CLAIMS):
        context.checkpoint();frame=ui.frame();real=frame.hi
        panel=text.read(root,frame,REWARD_PANEL)
        tab=_first(panel,'누적 점수 보상');score=score_of(text.read(root,frame,SCORE))
        rewards=reward_rows(panel)
        if score is None or not rewards:
            LOG.info('도사 수행록 점수·보상 판독 실패 · 점수=%s · 보상=%d개 · 다음 일정에 다시 확인',score,len(rewards))
            return 'partial' if claimed else 'failed'
        if tab is not None and not has_red_dot(real,tab):
            LOG.info('도사 수행록 %d점 · 받을 보상 없음%s',score,' · 이번에 %d개 수령'%claimed if claimed else '')
            return 'claimed' if claimed else 'none'
        steps=to_claim(real,rewards,score)
        if not steps:
            LOG.info('도사 수행록 %d점 · 받을 보상 없음%s',score,' · 이번에 %d개 수령'%claimed if claimed else '')
            return 'claimed' if claimed else 'none'
        step=steps[0];points,height=rewards[step];before=icon_light(real,height)
        x,y=hd.logical_of((ICON_LEFT+ICON_RIGHT)//2,height,getattr(frame,'layout',None))
        ui.click(x,y,lambda f:True);context.wait(.7)
        # The payout shows 보상받기 over the panel, then the icon stays dark. Either one proves it.
        shown=bool(text.find(text.read(root,ui.frame(),TOAST),'보상받기'))
        end=time.monotonic()+5
        while time.monotonic()<end and text.find(text.read(root,ui.frame(),TOAST),'보상받기'):context.wait(.4)
        after=icon_light(ui.frame().hi,height)
        if not shown and after>=before*.8:
            LOG.info('도사 수행록 %d단계 수령 확인 실패 · 추가 입력 없음',step)
            return 'partial' if claimed else 'failed'
        claimed+=1
        LOG.info('도사 수행록 %d단계 %d점 보상 수령',step,points)
    return 'claimed'
