"""Detect a visually confirmed remote potion limit; never send game input."""
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
import hashlib,re,threading,time

ASSETS=Path(__file__).parent/'assets/remote-potion-limit'
HASHES={'tier1':'4b6962c8724305a680bf7bde2330eab3ffe99acce1461b46cd80e2ca7c9dc0a9',
        'unavailable':'505b0e07069713cc2fc4bfa582f1c83cd4a3b20ef19e5cabb8b15f89b4d4f123'}
TTL=30.0;_LOCK=threading.Lock();_CACHE=OrderedDict()

@lru_cache(maxsize=2)
def _asset(name):
    import numpy as np
    from PIL import Image
    path=ASSETS/(name+'.png')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=HASHES[name]:raise ValueError('물약 한도 이미지 변경')
    with Image.open(path) as source:return np.asarray(source.convert('RGB'))

def _fixed(frame,name,box):
    import cv2,numpy as np
    x,y,w,h=box;patch=frame[y:y+h,x:x+w];needle=_asset(name)
    if patch.shape!=needle.shape:return False
    score=float(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)[0,0])
    # Dim overlays should not reproduce an underlying actionable control.
    difference=float(np.abs(patch.astype('int16')-needle.astype('int16')).mean())
    return bool(np.isfinite(score) and score>=.96 and difference<=15)

def _screen(frame,tier):
    import numpy as np,cv2
    from owner_membership import hit
    if tier!='1단물약' or getattr(frame,'shape',None)!=(479,897,3):return False
    if not hit(frame,'remote-shop-title',(35,4,110,30),.95):return False
    if not _fixed(frame,'tier1',(49,69,84,11)) or not _fixed(frame,'unavailable',(9,81,35,13)):return False
    hsv=cv2.cvtColor(frame[89:106,70:120],cv2.COLOR_RGB2HSV)
    red=((hsv[:,:,0]<12)|(hsv[:,:,0]>165))&(hsv[:,:,1]>60)&(hsv[:,:,2]>28)
    return int(red.sum())>=10

def sold_out(frame,tier):
    """The town merchant's row for this tier says 구매 불가: the weekly amount is used up, so there is nothing to buy.
    The label is the same in every row, one row pitch apart."""
    from owner_membership import hit
    if tier not in ('1단물약','2단물약','3단물약') or getattr(frame,'shape',None)!=(479,897,3):return False
    if not hit(frame,'remote-shop-title',(35,4,110,30),.95):return False
    return _fixed(frame,'unavailable',(9,81+round(46.14*'123'.index(tier[0])),35,13))

def _parse(rows):
    found=set()
    for row in rows:
        if row.get('score',0)<.99:continue
        match=re.fullmatch(r'\s*(\d{1,6})\s*/\s*(\d{1,6})\s*',str(row.get('text','')))
        if match:
            a,b=map(int,match.groups())
            if 0<a==b<=100000:found.add(a)
    return next(iter(found)) if len(found)==1 else None

def observed_full(ui,tier):
    """Fresh paired UI frames + exact equal counter; no success inference."""
    from owner_skill_goal import Pending
    try:
        first=ui.frame()
        if not _screen(first,tier):return None
        ui.context.wait(.12);second=ui.frame()
        if not _screen(second,tier):return None
        rows=ui.rows((70,89,50,17),language='number',pair_minimum=.99)
        pair=getattr(ui,'_owner_last_rows_pair',None)
        now=time.monotonic()
        if not pair or len(pair[0])!=2 or len(pair[1])!=2 or len(pair[2])!=2:return None
        frames,ticks,answers=pair
        if any(not 0<=now-t<=3 for t in ticks) or not all(_screen(frame,tier) for frame in frames):return None
        values=[_parse(answer) for answer in answers]
        if values[0] is None or values[0]!=values[1] or _parse(rows)!=values[0]:return None
        return values[0]
    except (Pending,OSError,ValueError,TypeError,KeyError):return None

def _identity(adapter,tier):
    from owner_progression import state
    from owner_hunt_rules_candidate import configured_identity
    try:
        root=Path(adapter.project.root).resolve();progress=state(adapter);age=time.monotonic()-progress.observed
        if not progress.character or not 0<=age<=30:return None
        return (str(root),configured_identity(root),progress.character,tier)
    except (OSError,ValueError,TypeError,AttributeError):return None

def cached_full(adapter,tier):
    key=_identity(adapter,tier)
    if key is None:return False
    now=time.monotonic()
    with _LOCK:
        item=_CACHE.get(key)
        if item is None:return False
        age=now-item
        if not 0<=age<TTL:_CACHE.pop(key,None);return False
        _CACHE.move_to_end(key);return True

def remember_full(adapter,tier):
    key=_identity(adapter,tier)
    if key is None:return False
    with _LOCK:
        _CACHE[key]=time.monotonic();_CACHE.move_to_end(key)
        while len(_CACHE)>128:_CACHE.popitem(last=False)
    return True
