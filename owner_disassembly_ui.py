"""Read grade toggles from the original disassembly dialog, not item artwork."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json,time

CODES=('normal','rare','hero')


class Hold(RuntimeError):pass
class NoItems(Hold):pass


@lru_cache(maxsize=1)
def assets():
    import numpy as np
    from PIL import Image
    root=Path(__file__).parent/'assets/disassembly-grades'
    layout=json.loads((root/'layout.json').read_text(encoding='utf-8'))
    names=('header','empty',*[code+'-'+state for code in CODES for state in ('off','on')])
    return layout,{name:np.asarray(Image.open(root/(name+'.png')).convert('RGB')) for name in names}


@dataclass(frozen=True)
class View:
    origin:tuple
    states:tuple
    empty:bool
    rects:tuple


def header_origin(frame):
    import cv2,numpy as np
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
    layout,images=assets();header=images['header']
    scores=cv2.matchTemplate(frame,header,cv2.TM_CCOEFF_NORMED)
    scores=np.where(np.isfinite(scores),scores,-1)
    _,score,_,pos=cv2.minMaxLoc(scores)
    if score<.99:return None
    # Two different matching dialogs are ambiguous; adjacent pixel matches
    # around the same header are not distinct dialogs.
    ys,xs=np.where(scores>=.99)
    if any(abs(int(x)-pos[0])>2 or abs(int(y)-pos[1])>2 for x,y in zip(xs,ys)):return None
    return pos[0]-layout['header'][0],pos[1]-layout['header'][1]


def observe(frame):
    import cv2,numpy as np
    origin=header_origin(frame)
    if origin is None:return None
    layout,images=assets();dx,dy=origin
    rects=[];states=[]
    for code in CODES:
        x1,y1,x2,y2=layout['boxes'][code];rect=(x1+dx,y1+dy,x2+dx,y2+dy)
        if min(rect)<0 or rect[2]>897 or rect[3]>479:return None
        crop=frame[rect[1]:rect[3],rect[0]:rect[2]];values=[]
        for state in ('off','on'):
            value=float(cv2.matchTemplate(crop,images[code+'-'+state],cv2.TM_CCOEFF_NORMED)[0,0])
            values.append(value if np.isfinite(value) else -1)
        best=int(values[1]>values[0])
        if values[best]<.98 or values[best]-values[1-best]<.10:return None
        states.append(bool(best));rects.append(rect)
    x1,y1,x2,y2=layout['boxes']['empty'];crop=frame[y1+dy:y2+dy,x1+dx:x2+dx]
    blank=images['empty']
    if crop.shape!=blank.shape:return None
    # A flat blank preview cannot use normalized correlation: that metric
    # would report a false perfect match even when a reward icon is present.
    empty=float((np.abs(crop.astype('int16')-blank.astype('int16')).max(axis=2)<=3).mean())>=.995
    return View((dx,dy),tuple(states),empty,tuple(rects))


def pair(service):
    views=[]
    for index in range(2):
        service.context.checkpoint();service.check();views.append(observe(service.capture()))
        if index==0:service.context.wait(.12)
    if views[0] is None or views[0]!=views[1]:raise Hold('분해 등급 선택 화면 두 번 확인 필요')
    return views[1]


def park_pointer(service,origin):
    """Reuse the existing input backend to uncover text; no click or drag."""
    service.context.checkpoint();service.check()
    if header_origin(service.capture())!=origin:raise Hold('분해 창 위치 변경 · 포인터 이동 보류')
    layout,_=assets();dx,dy=origin
    # Outside the dialog, over no recognition ROI. The game's cursor halo
    # covered the grade glyphs in both actual failed 23:48 TEST attempts.
    with service.inputs.transaction():
        service.context.checkpoint();service.check();service.inputs._guard_target()
        service.inputs.move(layout['header'][0]+dx-40,layout['header'][1]+dy+12)


def set_switch(service,raw_click,index,desired):
    current=pair(service)
    if current.states[index]==desired:return current
    x1,y1,x2,y2=current.rects[index]
    service.context.checkpoint();service.check()
    fresh=observe(service.capture())
    if fresh!=current:raise Hold('분해 등급 선택 대상 변경')
    raw_click(service,((x1+x2)//2,(y1+y2)//2,(x1,y1,x2,y2)))
    park_pointer(service,current.origin)
    expected=list(current.states);expected[index]=desired
    deadline=time.monotonic()+1.2
    while True:
        service.context.wait(.08)
        try:after=pair(service)
        except Hold:
            # Only reread the post-click state; never toggle a second time.
            # Stop/Pause exceptions are not Hold and propagate immediately.
            if time.monotonic()>=deadline:raise
            continue
        if after.origin!=current.origin:raise Hold('분해 창 위치 변경')
        if after.states==tuple(expected):return after
        if time.monotonic()>=deadline:raise Hold('분해 등급 선택 반영 확인 필요')


def configure(service,raw_click,desired):
    """Clear old selection, then choose only configured grades. No commit."""
    origin=header_origin(service.capture())
    if origin is None:raise Hold('분해 창 제목 확인 필요')
    park_pointer(service,origin)
    service.context.wait(.08)
    view=pair(service)
    for index in range(3):view=set_switch(service,raw_click,index,False)
    view=pair(service)
    if not view.empty:
        # A manually selected subset may leave all three group toggles off.
        # Use the original group toggles to select then deselect each grade;
        # require the empty reward preview before selecting the desired set.
        for index in range(3):view=set_switch(service,raw_click,index,True)
        for index in range(3):view=set_switch(service,raw_click,index,False)
        view=pair(service)
    if any(view.states) or not view.empty:raise Hold('이전 분해 선택 해제 확인 필요')
    for index in range(3):view=set_switch(service,raw_click,index,desired[index])
    view=pair(service)
    if view.states!=tuple(desired):raise Hold('설정한 분해 등급과 선택 상태 불일치')
    if view.empty:raise NoItems('선택한 등급에 분해 가능한 장비 없음')
    return view
