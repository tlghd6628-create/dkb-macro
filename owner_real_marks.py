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


def lit_pixels(real,box,rule='right',floor=170):
    x,y,w,h=real_box(box,rule=rule)
    return int((real[y:y+h,x:x+w].min(axis=2)>floor).sum())
