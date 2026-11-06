"""Whether the blessing screen's 일괄 획득 may be pressed, at 1366x768. The owner's rule: any blessing without 귀속 in its name
stops it, so a tradeable one is never swept up. Anything that cannot be read stops it too.

Each tile of the list is clicked once and closed with its X. A second click on a selected tile would equip or unequip it.
"""
import logging,time
import numpy as np
import owner_hd as hd
import owner_text as text
import owner_worn_stats as worn

LOG=logging.getLogger('project_gui.DKB')
ALL_TAB=(1331,92)
TILE_X=(1092,1152,1212,1272);TILE_Y=(152,212,272,332)  # the most the list shows without scrolling: 16
TILE_SPREAD=20
COMPARE_TAB=(695,303,60,24);COMPARE_TITLE=(685,155,215,32);COMPARE_CLOSE=(907,171)  # a spare's window, right of the worn one's


def tile_count(frame):
    """How many places of the list hold a tile, in order. The printed count did not read, and a tile is plain to see: an
    empty place varies by 5 at most and a tile by 40 or more."""
    real=np.asarray(frame.hi).astype(np.float32);count=0
    for x,y in places(len(TILE_X)*len(TILE_Y)):
        if real[y-22:y+22,x-22:x+22].std()<TILE_SPREAD:break
        count+=1
    return count


def window_kind(frame):
    """'worn' for the one window of a worn blessing, 'compare' for the two a spare opens beside the worn one, else None."""
    real=np.asarray(frame.hi)
    if worn.real_popup(real):return 'worn'
    x,y,w,h=COMPARE_TAB
    return 'compare' if any(text.clean(row['text'])=='정보' for row in text.read_area(None,real[y:y+h,x:x+w],minimum=.6)) else None


def window_title(frame,kind):
    """The clicked blessing's name: in a comparison it is the right-hand window."""
    x,y,w,h=worn.REAL_TITLE if kind=='worn' else COMPARE_TITLE
    return ''.join(text.clean(row['text']) for row in text.read_area(None,np.asarray(frame.hi)[y:y+h,x:x+w],minimum=.5))


def wait_closed(service,context):
    """The window just closed fades out, and a click into the fade is lost."""
    for _ in range(10):
        context.checkpoint();service.check()
        if window_kind(service.capture()) is None:return True
        context.wait(.2)
    return False


def close_window(service,context,kind):
    for attempt in range(3):
        service.click_hit(hd.real_hit(*(worn.REAL_CLOSE if kind=='worn' else COMPARE_CLOSE)))
        for _ in range(12):
            context.wait(.2);context.checkpoint();service.check()
            kind=window_kind(service.capture())
            if kind is None:return
    raise RuntimeError('가호 상세창 종료 결과 미확인')


ACQUIRE=(540,230,330,300)   # real: 가호를 획득하시겠습니까? with 거래 가능 소모 조각 : N개 (a blessing made from pieces)


def acquire_popup(frame):
    """For the 'make this blessing from pieces' window: the tradeable pieces it would use (0 when only 귀속 ones), -1 when
    that count does not read; None when the window is not there. pc1 11-06: unclaimed tiles opened it, not details."""
    import re
    x,y,w,h=ACQUIRE
    rows=[text.clean(row['text']) for row in text.read_area(None,np.asarray(frame.hi)[y:y+h,x:x+w],scale=2,minimum=.5)]
    if not any('획득하시겠습니까' in row for row in rows):return None
    for row in rows:
        found=re.search(r'가능.*?(\d+)개',row)
        if found and '불가' not in row:return int(found[1])
    return -1


LOW_GRADES=('일반','희귀')
POPUP_ROW=(525,845);POPUP_EDGE=357;POPUP_TOP=350   # the slots of the blessings 일괄 획득 makes, in its window


def slot_grade(real,left,top):
    """A slot's grade by its frame colour, inside its top and left edges: grey 일반, blue 희귀 (the list's 희귀 frame is
    (24,35,46), 일반 (36,34,31); the window's 일반 slot (59,56,52)). Any other colour is 영웅 or above."""
    tile=np.asarray(real)[top:top+56,left:left+56].astype(np.float32)
    r,g,b=np.concatenate([tile[3:7,10:46].reshape(-1,3),tile[10:46,3:7].reshape(-1,3)]).mean(0)
    if b>=r+12 and b>=g+5:return '희귀'
    if max(r,g,b)-min(r,g,b)<=12:return '일반'
    return None


def popup_grades(frame):
    """The grades of the blessings shown in the 일괄 획득 window, or None when no slot is found. Each slot is 56 wide, set
    off from the window's plain background (pc1 11-06: four at x 540, 613, 686, 759)."""
    real=np.asarray(frame.hi).astype(np.int32);x0,x1=POPUP_ROW
    row=real[POPUP_EDGE,x0:x1];ground=np.median(real[POPUP_EDGE,x0:x0+8],0)
    apart=list(np.abs(row-ground).sum(1)>15)+[False]
    grades=[];start=None
    for i,on in enumerate(apart):
        if on and start is None:start=i
        if not on and start is not None:
            if 45<=i-start<=65:grades.append(slot_grade(real,x0+start,POPUP_TOP))
            start=None
    return grades or None


def press_acquire(service,context):
    """확인 on 가호를 획득하시겠습니까?, only when it uses no tradeable pieces (user 11-06). True when the window went."""
    frame=service.capture()
    if acquire_popup(frame)!=0:return False
    x,y,w,h=ACQUIRE;real=np.asarray(frame.hi)
    confirm=[row for row in text.read_area(None,real[y:y+h+80,x:x+w],left=x,top=y,scale=2,minimum=.6) if text.clean(row['text'])=='확인']
    if len(confirm)!=1:return False
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(confirm[0]['rx'],confirm[0]['ry']))
    for _ in range(6):
        context.wait(.6)
        if acquire_popup(service.capture()) is None:return True
    return False


def close_acquire(service,context):
    """Its 취소, never 확인: making a blessing spends pieces."""
    import re
    for _ in range(3):
        context.checkpoint();service.check();frame=service.capture()
        if acquire_popup(frame) is None:return True
        x,y,w,h=ACQUIRE;real=np.asarray(frame.hi)
        cancel=[row for row in text.read_area(None,real[y:y+h+80,x:x+w],left=x,top=y,scale=2,minimum=.6) if text.clean(row['text'])=='취소']
        if cancel:service.click_hit(hd.real_hit(cancel[0]['rx'],cancel[0]['ry']))
        else:service.check();service.key(0x1b)
        context.wait(.8)
    return acquire_popup(service.capture()) is None


def places(count):
    return [(x,y) for y in TILE_Y for x in TILE_X][:count]


CLAIM_BUTTON=(1100,695,170,50)   # real pixels around 일괄 획득
DIALOG=(420,230,530,330);TOP_BAND=(400,60,560,50)


def claim(adapter,context,inputs,leave=True):
    """At 1366x768, 일괄 획득 and nothing else: the original job went on to equip and summon as well. True when it ran."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES)
    service.context=context
    if getattr(service.capture(),'hi',None) is None:return False
    try:
        if not worn.open_blessing_screen(service,context):
            LOG.info('가호 일괄 획득 생략 · 가호 화면 안 열림');return True
        # On the 전체 tab, by its own confirmation (user 11-06: no tile-by-tile sweep, which opened every tile and gave up
        # past one screen). The window names the tradeable pieces it would use; only 0 is answered with 확인.
        service.click_hit(hd.real_hit(*ALL_TAB));context.wait(1.2)
        context.checkpoint();service.check();frame=service.capture()
        button=[row for row in text.read(None,frame,CLAIM_BUTTON,scale=2,minimum=.7) if text.clean(row['text'])=='일괄획득']
        if len(button)!=1:
            LOG.info('가호 일괄 획득 생략 · 버튼 글자 미확인');return True
        service.click_hit(hd.real_hit(button[0]['rx'],button[0]['ry']))
        said=watch(service,context)
        LOG.info('가호 일괄 획득 누름 · 화면 문구 %s',said or '없음')
        return True
    finally:
        context.checkpoint()
        if window_kind(service.capture()):close_window(service,context,window_kind(service.capture()))
        if leave:worn.leave_blessing_screen(service,context)


def watch(service,context,seconds=4.0):
    """What the screen says after the press, for the log. A window asking to confirm a claim is answered; any other is left."""
    said=[];end=time.monotonic()+seconds
    while time.monotonic()<end:
        context.wait(.4);context.checkpoint();service.check();frame=service.capture()
        for box in (TOP_BAND,DIALOG):
            for row in text.read(None,frame,box,scale=2,minimum=.7):
                word=text.clean(row['text'])
                if word and word not in said:said.append(word)
        dialog=[text.clean(row['text']) for row in text.read(None,frame,DIALOG,scale=2,minimum=.7)]
        confirm=[row for row in text.read(None,frame,DIALOG,scale=2,minimum=.8) if text.clean(row['text'])=='확인']
        if confirm and any('획득' in word for word in dialog) and not any('판매' in word or '분해' in word for word in dialog):
            tradeable=acquire_popup(frame)
            grades=popup_grades(frame) if tradeable and tradeable>0 else None
            low=grades is not None and grades and all(grade in LOW_GRADES for grade in grades)
            if tradeable and tradeable>0 and low:
                # User 11-06: tradeable pieces may go for 일반 and 희귀; from 영웅 up the claim waits for the slot tabs.
                LOG.info('가호 일괄 획득 · 거래 가능 조각 사용 %d · 일반·희귀만 %d개',tradeable,len(grades))
            elif tradeable!=0:
                why='영웅 이상 포함' if grades else '획득 대상 등급 미확인'
                LOG.info('가호 일괄 획득 안 함 · 거래 가능 조각 사용 %s · %s',tradeable if (tradeable or 0)>0 else '미확인',why)
                cancel=[row for row in text.read(None,frame,DIALOG,scale=2,minimum=.7) if text.clean(row['text'])=='취소']
                if cancel:service.click_hit(hd.real_hit(cancel[0]['rx'],cancel[0]['ry']))
                else:service.key(0x1b)
                context.wait(1);return said
            service.click_hit(hd.real_hit(confirm[0]['rx'],confirm[0]['ry']));context.wait(1)
    return said


def skip_reason(service,**_):
    """None when every blessing is 귀속 and 일괄 획득 may be pressed, else why not. Whether the button is lit is the original
    routine's own check: a colour taken for unlit here was never seen lit, and it kept every claim from running."""
    context=service.context
    context.checkpoint();service.check()
    service.click_hit(hd.real_hit(*ALL_TAB));context.wait(1.2)
    context.checkpoint();service.check();frame=service.capture()
    count=tile_count(frame)
    if not count:return '가호 목록 수 미확인'
    # A full screen may have more below it, and only what can be read may let 일괄 획득 through.
    if count>=len(TILE_X)*len(TILE_Y):return '가호 목록이 한 화면을 넘을 수 있음 · %d개'%count
    for index,place in enumerate(places(count),start=1):
        context.checkpoint();service.check()
        wait_closed(service,context)
        service.click_hit(hd.real_hit(*place))
        acquire=None
        for _ in range(worn.OPEN_LOOKS):
            context.wait(.2);context.checkpoint();service.check()
            mode=window_kind(service.capture())
            if mode:break
            acquire=acquire_popup(service.capture())
            if acquire is not None:break
        else:return '%d번째 가호 상세창 안 열림'%index
        if acquire is not None:
            # Not owned yet: it is made from pieces, and 일괄 획득 makes it. Only bound pieces may be used.
            close_acquire(service,context)
            if acquire!=0:return '거래 가능 조각을 쓰는 가호 · %s개'%(acquire if acquire>0 else '미확인')
            continue
        context.wait(.3)
        title=window_title(service.capture(),mode)
        close_window(service,context,mode)
        if '귀속' not in title:return '귀속 없는 가호 · %s'%(title or '제목 미확인')
    LOG.info('가호 일괄 획득 확인 · %d개 전부 귀속',count)
    return None
