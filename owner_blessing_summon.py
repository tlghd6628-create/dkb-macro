"""가호 소환 at 1366x768, by the user's ticks (11-06): 10회 while ten tickets or more are left, when 10회 is ticked; 1회 for
the rest, when 1회 is ticked. Only 10회 ticked keeps a remainder under ten for later; only 1회 ticked uses them one by one.

The summon tab of the blessing screen shows the tickets left and the 1회/10회 buttons; after a press the result screen shows
the same with 나가기 (pc1 05:3x: 34 → 33, 도깨비 가호 조각1 ×25). Every press must take the count down by exactly its
cost before the next; anything else stops. Buttons are found by their words on each screen.
"""
import logging,re,time
import numpy as np
import owner_hd as hd
import owner_text as text
import owner_worn_stats as worn

LOG=logging.getLogger('project_gui.DKB')
KEY='owner_summon.blessing.enabled'
SUMMON_TAB=(199,79)
COUNT=(630,660,180,40)        # the tickets left: 34 at (719,674) on the tab, (719,682) on the result
BUTTONS=(420,698,560,50)      # 1회 · 10회 · 나가기
MAX_PRESSES=100
SKIP_BOX=(33,727,14,14)       # 모든 연출 건너뛰기, bottom left of the result screen: ~73 light pixels ticked (pc1 05:3x)
SKIP_LIGHT=25
COSTS={'1회':1,'10회':10}


def plan(tickets,one,ten):
    """How many 10회 and 1회 presses the ticks ask for, with this many tickets."""
    if type(tickets) is not int or tickets<0:return 0,0
    tens=tickets//10 if ten else 0
    ones=tickets-10*tens if one else 0
    return tens,ones


def tickets(service,context):
    """The tickets left, once two looks agree, or None."""
    looks=[]
    for _ in range(4):
        context.checkpoint();service.check()
        real=np.asarray(service.capture().hi);x,y,w,h=COUNT;value=None
        # A lone 3 read nothing at scale 3 and 3 at 1.0 at scales 2 and 4 (pc1 11:04): the first size that reads one number.
        for scale in (3,2,4):
            numbers=[clean for row in text.read_area(None,real[y:y+h,x:x+w],language='number',scale=scale,minimum=.6)
                     for clean in [text.clean(row['text']).replace(',','')] if re.fullmatch(r'\d{1,4}',clean)]
            if len(numbers)==1:value=int(numbers[0]);break
        looks.append(value)
        if len(looks)>=2 and looks[-1] is not None and looks[-1]==looks[-2]:return looks[-1]
        context.wait(.3)
    return None


def button(service,word):
    real=np.asarray(service.capture().hi);x,y,w,h=BUTTONS
    rows=[row for row in text.read_area(None,real[y:y+h,x:x+w],left=x,top=y,scale=2,minimum=.6) if text.clean(row['text'])==word]
    return rows[0] if len(rows)==1 else None


def skip_ticked(service):
    """True or False for the result screen's 모든 연출 건너뛰기 box, None when it is not there to read."""
    if button(service,'나가기') is None:return None
    real=np.asarray(service.capture().hi);x,y,w,h=SKIP_BOX
    light=int((real[y:y+h,x:x+w].astype(int).min(2)>160).sum())
    return True if light>=SKIP_LIGHT else False if light<=8 else None


def keep_skipping(service,context):
    """The user's rule (11-06): the box stays ticked whenever it shows."""
    if skip_ticked(service) is False:
        x,y,w,h=SKIP_BOX;service.click_hit(hd.real_hit(x+w//2,y+h//2));context.wait(.6)
        LOG.info('가호 소환 · 모든 연출 건너뛰기 체크 %s','확인' if skip_ticked(service) else '미확인')


def press(service,context,word,before):
    """One press of 1회 or 10회. True when the count fell by exactly its cost. A cutscene in between (혈을 꾸욱
    눌러주세요, Skip ESC: pc2 11-06, its box unticked) is skipped with ESC until the result screen is back."""
    row=button(service,word)
    if row is None:
        LOG.info('가호 소환 중단 · %s 버튼 미확인',word);return False
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(row['rx'],row['ry']))
    want=before-COSTS[word]
    end=time.monotonic()+20;escaped=0;sent=time.monotonic();again=0
    while time.monotonic()<end:
        context.wait(.5)
        now=tickets(service,context)
        if now==want:
            keep_skipping(service,context);return True
        if now==before and time.monotonic()-sent>5 and again<2:
            # A press on the result screen went unheard: 13 stayed 13 for 20 s (pc1 10:55). Pressing again is safe,
            # since only the count falling counts, and a double one is a wrong count that stops.
            row=button(service,word)
            if row is not None:
                context.checkpoint();service.check();service.click_hit(hd.real_hit(row['rx'],row['ry']))
                again+=1;sent=time.monotonic();LOG.info('가호 소환 · %s 다시 누름 · 소환권 그대로 %d',word,before)
        if now is not None and now!=before:
            LOG.info('가호 소환 중단 · 소환권 %d → %d · 예상 %d',before,now,want);return False
        if now is None and button(service,'나가기') is None and escaped<12:
            # No count and no result buttons: a cutscene. ESC is its own skip.
            context.checkpoint();service.check();service.key(0x1b);escaped+=1;context.wait(.8)
    LOG.info('가호 소환 중단 · %s 결과 미확인 · 소환권 %d',word,before);return False


def settings(root):
    from owner_gear_settings_candidate import Store
    from owner_hunt_rules_candidate import configured_identity
    try:section=Store(root,configured_identity(root)).read().get('blessing_summon',{})
    except (OSError,ValueError,TypeError):return {'one':False,'ten':False}
    return {'one':section.get('one') is True,'ten':section.get('ten') is True}


def enabled(root):
    return any(settings(root).values())


def run(adapter,context,inputs,choice=None):
    """A short result for the log and TEST."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES);service.context=context
    if getattr(service.capture(),'hi',None) is None:return '보류 · 1366x768 화면이 아님'
    choice=choice if choice is not None else settings(adapter.project.root)
    if not choice.get('one') and not choice.get('ten'):return '보류 · 1회·10회 선택 없음'
    if not worn.open_blessing_screen(service,context):return '보류 · 가호 화면 안 열림'
    done={'10회':0,'1회':0};left=None
    try:
        service.click_hit(hd.real_hit(*SUMMON_TAB));context.wait(1.5)
        left=tickets(service,context)
        if left is None:return '보류 · 소환권 수 미확인'
        tens,ones=plan(left,choice.get('one'),choice.get('ten'))
        LOG.info('가호 소환 시작 · 소환권 %d · 10회 %d번 · 1회 %d번',left,tens,ones)
        for word,times in (('10회',tens),('1회',ones)):
            for _ in range(min(times,MAX_PRESSES)):
                if not press(service,context,word,left):raise StopIteration
                left-=COSTS[word];done[word]+=1
    except StopIteration:pass
    finally:
        context.checkpoint()
        out=button(service,'나가기')
        if out is not None:service.click_hit(hd.real_hit(out['rx'],out['ry']));context.wait(1.5)
        worn.leave_blessing_screen(service,context)
    result='가호 소환 10회 %d번 · 1회 %d번 · 남은 소환권 %s'%(done['10회'],done['1회'],left)
    LOG.info(result)
    return result
