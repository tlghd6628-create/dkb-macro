"""장비 분해 at 1366x768, from the bag's own disassembly dialog, by the grades ticked on 보상·정리.

The dialog keeps the last choice: it opened with 일반 and 희귀 on and 강화된 물품 포함 ticked, rare items already marked
(pc1 11-06). So everything is turned off first and the empty reward preview proves nothing is chosen; then only the
ticked grades go on. Every tile that changed between those two looks must have been a grade allowed: one blue (희귀) or
purple (영웅) tile marked when only 일반 is ticked cancels the dialog. 강화된 물품 포함 stays off, so an enhanced item is
never taken. Grade buttons are lit when on (mean ~130-147) and dark when off (~65-88); the box reads ~72 ticked, ~24 not.
"""
import logging,time
import numpy as np
import owner_hd as hd
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
OPEN_ICON=(1335,735)
TITLE=(880,235,90,30);DIALOG=(800,230,250,290);ACTIONS=(800,475,250,45)
BUTTONS=(('일반',(872,412)),('희귀',(938,412)),('영웅',(1005,412)))
BOX=(825,448);CANCEL=(864,495)
PREVIEW=(810,305,230,60)
ON=110;OFF=100;BOX_ON=50;BOX_OFF=40
ORDER=('일반','희귀','영웅')


class Hold(RuntimeError):pass


def real(service):return np.asarray(service.capture().hi)


def words(service,box,minimum=.6):
    x,y,w,h=box;im=real(service)
    return [dict(row,word=text.clean(row['text'])) for row in text.read_area(None,im[y:y+h,x:x+w],left=x,top=y,scale=2,minimum=minimum)]


def is_open(service):
    found=[row['word'] for row in words(service,DIALOG)]
    return '분해' in found and '취소' in found


def brightness(im,place,half=(28,10)):
    x,y=place;dx,dy=half
    return float(im[y-dy:y+dy,x-dx:x+dx].reshape(-1,3).mean())


def states(service):
    """({grade: on}, box ticked) or Hold when any of them is between lit and dark."""
    im=real(service);result={}
    for name,place in BUTTONS:
        value=brightness(im,place)
        if value>=ON:result[name]=True
        elif value<=OFF:result[name]=False
        else:raise Hold('분해 등급 버튼 상태 미확인 · %s %.0f'%(name,value))
    value=brightness(im,BOX,(9,9))
    if value>=BOX_ON:box=True
    elif value<=BOX_OFF:box=False
    else:raise Hold('강화된 물품 포함 상태 미확인 · %.0f'%value)
    return result,box


def preview_empty(service):
    x,y,w,h=PREVIEW
    return float(real(service)[y:y+h,x:x+w].astype(np.float32).std())<8


def toggle(service,context,place,check):
    """One press and wait for it to show; never a second press on the same control."""
    service.click_hit(hd.real_hit(*place))
    end=time.monotonic()+2
    while time.monotonic()<end:
        context.wait(.25);context.checkpoint();service.check()
        try:
            if check():return
        except Hold:pass
    raise Hold('분해 창 선택 반영 확인 필요')


def changed_tiles(before,after):
    """Bag places whose tile changed between two looks: the ones the selection marked."""
    from owner_upgrade_equip import BAG_X,BAG_Y
    out=[]
    for y in BAG_Y:
        for x in BAG_X:
            a=before[y-24:y+24,x-24:x+24].astype(np.float32);b=after[y-24:y+24,x-24:x+24].astype(np.float32)
            if float(np.abs(a-b).mean())>12:out.append((x,y))
    return out


def grade_colour(im,place):
    """'일반' for a grey tile, '높음' for a blue or purple one, from the look before any mark."""
    from owner_upgrade_equip import above_common
    return '높음' if above_common(im,place) else '일반'


def before_disassembly(adapter,context,inputs):
    """The user's order (11-06): the existing higher-grade check and gear growth run first, as they are, so the items
    they take (a spare worn now, a twin used to awaken) are gone before anything is ground."""
    from owner_upgrade_equip import run as equip
    from owner_worn_growth import growth_switches,run as grow
    LOG.info('장비 분해 전 · 높은 등급 장착 확인 · %s',equip(adapter,context,inputs,'gear'))
    if not growth_switches(adapter.project.root)['gear']:
        LOG.info('장비 분해 전 · 장비 성장 기능 꺼짐 · 성장 생략');return
    old=adapter.values
    # A TEST or a timed job exposes only its own switch; the saved one decides here, gear only.
    adapter.values=dict(old,**{'auto_growth.equipment.enabled':True,'auto_growth.blessing.enabled':False})
    try:grow(adapter,context,inputs)
    finally:adapter.values=old
    LOG.info('장비 분해 전 · 장비 성장 차례 끝')


def run(adapter,context,inputs,desired):
    """desired: (일반, 희귀, 영웅) booleans. An outcome dict like the original's."""
    from project_adapter.town_services import TownServices
    from project_adapter import market_inventory
    from owner_progression import open_inventory_by_key
    import owner_worn_stats as worn
    service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES);service.context=context
    want={name:bool(on) for name,on in zip(ORDER,desired)}
    grades=[name for name,on in want.items() if on]
    from owner_upgrade_equip import plain_grid,restore_grouping
    grouped=None
    try:
        open_inventory_by_key(service);context.wait(1.5)
        # The marked tiles are checked on the plain grid; the sorted view moves every row.
        grouped=plain_grid(service,context)
        if grouped is None:raise Hold('가방 정렬 보기 상태 미확인')
        service.click_hit(hd.real_hit(*OPEN_ICON));context.wait(1.8)
        if not is_open(service):return {'state':'not_attempted','reason':'분해 창 안 열림','verified':False}
        # Everything off, the box too: nothing may stay chosen from the last time.
        current,box=states(service)
        if box:toggle(service,context,BOX,lambda:states(service)[1] is False)
        for name,place in BUTTONS:
            if states(service)[0][name]:toggle(service,context,place,lambda name=name:states(service)[0][name] is False)
        context.wait(.5)
        if not preview_empty(service):raise Hold('모두 끈 뒤에도 분해 대상 남음')
        before=real(service).copy()
        for name,place in BUTTONS:
            if want[name]:toggle(service,context,place,lambda name=name:states(service)[0][name] is True)
        context.wait(.8)
        current,box=states(service)
        if current!=want or box:raise Hold('분해 등급 선택 불일치 · %s'%current)
        if preview_empty(service):
            LOG.info('장비 분해 · 선택한 등급에 분해할 장비 없음 · %s',', '.join(grades))
            return {'state':'not_attempted','reason':'선택한 등급에 분해 가능한 장비 없음','verified':False}
        after=real(service)
        marked=changed_tiles(before,after)
        if not marked:raise Hold('분해 대상 칸 확인 실패')
        colours=[grade_colour(before,place) for place in marked]
        if not want['희귀'] and not want['영웅'] and '높음' in colours:
            raise Hold('일반만 선택했는데 높은 등급 칸이 표시됨 · %d개'%colours.count('높음'))
        LOG.info('분해 등급 확인 · %s · 강화된 물품 제외 · 표시된 칸 %d개',', '.join(grades),len(marked))
        go=[row for row in words(service,ACTIONS) if row['word']=='분해']
        if len(go)!=1:raise Hold('분해 실행 버튼 미확인')
        held=bag_count(service)
        context.checkpoint();service.check()
        service.click_hit(hd.real_hit(go[0]['rx'],go[0]['ry']))
        said=watch(service,context)
        left=bag_count(service)
        # The dialog stays open after it works (pc1 06:44: 127 → 126, its preview emptied); the bag's count says it.
        done=held is not None and left is not None and left<held
        LOG.info('장비 분해 누름 · 가방 %s → %s · 화면 문구 %s',held,left,said or '없음')
        return {'state':'confirmed' if done else 'sent_unconfirmed','reason':'가방 수량 %s → %s'%(held,left) if done else '분해 결과 확인 필요',
                'grades':grades,'verified':done}
    except Hold as exc:
        LOG.info('장비 분해 보류 · %s',exc)
        return {'state':'not_attempted','reason':str(exc),'verified':False}
    finally:
        context.checkpoint()
        if is_open(service):
            cancel=[row for row in words(service,ACTIONS) if row['word']=='취소']
            if cancel:service.click_hit(hd.real_hit(cancel[0]['rx'],cancel[0]['ry']));context.wait(1)
        restore_grouping(service,context,grouped)
        worn.close_bag(service,context)


BAG_COUNT=(1080,116,110,28)   # 127/400 beside the bag's tabs


def bag_count(service):
    """Items in the bag (127 of 127/400), once two looks agree, or None."""
    import re
    looks=[]
    for _ in range(3):
        found=[re.fullmatch(r'\D*(\d{1,3})/(\d{2,3})',row['word']) for row in words(service,BAG_COUNT,minimum=.5)]
        found=[int(m[1]) for m in found if m]
        looks.append(found[0] if len(found)==1 else None)
        if len(looks)>=2 and looks[-1] is not None and looks[-1]==looks[-2]:return looks[-1]
        service.context.wait(.3)
    return None


def watch(service,context,seconds=5.0):
    """After 분해: a window asking to confirm the disassembly is answered once; what the screen says is kept for the log."""
    said=[];end=time.monotonic()+seconds;answered=False
    while time.monotonic()<end:
        context.wait(.4);context.checkpoint();service.check()
        rows=words(service,(400,180,600,420))
        for row in rows:
            if row['word'] and row['word'] not in said:said.append(row['word'])
        texts=[row['word'] for row in rows]
        confirm=[row for row in rows if row['word'] in ('확인','지금분해')]
        if not answered and confirm and any('분해' in t for t in texts) and not any('판매' in t for t in texts):
            service.click_hit(hd.real_hit(confirm[0]['rx'],confirm[0]['ry']));answered=True;context.wait(1)
    return said[:12]
