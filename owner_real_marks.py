"""Small marks on the real 1366x768 screen: the orange worn badge, a window's X, a tab that is lit.

These stand in for pixel-exact checks made on the old 897x479 frame, which a scaled-down frame can never pass. Places
are given in the old terms with the anchor they hold to, so callers keep their boxes.
"""
from functools import lru_cache
from pathlib import Path
import logging
import numpy as np
from owner_hd import real_box

LOG=logging.getLogger('project_gui.DKB')

CLOSE_INK=190;BADGE_MOST=24


def real_of(frame):
    real=getattr(frame,'hi',None)
    return None if real is None else np.asarray(real)


def orange_pixels(part):
    part=np.asarray(part).astype(np.int16)
    return int(((part[:,:,0]-part[:,:,2]>90)&(part[:,:,0]>150)&(part[:,:,1]>70)).sum())


def worn_badge(real,box,rule='center'):
    """The orange E on a tooltip's item icon. Worn badges measure 60 or more orange pixels, anything else under 20."""
    x,y,w,h=real_box(box,rule=rule)
    part=real[y:y+h,x:x+w]
    if not 30<=orange_pixels(part)<=w*h//4:return False
    # A golden box's frame is this colour too, in long strokes. A badge is a small square holding a white E.
    signed=part.astype(np.int16)
    ys,xs=np.where((signed[:,:,0]-signed[:,:,2]>90)&(signed[:,:,0]>150)&(signed[:,:,1]>70))
    if xs.max()-xs.min()>BADGE_MOST or ys.max()-ys.min()>BADGE_MOST:return False
    return int((part[ys.min():ys.max()+1,xs.min():xs.max()+1].min(axis=2)>170).sum())>=6


@lru_cache(maxsize=1)
def _close_ink():
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets/hud/detail-close.png').convert('RGB')).min(axis=2)>CLOSE_INK


def close_at(real,box,rule='center'):
    """A window's X inside this box: all of its ink is lit, a few pixels either way, and little around it is."""
    ink=_close_ink();h,w=ink.shape
    x,y,bw,bh=real_box(box,rule=rule)
    area=real[max(0,y-2):y+bh+2,max(0,x-2):x+bw+2].min(axis=2)>150
    for dy in range(area.shape[0]-h+1):
        for dx in range(area.shape[1]-w+1):
            part=area[dy:dy+h,dx:dx+w]
            if float(part[ink].mean())>=.9 and float(part[~ink].mean())<=.25:return True
    return False


@lru_cache(maxsize=1)
def _map_merchant():
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets/hud/map-merchant.png').convert('RGB'))


def map_merchant(frame):
    """The potion merchant anywhere on the map, as a hit in the old terms. The map centres on the character, so the
    native fixed place only holds right after a return. Measured 1.0 and .89 selected, .795 under the map's rainy tint,
    under .48 on other screens."""
    import cv2
    from owner_hd import logical_of
    real=real_of(frame)
    if real is None:return None
    needle=_map_merchant();h,w=needle.shape[:2];x0,y0=60,60
    _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(real[y0:680,x0:1340],needle,cv2.TM_CCOEFF_NORMED))
    if score<.7:return None
    x,y=logical_of(x0+pos[0]+w//2,y0+pos[1]+h//2,getattr(frame,'layout',None))
    return x,y,(x-8,y-8,x+9,y+9)


MAP_BUTTONS=(1000,700,366,50)  # real pixels: 걸어가기, 축지술, 축지부 사용 along the map's foot


def map_teleport(frame):
    """The map's 축지술 button, in the shape a found picture has. Exactly that word: 축지부 사용 beside it costs an item."""
    from owner_text import clean,logical_bounds,read
    found=[row for row in read(None,frame,MAP_BUTTONS) if clean(row['text'])=='축지술']
    return (found[0]['x'],found[0]['y'],logical_bounds(found[0],frame)) if len(found)==1 else None


ACCOUNT_BUTTONS=(460,490,450,140)  # real pixels: the buttons under the settings' account tab


DEATH_RED=(22,58,600,780);DEATH_RED_FLOOR=.05


def death_mark(frame):
    """체크_사망상태 by the death screen's own words. Its picture scores 58-72% at 1366, so the native runner and every
    native check missed deaths (pc1 11-06 13:51; 짱군네 11-07 15:40, where an overdue 우편 then ran on it). The red title
    letters (.096-.115 of the title band on death frames, .03 or less elsewhere) gate the word read."""
    real=getattr(frame,'hi',None)
    if real is None:return None
    y0,y1,x0,x1=DEATH_RED;band=np.asarray(real)[y0:y1,x0:x1].astype(int)
    if float(((band[...,0]>170)&(band[...,1]<110)&(band[...,2]<110)).mean())<DEATH_RED_FLOOR:return None
    from owner_death_real import dead,TITLE
    if not dead(frame):return None
    from owner_text import logical_bounds,read
    rows=read(None,frame,TITLE,scale=2,minimum=.6)
    return (rows[0]['x'],rows[0]['y'],logical_bounds(rows[0],frame)) if rows else None


RAID_ADMIT_TITLE=(560,195,250,56)   # real: 매칭 입장 (682,223)
RAID_ADMIT_BUTTONS=(500,505,360,48)  # real: 취소 (580,529) and 확인 (778,529)


def _raid_admit_rows(frame):
    """(title, 확인) on the 매칭 입장 popup, or None. 확인 is taken by exactly that word; 취소 on the same row never is."""
    if getattr(frame,'hi',None) is None:return None
    from owner_text import clean,read
    title=read(None,frame,RAID_ADMIT_TITLE,scale=2,minimum=.6)
    if not title or '매칭입장' not in ''.join(clean(r['text']) for r in title):return None
    ok=[r for r in read(None,frame,RAID_ADMIT_BUTTONS,scale=2,minimum=.6) if clean(r['text'])=='확인']
    return (title[0],ok[0]) if len(ok)==1 else None


def _mark(row,frame):
    from owner_text import logical_bounds
    return (row['x'],row['y'],logical_bounds(row,frame))


def raid_admit_title(frame):
    """체크_레이드_매칭입장 at 1366x768. Its picture scores .81 there, so the native wait never saw the popup and let it
    run out (pc2 11-07: 확인 not pressed, then 투표 부결 and a stopped run)."""
    rows=_raid_admit_rows(frame)
    return _mark(rows[0],frame) if rows else None


def raid_admit_confirm(frame):
    """버튼_레이드_매칭입장확인 at 1366x768 (its picture scores .86): the 확인 under the 매칭 입장 title."""
    rows=_raid_admit_rows(frame)
    return _mark(rows[1],frame) if rows else None


RAID_MATCHING_PANEL=(1090,70,270,140)  # real: 레이드 (1204,124), 대기시간00:05경과 (1204,184)


def raid_matching(frame):
    """체크_레이드_매칭중 at 1366x768: the top-right panel's 레이드 and 대기시간 … 경과. The raid never logged its matching
    wait on pc2 (5 tries 11-07), so it kept looking for the raid page while the queue ran."""
    if getattr(frame,'hi',None) is None:return None
    from owner_text import clean,read
    rows=read(None,frame,RAID_MATCHING_PANEL,scale=2,minimum=.6)
    words=[clean(r['text']) for r in rows]
    if not any('레이드' in w for w in words):return None
    wait=[r for r,w in zip(rows,words) if '대기시간' in w and '경과' in w]
    return _mark(wait[0],frame) if wait else None


def coupon_menu(frame):
    """쿠폰등록 on the settings' account tab, by exactly that word. Its picture does not match at 1366x768."""
    from owner_text import clean,logical_bounds,read
    found=[row for row in read(None,frame,ACCOUNT_BUTTONS) if clean(row['text'])=='쿠폰등록']
    return (found[0]['x'],found[0]['y'],logical_bounds(found[0],frame)) if len(found)==1 else None


def install_merchant():
    """Native callers keep their retries: nothing on this map answers as it always has."""
    from functools import wraps
    from project_adapter.town_services import TownServices
    ordinary=TownServices.merchant
    if getattr(ordinary,'_owner_real_merchant',False):return

    @wraps(ordinary)
    def merchant(service):
        frame=service.capture()
        if real_of(frame) is None:return ordinary(service)
        service.check()
        hit=map_merchant(frame)
        # The native one presses what it finds: returning only the place left the map unselected and 축지술 never came.
        if hit is not None:service.click_hit(hit)
        return hit
    merchant._owner_real_merchant=True
    TownServices.merchant=merchant


def lit_pixels(real,box,rule='right',floor=170):
    x,y,w,h=real_box(box,rule=rule)
    return int((real[y:y+h,x:x+w].min(axis=2)>floor).sum())
