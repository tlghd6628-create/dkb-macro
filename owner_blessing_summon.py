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
        real=np.asarray(service.capture().hi);x,y,w,h=COUNT
        numbers=[clean for row in text.read_area(None,real[y:y+h,x:x+w],language='number',scale=3,minimum=.6)
                 for clean in [text.clean(row['text']).replace(',','')] if re.fullmatch(r'\d{1,4}',clean)]
        looks.append(int(numbers[0]) if len(numbers)==1 else None)
        if len(looks)>=2 and looks[-1] is not None and looks[-1]==looks[-2]:return looks[-1]
        context.wait(.3)
    return None


def button(service,word):
    real=np.asarray(service.capture().hi);x,y,w,h=BUTTONS
    rows=[row for row in text.read_area(None,real[y:y+h,x:x+w],left=x,top=y,scale=2,minimum=.6) if text.clean(row['text'])==word]
    return rows[0] if len(rows)==1 else None


def press(service,context,word,before):
    """One press of 1회 or 10회. True when the count fell by exactly its cost."""
    row=button(service,word)
    if row is None:
        LOG.info('가호 소환 중단 · %s 버튼 미확인',word);return False
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(row['rx'],row['ry']))
    want=before-COSTS[word]
    end=time.monotonic()+8
    while time.monotonic()<end:
        context.wait(.5)
        now=tickets(service,context)
        if now==want:return True
        if now is not None and now!=before:
            LOG.info('가호 소환 중단 · 소환권 %d → %d · 예상 %d',before,now,want);return False
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
