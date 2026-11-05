"""Narrow visual guards around existing native reward recognition, no inputs."""
from functools import lru_cache,wraps
from pathlib import Path


@lru_cache(maxsize=3)
def asset(name):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets/reward-proof'/name).convert('L'))


def ink(frame,minimum,spread):
    import numpy as np
    return ((frame.min(2)>minimum)&(np.ptp(frame.astype('int16'),axis=2)<spread)).astype('uint8')*255


def match(mask,needle):
    import cv2,numpy as np
    if mask.shape[0]<needle.shape[0] or mask.shape[1]<needle.shape[1]:return False
    scores=cv2.matchTemplate(mask,needle,cv2.TM_CCOEFF_NORMED)
    return bool(np.any(np.isfinite(scores)&(scores>=.98)))


def locked_slot(frame,box):
    x1,y1,x2,y2=map(int,box)
    # The lock sits above the native yellow-glow sample, at the item corner.
    region=frame[max(0,y1-25):y1,min(897,max(0,x1-7)):min(897,x1+19)]
    if not region.size:return True
    mask=ink(region,200,65)
    return any(match(mask,asset(name)) for name in ('padlock.png','padlock-gold.png'))


@lru_cache(maxsize=1)
def _dot_shape():
    import numpy as np
    from PIL import Image
    return _redness(np.asarray(Image.open(Path(__file__).parent/'assets/reward-proof/notice-dot.png').convert('RGB')))


def _redness(rgb):
    import numpy as np
    pixels=rgb.astype('int16')
    return np.clip(pixels[:,:,0]-pixels[:,:,1:].max(axis=2),0,255).astype('uint8')


def _real_dots(frame,box):
    """The same dots on the real pixels, where they keep their colour. Small, round and red."""
    import cv2,numpy as np
    from owner_hd import real_box,logical_of,SHIFTS,F
    real=np.asarray(frame.hi);x,y,w,h=box
    left,top=max(0,round(x*F+SHIFTS['right'])),max(0,round(y*F));right,bottom=min(real.shape[1],round((x+w)*F)),min(real.shape[0],round((y+h)*F))
    part=real[top:bottom,left:right].astype('int16');r,g,b=part[:,:,0],part[:,:,1],part[:,:,2]
    # A dot's white shine leaves holes, and can split it in two: its parts filled 33% of its box and it was never seen (11-06).
    mask=cv2.morphologyEx(((r>170)&(g<95)&(b<95)).astype('uint8'),cv2.MORPH_CLOSE,np.ones((3,3),'uint8'))
    count,_,stats,_=cv2.connectedComponentsWithStats(mask,8);found=[]
    for index in range(1,count):
        l,t,width,height,area=(int(v) for v in stats[index])
        if not (6<=width<=13 and 6<=height<=13 and abs(width-height)<=2 and area>=.35*width*height):continue
        cx,cy=left+l+width//2,top+t+height//2
        # Red art shares the colour. The same shape as on the small frame: dots .85-.93, the rest under .75 on the saved screens.
        crop=real[max(0,cy-16):cy+17,max(0,cx-16):cx+17];shape=_real_dot_shape()
        if crop.shape[0]<shape.shape[0] or crop.shape[1]<shape.shape[1] or float(cv2.matchTemplate(_redness(crop),shape,cv2.TM_CCOEFF_NORMED).max())<.8:continue
        at=logical_of(cx,cy,frame.layout)
        # The search above is wide enough for every anchor, so it also takes in the tab list's dots. A tab's
        # dot taken for a claimable row was pressed as a reward (11-05 17:32), and the row's own was never looked at.
        if x<=at[0]<x+w and y<=at[1]<y+h:found.append(at)
    return found


@lru_cache(maxsize=1)
def _real_dot_shape():
    import cv2
    return cv2.resize(_dot_shape(),None,fx=1.6,fy=1.6,interpolation=cv2.INTER_CUBIC)


# Real pixels of the point panel in the event window: its title, its total, and the column of each prize's points.
POINT_TITLE=(960,350,115,28);POINT_TOTAL=(1075,350,45,28);POINT_COLUMN=(1068,48);POINT_PANEL_LEFT=620


def _digits(area,left,top):
    """The one number in this array of real pixels, or None. A single digit misreads (6 as O), and then nothing is decided."""
    import re
    from owner_text import read_area,clean
    rows=[clean(row['text']) for row in read_area(None,area,left=left,top=top,scale=4,minimum=.8)]
    return int(rows[0]) if len(rows)==1 and re.fullmatch(r'\d{1,3}',rows[0]) else None


def short_of_points(frame,box):
    """A prize in the point panel needing more points than the total. Pressing one only opens its detail card (11-05
    17:32). Nothing is decided on a frame with no real pixels, in another tab, or when a number does not read."""
    real=getattr(frame,'hi',None)
    if real is None or box[0]<POINT_PANEL_LEFT:return False
    import numpy as np
    from owner_text import read_area,clean
    real=np.asarray(real);x,y,w,h=POINT_TITLE
    if not any('누적포인트' in clean(row['text']) for row in read_area(None,real[y:y+h,x:x+w],left=x,top=y)):return False
    x,y,w,h=POINT_TOTAL;total=_digits(real[y:y+h,x:x+w],x,y)
    if total is None:return False
    x,w=POINT_COLUMN;y=round((box[1]+box[3])/2*1.6)-16
    need=_digits(real[y:y+32,x:x+w],x,y)
    return need is not None and need>total


PRIZE_X=(989,1025);PRIZE_COLUMN=(385,625);PRIZE_HALF=18;PRIZE_COLOUR=130;PRIZE_OPEN=.15
# Real pixels: the bar of a mission row cut by the top of the list, and where its coin still shows.
CUT_BAR=(475,343,370,14);CUT_COIN=(896,350);CUT_BRIGHT=140;RANGE_TOP=204


def open_prizes(frame):
    """Real places of point prizes already earned and not taken. Their own mark is too faint to find, but the numbers say
    which are earned, and a taken one is dark with a tick: colour on .26 or more of it untaken, .07 or less taken (11-06)."""
    real=getattr(frame,'hi',None)
    if real is None:return []
    import numpy as np,re
    from owner_text import read_area,clean
    real=np.asarray(real);x,y,w,h=POINT_TITLE
    if not any('누적포인트' in clean(row['text']) for row in read_area(None,real[y:y+h,x:x+w],left=x,top=y)):return []
    x,y,w,h=POINT_TOTAL;total=_digits(real[y:y+h,x:x+w],x,y)
    if total is None:return []
    x,w=POINT_COLUMN;top,bottom=PRIZE_COLUMN;found=[]
    for row in read_area(None,real[top:bottom,x:x+w],left=x,top=top,scale=4,minimum=.8):
        need=clean(row['text'])
        if not re.fullmatch(r'\d{1,3}',need) or int(need)>total:continue
        ry=row['ry'];icon=real[ry-PRIZE_HALF:ry+PRIZE_HALF,PRIZE_X[0]:PRIZE_X[1]]
        if icon.size and float((icon.max(axis=2)>PRIZE_COLOUR).mean())>PRIZE_OPEN:found.append(((PRIZE_X[0]+PRIZE_X[1])//2,ry))
    return found


def cut_finished_row(frame):
    """The coin of a finished, untaken mission row whose top the list cuts off, or None. Its dot is above the list, so
    nothing else finds it, and the list keeps its scroll per tab (2일차, 11-06). Its bar reads N / N and is bright: 156
    untaken, 123 once taken. The coin's lower half still takes the press."""
    real=getattr(frame,'hi',None)
    if real is None:return None
    import numpy as np,re
    from owner_text import read_area,clean
    real=np.asarray(real);x,y,w,h=CUT_BAR;bar=real[y:y+h,x:x+w]
    if not bar.size or float(np.median(bar.reshape(-1,3)[:,0]))<=CUT_BRIGHT:return None
    for row in read_area(None,bar,left=x,top=y,scale=4,minimum=.6):
        found=re.fullmatch(r'(\d+)/(\d+)',clean(row['text']).replace(' ',''))
        if found and found[1]==found[2] and int(found[1])>0:return CUT_COIN
    return None


ADDED=[];ADDED_LIFE=5.0


def add(box,check):
    """A box this guard put into the native list, with what still has to read true before its press."""
    import time
    now=time.monotonic();ADDED[:]=[row for row in ADDED if now-row[0]<=ADDED_LIFE and row[1]!=box]+[(now,box,check)]


def added_here(hit):
    """The check for an added box this hit falls in, or None."""
    import time
    now=time.monotonic();x,y=hit[0],hit[1]
    for seen,(x0,y0,x1,y1),check in reversed(ADDED):
        if now-seen<=ADDED_LIFE and x0<=x<=x1 and y0<=y<=y1:return check
    return None


def notice_dots(frame,box=(305,204,420,182)):
    """Centres of real notification dots. Red art (a potion, a pattern inside a
    gold item) shares the colour but not this small round shape."""
    import cv2,numpy as np
    if getattr(frame,'hi',None) is not None:return _real_dots(frame,box)
    x,y,w,h=box;part=frame[y:y+h,x:x+w].astype('int16');r,g,b=part[:,:,0],part[:,:,1],part[:,:,2]
    mask=((r>170)&(g<95)&(b<95)).astype('uint8')
    count,_,stats,_=cv2.connectedComponentsWithStats(mask,8);shape=_dot_shape();found=[]
    for index in range(1,count):
        left,top,width,height,area=(int(v) for v in stats[index])
        if not (4<=width<=7 and 4<=height<=7 and area>=9):continue
        cx,cy=left+x+width//2,top+y+height//2;crop=frame[cy-7:cy+8,cx-7:cx+8]
        if crop.shape!=(15,15,3):continue
        # The mark's own bounds put its centre up to a pixel off: a real row dot
        # scored .61 centred and .94 one pixel over, and was never claimed.
        if float(cv2.matchTemplate(_redness(crop),shape,cv2.TM_CCOEFF_NORMED).max())>=.8:found.append((cx,cy))
    return found


def gold_inside(frame,box,inset=8):
    x1,y1,x2,y2=map(int,box);part=frame[y1+inset:y2-inset,x1+inset:x2-inset].astype('int16')
    if not part.size:return 1.
    r,g,b=part[:,:,0],part[:,:,1],part[:,:,2]
    return float(((r>170)&(g>120)&(b<110)&(r-b>70)).mean())


def marked(frame,box):
    """A claim glow is only a rim, with the item's own colour inside (real pass
    reward .00-.04). A gold-grade prize is gold through the middle (.45), and
    is claimable only when a notification dot sits at its corner."""
    x1,y1,x2,y2=map(int,box)
    return gold_inside(frame,box)<.2 or any(x1-6<=cx<=x2+8 and y1-10<=cy<=y2 for cx,cy in notice_dots(frame))


def near_dot(frame,hit):
    return any(abs(cx-hit[0])<=6 and abs(cy-hit[1])<=6 for cx,cy in notice_dots(frame))


def disassembly_result(frame):
    if getattr(frame,'shape',None)!=(479,897,3):return False
    # Actual game toast title "분해". Never generic "아이템 획득" or item art.
    return match(ink(frame[92:114,425:472],180,55),asset('disassembly-toast.png'))


def install():
    from project_adapter import event_rewards as native
    cls=native.EventGlowDetector
    if getattr(cls.find,'_owner_reward_visual_guard',False):return
    original_find,original_recheck,original_boxes=cls.find,cls.recheck_point,cls.boxes
    def opened(detector,frame):
        reader=getattr(detector,'_owner_event_window',None)
        if reader is None:
            from roi_runtime import RoiDetector
            reader=RoiDetector(detector.base.profile,['체크_이벤트'])
            detector._owner_event_window=reader
        return reader.find('체크_이벤트',frame,threshold=.95) is not None
    @wraps(original_find)
    def find(self,name,frame,region=None,threshold=.9,*,candidate_filter=None):
        body=region==native.REWARD_RANGE
        if body and not opened(self,frame):return None
        # A red potion or introduction illustration is not a notification, yet
        # the claimable slots and mission rows are marked by this real dot.
        if body and name==native.DOT:
            if not notice_dots(frame):return None
            def real_dot(f,hit,_given=candidate_filter):
                return near_dot(f,hit) and (_given is None or _given(f,hit))
            return original_find(self,name,frame,region,threshold,candidate_filter=real_dot)
        return original_find(self,name,frame,region,threshold,candidate_filter=candidate_filter)
    @wraps(original_recheck)
    def recheck(self,name,frame,hit,region=None,threshold=.9,radius=2):
        if region==native.REWARD_RANGE and (not opened(self,frame) or (name==native.DOT and not near_dot(frame,hit))):return None
        # A prize or a day tab added below is not the yellow reward picture, so its own reading confirms it again.
        still=added_here(hit)
        if still is not None:return hit if opened(self,frame) and still(frame) else None
        return original_recheck(self,name,frame,hit,region,threshold,radius)
    @wraps(original_boxes)
    def boxes(self,frame,reward_name=None):
        if not opened(self,frame):return []
        # The native search also takes a gold-grade prize for a claim glow:
        # the 7th-day prize and a locked point prize both matched it.
        kept=[(name,box) for name,box in original_boxes(self,frame,reward_name) if not locked_slot(frame,box) and marked(frame,box) and not short_of_points(frame,box)]
        if reward_name in (None,native.REWARD):
            # The native reward search reads only this list, so a marked slot or
            # mission row joins it and takes the same click and recheck path.
            e=self.base.entries[native.REWARD];w,h=e['w'],e['h']
            for cx,cy in notice_dots(frame):
                if not any(box[0]-6<=cx<=box[2]+8 and box[1]-10<=cy<=box[3] for _,box in kept):
                    # The native click compares a region of exactly the image's size.
                    l,t=min(897-w,max(0,cx-w//2)),min(479-h,max(0,cy-h//2))
                    kept.append((native.REWARD,(l,t,l+w,t+h)))
            def press(at,still):
                # The native search crops inside its range, so a box never starts above it (an empty crop ended a
                # run, 11-06 03:36). Its press is sent to the real place found, and the place is read again first.
                from owner_hd import logical_of,pin_box
                cx,cy=logical_of(*at,frame.layout)
                l,t=min(897-w,max(0,cx-w//2)),min(479-h,max(RANGE_TOP,cy-h//2))
                box=(l,t,l+w,t+h);pin_box(box,*at);add(box,still)
                kept.append((native.REWARD,box))
            for at in open_prizes(frame):press(at,lambda f,_at=at:_at in open_prizes(f))
            cut=cut_finished_row(frame)
            if cut and not kept:press(cut,lambda f:cut_finished_row(f) is not None)
        return kept
    find._owner_reward_visual_guard=True
    cls.find,cls.recheck_point,cls.boxes=find,recheck,boxes
