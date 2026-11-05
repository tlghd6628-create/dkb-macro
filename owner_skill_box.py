"""Level-30 commemorative choice box: one box per wanted skill, never more.

Screens seen on 2026-11-05: the box detail popup shows its count, 상자 열기 opens 물품 선택하기
with a scrolling list of fragment rows, 결정 spends one box and returns to the popup.
A sent box that shows no count drop stays pending, so it is never sent twice.
"""
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
import logging,re,time
import cv2,numpy as np
from PIL import Image
from owner_skill_goal import Pending
LOG=logging.getLogger('project_gui.DKB')
ROWS=(395,155,145,155);CLOSE=(510,106);DECIDE=(448,357)
MANUALS=('절명','연타','강타','척살','저격','주술','파멸','강인','기동','기만','헌신','제압')
REAL_GRID=(1062,130,1320,768);REAL_CELL_SCORE=.75


@lru_cache(maxsize=4)
def reference(name):
    return np.asarray(Image.open(Path(__file__).parent/'assets/skill-box'/(name+'.png')).convert('RGB'))


def on_dialog(frame):
    if getattr(frame,'shape',None)!=(479,897,3):return False
    return float(cv2.matchTemplate(frame[100:130,400:500],reference('choice-title'),cv2.TM_CCOEFF_NORMED).max())>=.95


def _real_cell(real,asset,layout):
    """A real-size cut over the whole bag grid. Across 156 saved 1366x768 frames a box on screen measured .83 to 1.0
    and the best other tile .48; the old cut, enlarged or not, misses the 요령서 box."""
    from owner_hd import logical_of
    needle=reference(asset+'-real');h,w=needle.shape[:2];x0,y0,x1,y1=REAL_GRID
    result=cv2.matchTemplate(real[y0:y1,x0:x1],needle,cv2.TM_CCOEFF_NORMED)
    y,x=np.unravel_index(result.argmax(),result.shape)
    return logical_of(x0+int(x)+w//2,y0+int(y)+h//2,layout) if float(result.max())>=REAL_CELL_SCORE else None


def box_cell(frame,asset='choice-box'):
    """Centre of the box in the bag grid, from the part of its tile the count never covers."""
    if getattr(frame,'shape',None)!=(479,897,3):return None
    real=getattr(frame,'hi',None)
    if real is not None:return _real_cell(np.asarray(real),asset,getattr(frame,'layout',None))
    result=cv2.matchTemplate(frame[85:430,712:858],reference(asset),cv2.TM_CCOEFF_NORMED)
    y,x=np.unravel_index(result.argmax(),result.shape)
    return (712+int(x)+14,85+int(y)+15) if float(result.max())>=.90 else None


def row_selected(frame,y):
    """A picked row gets a white rim and the decide button lights up."""
    return float(frame[y-18:y-16,365:530].mean())>110 and float(frame[347:367,410:488].mean())>110


def row_for(rows,name):
    """Row of this skill, by a name close enough that 방패 치기 (.75) cannot pass for 방패 밀기."""
    from owner_skill_ui import clean
    for row in rows:
        body=clean(row['text'])
        if clean(name) in body:return row
        words=row['text'].replace('[','').replace(']','').split()
        if len(words)>=3 and SequenceMatcher(None,clean(''.join(words[1:-2])),clean(name)).ratio()>=.8:return row
    return None


def _scroll(ui):
    """Held at the end so the list stops where it was left: a flick glides past rows."""
    start,end=(445,300),(445,160)
    if not on_dialog(ui.frame()):raise Pending('도술 상자 목록 이동 전 화면 변경')
    with ui.inputs.transaction():
        ui.inputs.move(*start);ui.context.wait(.08);ui.inputs.down('mouse','left');ui.context.wait(.1)
        try:
            for n in range(1,17):
                ui.context.checkpoint();ui.inputs.move(start[0],start[1]+(end[1]-start[1])*n//16);ui.context.wait(.03)
            ui.context.wait(.25)
        finally:ui.inputs.up('mouse','left')
    ui.context.wait(1.)


def count(ui):
    """Boxes left, from the digit of the popup's '4개'. Whole, its 3 reads as 8 at .86; alone, as 3 at .70."""
    for attempt in range(6):
        try:
            for row in ui.rows((480,118,48,40),pair_minimum=.8):
                found=re.fullmatch(r'(\d+)\s*개',row['text'].strip())
                if found and row['score']>=.9:return int(found[1])
            for row in ui.rows((482,140,14,18),language='number',pair_minimum=.6):
                if re.fullmatch(r'[1-5]',row['text'].strip()) and row['score']>=.65:return int(row['text'])
        except Pending:pass
        ui.context.wait(.5)
    raise Pending('도술 상자 수량 확인 필요')


def _open_bag(ui):
    from owner_progression import open_inventory_by_key,inventory_parts
    from owner_inventory_filters import choose
    if inventory_parts(ui.frame())!=(True,True) and open_inventory_by_key(ui.service) is False:
        raise Pending('도술 상자 전 인벤토리 열기 확인 필요')
    from owner_energy_box_runtime_candidate import Hold
    for attempt in range(4):
        # The tab highlight can take longer than choose() looks for, and it must not end the job.
        try:
            choose(ui.service,ui.context,'consumables');ui.context.wait(.4);return
        except Hold as exc:
            if attempt==3:raise Pending(str(exc)) from exc
            ui.context.wait(.6)


def _close_bag(ui):
    from owner_progression import inventory_parts
    from owner_energy_box_detail_candidate import generic_box_detail
    end=time.monotonic()+8
    while time.monotonic()<end:
        frame=ui.frame()
        if on_dialog(frame):ui.click(534,115,on_dialog)
        elif generic_box_detail(frame):ui.click(CLOSE[0],CLOSE[1],generic_box_detail)
        elif inventory_parts(frame)==(True,True):ui.key(0x49)
        elif not any(inventory_parts(frame)):return
        ui.context.wait(.6)
    raise Pending('도술 상자 후 인벤토리 닫기 확인 필요')


def _settle(journal,state,left):
    """What an earlier sent box did, from the count it left behind."""
    pending=state['pending']
    if left==pending['boxes_before']-1:
        state['receipts'].append({'sid':pending['sid'],'name':pending['name'],'at':time.time()})
    elif left!=pending['boxes_before']:raise Pending('이전 도술 상자 수량 불일치')
    state['pending']=None;journal.save(state)


def _detail(ui,cell,asset):
    """Popup of this box, with its count."""
    from owner_energy_box_detail_candidate import generic_box_detail
    ui.click(cell[0],cell[1],lambda f:box_cell(f,asset)==cell)
    return ui.wait(generic_box_detail,seconds=4),count(ui)


def _open_dialog(ui,frame):
    from owner_energy_box_detail_candidate import generic_box_detail
    from owner_equipment_boxes import UNUSED_ITEM
    button=ui.service.detector.find(UNUSED_ITEM,frame,threshold=.9)
    if not button:raise Pending('선택 상자 열기 버튼 확인 필요')
    ui.click(button[0],button[1],generic_box_detail)
    ui.wait(on_dialog,seconds=4);ui.context.wait(.4)


def _pick(ui,locate,name):
    """Scroll to the row and select it; returns its height."""
    for _ in range(12):
        row=locate(ui.rows(ROWS,pair_minimum=.8))
        if row:break
        _scroll(ui)
    else:raise Pending('선택 상자 목록에 없음: '+name)
    y=row['y']
    ui.click(445,y,on_dialog);ui.wait(lambda f:on_dialog(f) and row_selected(f,y),seconds=3)
    return y


def claim(ui,ledger,sid,name):
    """Take this skill's fragments from one box. Returns True once they were received."""
    from owner_coupon_box_candidate import CouponBoxJournal
    from owner_energy_box_detail_candidate import generic_box_detail
    journal=CouponBoxJournal(ui.adapter.project.root,ledger.receipt_key);state=journal.read()
    if any(row.get('sid')==sid for row in state['receipts']):raise Pending('받은 도술 조각의 학습 행 확인 필요: '+name)
    try:
        _open_bag(ui);cell=box_cell(ui.frame())
        if cell is None:
            if state['pending'] and state['pending']['boxes_before']==1:_settle(journal,state,0)
            raise Pending('도술 선택 상자 없음')
        frame,left=_detail(ui,cell,'choice-box')
        if state['pending']:_settle(journal,state,left)
        if any(row.get('sid')==sid for row in journal.read()['receipts']):return True
        _open_dialog(ui,frame)
        y=_pick(ui,lambda rows:row_for(rows,name),name)
        amount=[r for r in ui.rows((425,318,50,20),pair=False) if re.match(r'1\s*/',r['text'])]
        if not amount:raise Pending('도술 상자 수량 1개 확인 필요')
        state=journal.read()
        state['pending']={'phase':'sent','sid':sid,'name':name,'boxes_before':left,'at':time.time()};journal.save(state)
        ui.click(DECIDE[0],DECIDE[1],lambda f:on_dialog(f) and row_selected(f,y))
        LOG.info('도술 상자 사용 · %s · 남은 상자 %d',name,left)
        ui.wait(lambda f:not on_dialog(f),seconds=5)
        if left>1:
            # The reward banner covers the popup for about 3 seconds after the box opens.
            ui.wait(generic_box_detail,seconds=8)
            for attempt in range(12):
                try:
                    if count(ui)==left-1:break
                except Pending:pass
                ui.context.wait(.7)
            else:raise Pending('도술 조각 수령 후 상자 수량 확인 필요')
            _settle(journal,journal.read(),left-1)
        else:
            ui.context.wait(3);_settle(journal,journal.read(),0)
        LOG.info('도술 조각 수령 확인 · %s',name)
        return True
    finally:_close_bag(ui)


def manual_row(rows,style):
    """Row of a manual, by its place in the fixed order when its small two-letter style is misread."""
    from owner_skill_ui import clean
    rows=sorted(rows,key=lambda r:r['y']);place=MANUALS.index(style)
    named=[(row,next((MANUALS.index(s) for s in MANUALS if clean(row['text']).startswith(clean(s))),None)) for row in rows]
    for index,(row,found) in enumerate(named):
        if found==place:return row
    for index,(row,found) in enumerate(named):
        if found is not None:
            at=index+place-found
            if 0<=at<len(rows) and named[at][1] is None and abs(rows[at]['y']-(row['y']+(place-found)*38))<=6:return rows[at]
    return None


def open_manuals(ui,ledger,style):
    """All 강화 요령서 선택 첩 into the one chosen manual, in a single decide.

    A repeat can only give more of the same manual, so no record guards it. The tile going away is the proof.
    """
    from owner_energy_box_detail_candidate import generic_box_detail
    if style not in MANUALS:return 'off'
    try:
        _open_bag(ui);cell=box_cell(ui.frame(),'manual-box')
        if cell is None:return 'none'
        ui.click(cell[0],cell[1],lambda f:box_cell(f,'manual-box')==cell)
        _open_dialog(ui,ui.wait(generic_box_detail,seconds=4))
        y=_pick(ui,lambda rows:manual_row(rows,style),style)
        ui.click(528,327,lambda f:on_dialog(f) and row_selected(f,y));ui.context.wait(.5)
        ui.click(DECIDE[0],DECIDE[1],lambda f:on_dialog(f) and row_selected(f,y))
        LOG.info('요령서 상자 사용 · %s',style)
        ui.wait(lambda f:not on_dialog(f),seconds=5);ui.context.wait(4)
        frame=ui.frame()
        if generic_box_detail(frame):return 'left'
        return 'left' if box_cell(frame,'manual-box') else 'opened'
    finally:_close_bag(ui)