"""Small marks on the real 1366x768 screen: the orange worn badge, a window's X, a tab that is lit.

These stand in for pixel-exact checks made on the old 897x479 frame, which a scaled-down frame can never pass. Places
are given in the old terms with the anchor they hold to, so callers keep their boxes.
"""
from functools import lru_cache
from pathlib import Path
import numpy as np
from owner_hd import real_box

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
        return map_merchant(frame)
    merchant._owner_real_merchant=True
    TownServices.merchant=merchant


def lit_pixels(real,box,rule='right',floor=170):
    x,y,w,h=real_box(box,rule=rule)
    return int((real[y:y+h,x:x+w].min(axis=2)>floor).sum())
