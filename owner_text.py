"""Read words off the real 1366x768 frame and say where they are. The shared way to find things by their text.

Words survive small patches where pictures and fixed places do not. Rows carry real pixels (rx, ry, bounds) and the
same place in the 897x479 terms the rest of the program clicks in (x, y); a click there lands on the word.
"""
import re
import numpy as np

SPACE=re.compile(r'[\s·.,:;\'"`\-_~]+')
BORDER=16
TITLE=(20,0,330,50)   # real pixels: the title of a full panel, the place name on the field, the level and name in the bag
_ROOT=[None];_titles={};_areas={}


def set_root(root):
    _ROOT[0]=root


def clean(text):
    return SPACE.sub('',str(text))


def same_words(a,b):
    return clean(a)==clean(b)


def _engine(root,language):
    from tools.ocr_support import get_paddle_engine
    return get_paddle_engine(root or _ROOT[0],language=language)


def _real(frame):
    return getattr(frame,'hi',None)


def brighten(area,floor=18,ceiling=150):
    """Lift dim text: settings show the options not chosen in very low contrast."""
    scaled=(area.astype(np.float32)-floor)*255/(ceiling-floor)
    return np.clip(scaled,0,255).astype(np.uint8)


def read_area(root,area,*,left=0,top=0,language='korean',scale=2,bright=False,minimum=.5):
    """Words in this array of real pixels. Places are real, counting from (left, top)."""
    import cv2
    area=np.asarray(area)
    key=(hash(area.tobytes()),area.shape,left,top,language,scale,bright,minimum)
    if key in _areas:return [dict(row) for row in _areas[key]]
    source=brighten(area) if bright else area
    if scale!=1:source=cv2.resize(source,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    source=cv2.copyMakeBorder(source,BORDER,BORDER,BORDER,BORDER,cv2.BORDER_CONSTANT,value=(40,40,40))
    rows=[]
    for page in _engine(root,language).predict(source):
        polys=page.get('rec_polys',())
        for index,(text,score) in enumerate(zip(page.get('rec_texts',()),page.get('rec_scores',()))):
            if float(score)<minimum or index>=len(polys):continue
            poly=(np.asarray(polys[index],dtype=np.float32)-BORDER)/scale
            low=poly.min(axis=0);high=poly.max(axis=0)
            rows.append(dict(text=str(text),score=float(score),rx=round(float((low[0]+high[0])/2)+left),ry=round(float((low[1]+high[1])/2)+top),
                             bounds=(round(float(low[0]))+left,round(float(low[1]))+top,round(float(high[0]))+left,round(float(high[1]))+top)))
    rows.sort(key=lambda r:(r['ry'],r['rx']))
    if len(_areas)>32:_areas.clear()
    _areas[key]=rows
    return [dict(row) for row in rows]


def read(root,frame,real_box=None,**options):
    """Words on a frame. real_box is (x, y, w, h) in real pixels; without it the whole screen. Rows also get x, y."""
    import owner_hd
    real=_real(frame)
    if real is None:raise ValueError('글자 읽기는 실제 화면이 필요합니다')
    real=np.asarray(real)
    x,y,w,h=real_box or (0,0,real.shape[1],real.shape[0])
    rows=read_area(root,real[y:y+h,x:x+w],left=x,top=y,**options)
    layout=getattr(frame,'layout',None)
    for row in rows:row['x'],row['y']=owner_hd.logical_of(row['rx'],row['ry'],layout)
    return rows


def title(frame,root=None):
    """The words in the top left of the screen, on a frame from the real screen. About .15 seconds, and the same
    picture is not read twice. None on a frame with no real pixels."""
    real=_real(frame)
    if real is None:return None
    x,y,w,h=TITLE
    crop=np.asarray(real)[y:y+h,x:x+w]
    key=hash(crop.tobytes())
    if key not in _titles:
        if len(_titles)>64:_titles.clear()
        _titles[key]=[row['text'] for row in read_area(root,crop,left=x,top=y) if len(clean(row['text']))>=2]
    return _titles[key]


def shows_title(frame,words,root=None,minimum=.7):
    """Is this the screen with this title? None when the frame has no real pixels, so old checks can answer."""
    seen=title(frame,root)
    if seen is None:return None
    from difflib import SequenceMatcher
    wanted=clean(words)
    return any(wanted in clean(t) or SequenceMatcher(None,clean(t),wanted).ratio()>=minimum for t in seen)


def level_and_name(frame,root=None):
    """(level, name) from the bag or info panel's 레벨 50 홍짱군, or (None, None)."""
    for line in title(frame,root) or ():
        found=re.search(r'레벨\s*(\d{1,3})\s*(\S+)',str(line))
        if found:return int(found[1]),found[2]
    return None,None


def shows_field_words(frame,root=None):
    """The bare field: the key labels under its icons (Home, Tab, H, T) are all showing, in the bottom right corner."""
    real=_real(frame)
    if real is None:return False
    words={clean(row['text']).lower() for row in read_area(root,np.asarray(real)[712:768,985:1366],left=985,top=712,scale=3)}
    return 'home' in words and len(words&{'h','t','tab','tob','toab'})>=2


def word_box(box):
    """Real pixels covering a logical (x, y, w, h) under any of the three anchors."""
    import owner_hd
    x,y,w,h=box;F=owner_hd.F
    left=max(0,round(x*F+owner_hd.SHIFT_RIGHT)-12);right=min(owner_hd.REAL[0],round((x+w)*F)+12)
    top=max(0,round(y*F)-8);bottom=min(owner_hd.REAL[1],round((y+h)*F)+8)
    return left,top,right-left,bottom-top


def logical_bounds(row,frame):
    """A word's box in 897x479 terms, around where a click on it goes."""
    x0,y0,x1,y1=row['bounds'];half=max(2,round((x1-x0)/3.2));high=max(2,round((y1-y0)/3.2))
    x,y=row['x'],row['y']
    return max(0,x-half),max(0,y-high),min(897,x+half+1),min(479,y+high+1)


def find(rows,words):
    """The rows holding these words. Exact words first, so 사용 does not answer for 사용 안 함."""
    wanted=clean(words)
    exact=[r for r in rows if clean(r['text'])==wanted]
    return exact or [r for r in rows if wanted in clean(r['text'])]
