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


def places(count):
    return [(x,y) for y in TILE_Y for x in TILE_X][:count]


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
        for _ in range(worn.OPEN_LOOKS):
            context.wait(.2);context.checkpoint();service.check()
            mode=window_kind(service.capture())
            if mode:break
        else:return '%d번째 가호 상세창 안 열림'%index
        context.wait(.3)
        title=window_title(service.capture(),mode)
        close_window(service,context,mode)
        if '귀속' not in title:return '귀속 없는 가호 · %s'%(title or '제목 미확인')
    LOG.info('가호 일괄 획득 확인 · %d개 전부 귀속',count)
    return None
