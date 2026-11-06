"""Follow a game tutorial's pointing hand at 1366x768 (pc2 follow_hand.py, 11-06; 몽련의 선물 at pc1 01:56).

The hand is a white glove: near-white pixels (min RGB > 235) in one piece, 250-1400 px, 18-60 by 22-70 px, filled
35-85%. Its fingertip is the top-left. To keep white UI from passing for it, the hint's white arrow must stand left
of the glove on its row. The click lands just inside the fingertip.
"""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
ARROW_REACH=320;MAX_STEPS=8


def hand(real):
    import numpy as np,cv2
    a=np.asarray(real)
    if a.ndim!=3:return None
    w=(a.min(axis=2)>235).astype(np.uint8)
    num,lab,st,cen=cv2.connectedComponentsWithStats(w,8)
    best=None
    for i in range(1,num):
        x,y,ww,hh,area=[int(v) for v in st[i]]
        if 250<=area<=1400 and 18<=ww<=60 and 22<=hh<=70 and .35<=area/(ww*hh)<=.85:
            if best is None or area>best[4]:best=(x,y,ww,hh,area)
    if best is None:return None
    x,y=best[0]+4,best[1]+2
    # The hint's white arrow stands left of the glove on its row (q021 1222,193; q090 1014,567; 몽련 1150,535).
    w2=(a.min(axis=2)>200).astype(np.uint8);num2,_,st2,_=cv2.connectedComponentsWithStats(w2,8)
    for i in range(1,num2):
        ax,ay,aw,ah,aa=[int(v) for v in st2[i]]
        if 12<=aw<=22 and 20<=ah<=30 and 140<=aa<=280 and 0<x-ax<=ARROW_REACH and abs((ay+ah//2)-(best[1]+best[3]//2))<=45:
            return x,y
    return None


def follow(service,context,steps=MAX_STEPS):
    """Click the fingertip while a hand shows; when none, tap the centre once for a text-only hint. Returns clicks made."""
    import owner_hd as hd
    clicks=0;miss=0
    for _ in range(steps):
        context.checkpoint()
        real=getattr(service.capture(),'hi',None)
        if real is None:break
        tip=hand(real)
        if tip is None:
            miss+=1
            if miss>=2 or not clicks:break
            service.click_hit(hd.real_hit(683,383));context.wait(1.5);continue
        miss=0
        service.click_hit(hd.real_hit(*tip));clicks+=1
        LOG.info('튜토리얼 손가락 따라 누름 · %d,%d',*tip)
        context.wait(1.5)
    return clicks
