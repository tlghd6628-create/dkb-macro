"""Run the macro at the game's own 1366x768 setting, while the code keeps speaking 897x479.

The UI scale is 1.6 at this size and the screen is narrower in those units (853.75 against 897), so each thing
moves by one of three amounts: 0 when anchored left, -34.6 in the middle, -69.2 when anchored right. Measured on
21 screens: nothing stretches, but where one anchor ends and the next begins differs by screen. So a layout map is
measured for each screen, and the current one is recognised from a tiny picture of the frame.

- A capture is the real frame plus an 897x479 frame composed by that map, so fixed places still look at the thing.
- A template match answers from the picture re-cut at the real size, on the real pixels.
- A crop given to the reader comes from the real pixels.
- A click goes through the same map at the one point where client coordinates become screen coordinates.

Pictures and maps are made by image_scope_20261104/hd_pair.py from the same screen at both sizes. Nothing is cut
from a guess at runtime: a picture with no new cut falls back to the composed frame and is listed as missing.
"""
import base64,collections,hashlib,json,logging,threading,time
from pathlib import Path
import numpy as np

LOG=logging.getLogger('project_gui.DKB')
REAL=(1366,768);LOGICAL=(897,479);F=1.6
SHIFT_RIGHT=REAL[0]-LOGICAL[0]*F  # -69.2
SHIFTS={'left':0.0,'center':SHIFT_RIGHT/2,'right':SHIFT_RIGHT}
RULES=tuple(SHIFTS)
CELL=16
GRID=(LOGICAL[1]//CELL+1,LOGICAL[0]//CELL+1)
SIGNATURE=(48,27)
SAME_SCREEN=.72
SAME_SIDES=.85;BAG_SCREENS=('inventory','inv_','pc2_bag','pc2_box_detail');SIDE_COLUMNS=(11,37)  # of 48: x<316, x>=1062
DEFAULT_SCREEN='field'
# A window whose inside changes with its tabs looks like no measured screen, and the field map then tears it: its X
# and its last prize moved, and a torn gold prize passed for a claimable one (11-05 17:32). Its own title or X names
# it (1.00 on the event screen, under .5 on the other saved real screens), and all of its inside holds one anchor.
WINDOW_MARKS={'event':('native:체크_이벤트','native:버튼_X_이벤트창')}
WINDOW_INSIDE={'event':(157,85,740,398)}  # logical x0,y0,x1,y1
MARK_SCORE=.9
STORE=Path(__file__).parent/'assets/hd'
HIT_LIFE=5.0
_index=None;_images={};_missing=set();_layouts=None;_marks=None
_current=None;_last_capture=None;_hits=collections.deque(maxlen=64);_lock=threading.Lock()


def rule_of(x):
    """Where nothing is measured."""
    return 'left' if x<100 else 'right' if x>=700 else 'center'


def to_real_x(x,rule=None):
    return x*F+SHIFTS[rule or rule_of(x)]


def to_real_y(y):
    return y*F


# ---- layouts

class Layout:
    """Which of the three anchors holds at each part of one screen."""
    def __init__(self,name,grid,signature=None):
        self.name=name;self.grid=np.asarray(grid,np.uint8);self.signature=signature
        self._xs=None
    def rule(self,x,y):
        row=min(GRID[0]-1,max(0,int(y)//CELL));col=min(GRID[1]-1,max(0,int(x)//CELL))
        return RULES[int(self.grid[row,col])]
    def shift(self,x,y):
        return SHIFTS[self.rule(x,y)]
    def picks(self):
        """For each 897x479 pixel, the column to take from the real frame scaled to 1/1.6."""
        if self._xs is None:
            cells=np.repeat(np.repeat(self.grid,CELL,axis=0),CELL,axis=1)[:LOGICAL[1],:LOGICAL[0]]
            steps=np.array([SHIFTS[r]/F for r in RULES])[cells]
            columns=np.arange(LOGICAL[0])[None,:]+steps
            self._xs=np.clip(np.round(columns).astype(np.int32),0,round(REAL[0]/F)-1)
        return self._xs


def _plain_layout():
    grid=np.zeros(GRID,np.uint8)
    for col in range(GRID[1]):grid[:,col]=RULES.index(rule_of(col*CELL))
    return Layout('plain',grid)


def signature_of(real):
    import cv2
    gray=cv2.cvtColor(np.asarray(real),cv2.COLOR_RGB2GRAY)
    tiny=cv2.resize(gray,SIGNATURE,interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    tiny-=tiny.mean();size=float(np.linalg.norm(tiny))
    return tiny/size if size>1e-3 else tiny


def build_layout(small,real,name='screen'):
    """Compare each part of the same screen at both sizes. Parts with nothing on them take their neighbour's anchor."""
    import cv2
    small=np.asarray(small);real=np.asarray(real)
    grid=np.full(GRID,255,np.uint8)
    for row in range(GRID[0]):
        for col in range(GRID[1]):
            x,y=col*CELL,row*CELL
            x0,y0,x1,y1=max(0,x-10),max(0,y-3),min(LOGICAL[0],x+CELL+10),min(LOGICAL[1],y+CELL+3)
            patch=small[y0:y1,x0:x1]
            if patch.shape[0]<8 or patch.shape[1]<12 or float(patch.std())<9:continue
            big=cv2.resize(patch,None,fx=F,fy=F,interpolation=cv2.INTER_CUBIC)
            scores=[]
            for rule in RULES:
                rx,ry=round(x0*F+SHIFTS[rule]),round(y0*F)
                l,t=max(0,rx-3),max(0,ry-3)
                hay=real[t:ry+big.shape[0]+3,l:rx+big.shape[1]+3]
                if hay.shape[0]<big.shape[0] or hay.shape[1]<big.shape[1]:scores.append(-1.);continue
                scores.append(float(np.nan_to_num(cv2.matchTemplate(hay,big,cv2.TM_CCOEFF_NORMED),nan=-1).max()))
            order=np.argsort(scores)[::-1]
            if scores[order[0]]>=.8 and scores[order[0]]-scores[order[1]]>=.02:grid[row,col]=order[0]
    grid=_tidy(grid)
    return Layout(name,grid,signature_of(real))


def _tidy(grid):
    """A lone cell against all its neighbours is noise; empty cells take the nearest measured cell along the row."""
    out=grid.copy()
    for row in range(grid.shape[0]):
        for col in range(grid.shape[1]):
            if grid[row,col]==255:continue
            around=grid[max(0,row-1):row+2,max(0,col-1):col+2].ravel()
            around=around[around!=255]
            if len(around)>=4:
                counts=np.bincount(around,minlength=3)
                if counts[grid[row,col]]<=1:out[row,col]=int(counts.argmax())
    for axis in (1,0):
        moved=out if axis==1 else out.T
        for line in moved:
            known=np.flatnonzero(line!=255)
            if len(known):
                empty=np.flatnonzero(line==255)
                line[empty]=line[known[np.abs(empty[:,None]-known[None,:]).argmin(axis=1)]]
    out[out==255]=1
    return out


def dump_layout(layout):
    return dict(screen=layout.name,grid=[''.join(map(str,row)) for row in layout.grid.tolist()],
                signature=base64.b64encode(np.round(layout.signature*1000).astype(np.int16).tobytes()).decode())


def load_layout(row):
    tiny=np.frombuffer(base64.b64decode(row['signature']),np.int16).astype(np.float32)/1000
    return Layout(row['screen'],[[int(c) for c in line] for line in row['grid']],tiny/max(1e-6,float(np.linalg.norm(tiny))))


def layouts():
    global _layouts
    if _layouts is None:
        rows={}
        try:
            for line in (STORE/'layouts.jsonl').read_text(encoding='utf-8').splitlines():
                if line.strip():
                    row=json.loads(line);rows[row['screen']]=row  # the same screen twice: the later line wins
        except (OSError,ValueError):pass
        _layouts=[load_layout(row) for row in rows.values()]
        for layout in _layouts:
            if layout.name in WINDOW_INSIDE:
                x0,y0,x1,y1=WINDOW_INSIDE[layout.name]
                layout.grid[y0//CELL:(y1+CELL-1)//CELL,x0//CELL:(x1+CELL-1)//CELL]=RULES.index('center')
    return _layouts


def default_layout():
    for layout in layouts():
        if layout.name==DEFAULT_SCREEN:return layout
    return _PLAIN


def classify(real):
    """The measured screen this frame looks like, or the field map when it looks like none of them."""
    known=[l for l in layouts() if l.signature is not None and l.name!=DEFAULT_SCREEN]
    if not known:return default_layout()
    marked=marked_window(real)
    if marked:
        for layout in known:
            if layout.name==marked:return layout
    tiny=signature_of(real)
    scores=[float(np.dot(l.signature,tiny)) for l in known]
    best=int(np.argmax(scores))
    if scores[best]>=SAME_SCREEN:return known[best]
    # The bag opens over whatever scenery is there, which pulls the whole picture away from the measured one, and the
    # field map then tears its panels apart. Its two opaque side panels stay the same.
    sides=_side_panels(tiny)
    close=[(scores[i],l) for i,l in enumerate(known) if l.name.startswith(BAG_SCREENS) and float(np.dot(_side_panels(l.signature),sides))>=SAME_SIDES]
    return max(close,key=lambda pair:pair[0])[1] if close else default_layout()


def _window_marks():
    """(screen, picture, row) for each mark that has its new cut."""
    global _marks
    if _marks is None:
        wanted={label:screen for screen,labels in WINDOW_MARKS.items() for label in labels}
        _marks=[]
        for key,row in index().items():
            if row.get('label') in wanted:
                try:_marks.append((wanted[row['label']],_load(key,row,False),row))
                except OSError:pass
    return _marks


def marked_window(real):
    """The screen named by a window's own mark at its own place on this real frame, or None."""
    import cv2
    real=np.asarray(real)
    for screen,cut,row in _window_marks():
        x,y=row['x'],row['y'];h,w=cut.shape[:2]
        area=real[max(0,y-6):y+h+6,max(0,x-6):x+w+6]
        if area.shape[0]<h or area.shape[1]<w:continue
        if float(np.nan_to_num(cv2.matchTemplate(area,cut,cv2.TM_CCOEFF_NORMED),nan=-1).max())>=MARK_SCORE:return screen
    return None


def _side_panels(tiny):
    """A signature with only the bag's side panels left, normalized again."""
    grid=np.asarray(tiny,np.float32).reshape(SIGNATURE[1],SIGNATURE[0])
    part=np.concatenate((grid[:,:SIDE_COLUMNS[0]],grid[:,SIDE_COLUMNS[1]:]),axis=1).ravel()
    part=part-part.mean();size=float(np.linalg.norm(part))
    return part/size if size>1e-3 else part


# ---- places

def to_real_point(x,y,layout=None):
    """A real place for this logical one. Something a picture just found keeps the anchor it was found under."""
    now=time.monotonic()
    with _lock:
        for seen,x0,y0,x1,y1,shift in reversed(_hits):
            if now-seen<=HIT_LIFE and x0<=x<=x1 and y0<=y<=y1:
                return min(REAL[0]-1,max(0,round(x*F+shift))),min(REAL[1]-1,max(0,round(y*F)))
    shift=(layout or _current or default_layout()).shift(x,y)
    return min(REAL[0]-1,max(0,round(x*F+shift))),min(REAL[1]-1,max(0,round(y*F)))


def logical_of(rx,ry,layout=None):
    """The place in 897x479 terms for a real place something was read at. A click there lands back on it."""
    layout=layout or _current or default_layout();y=ry/F
    picked=None
    for rule in RULES:
        x=(rx-SHIFTS[rule])/F
        if 0<=x<LOGICAL[0] and layout.rule(x,y)==rule:picked=(x,SHIFTS[rule]);break
    if picked is None:picked=((rx-SHIFTS['center'])/F,SHIFTS['center'])
    x,shift=picked
    with _lock:_hits.append((time.monotonic(),x-8,y-8,x+8,y+8,shift))
    return round(x),round(y)


def real_box(box,layout=None,rule=None):
    """A logical (x,y,w,h) in real pixels, by the anchor at its middle."""
    x,y,w,h=box
    shift=SHIFTS[rule] if rule else (layout or _current or default_layout()).shift(x+w/2,y+h/2)
    return max(0,round(x*F+shift)),max(0,round(y*F)),round(w*F),round(h*F)


# ---- pictures

def key_of(needle):
    array=np.asarray(needle)
    return hashlib.sha1(array.tobytes()+repr(array.shape).encode()).hexdigest()[:20]


def index():
    global _index
    if _index is None:
        _index={}
        try:
            for line in (STORE/'index.jsonl').read_text(encoding='utf-8').splitlines():
                if line.strip():
                    row=json.loads(line);_index[row['key']]=row
        except (OSError,ValueError):pass
    return _index


def reload_index():
    global _index,_layouts,_marks
    _index=None;_layouts=None;_marks=None;_images.clear()
    return index()


def _load(key,row,flip):
    tag=(key,flip)
    if tag not in _images:
        from PIL import Image
        image=np.asarray(Image.open(STORE/row['file']).convert('RGB'))
        # Stored as seen on screen; a picture read the other way round is compared the same way round.
        _images[tag]=image[:,:,::-1].copy() if flip else image
    return _images[tag]


def cut_for(needle):
    """The new cut of this old picture and its row, or None."""
    key=key_of(needle);row=index().get(key)
    if row:return _load(key,row,bool(row.get('bgr'))),row
    array=np.asarray(needle)
    if array.ndim==3 and array.shape[2]==3:
        key=key_of(array[:,:,::-1]);row=index().get(key)
        if row:return _load(key,row,not row.get('bgr')),row
    return None


def missing():
    return sorted(_missing)


def _note_missing(needle):
    key=key_of(needle)
    if key in _missing:return
    _missing.add(key)
    try:
        with (STORE.parent/'hd-missing.txt').open('a',encoding='utf-8') as out:
            out.write('%s %s\n'%(key,np.asarray(needle).shape))
    except OSError:pass


# ---- frames

class HdFrame(np.ndarray):
    """The 897x479 frame the code expects, carrying the real one. A slice remembers where it came from.
    Arithmetic gives a plain array: what came out of it is no longer that part of the screen."""
    hi=None;source=None;flip=False;layout=None
    def __array_finalize__(self,obj):
        self.hi=getattr(obj,'hi',None);self.source=getattr(obj,'source',None)
        self.flip=getattr(obj,'flip',False);self.layout=getattr(obj,'layout',None)
    def __array_ufunc__(self,ufunc,method,*inputs,**kwargs):
        inputs=tuple(np.asarray(v) if isinstance(v,HdFrame) else v for v in inputs)
        if 'out' in kwargs:kwargs['out']=tuple(np.asarray(v) if isinstance(v,HdFrame) else v for v in kwargs['out'])
        return getattr(ufunc,method)(*inputs,**kwargs)
    def __getitem__(self,item):
        part=super().__getitem__(item)
        if isinstance(part,HdFrame) and self.hi is not None:
            box=_slice_box(self,item)
            if box is None:part.hi=None;part.source=None
            else:part.source=box;part.flip=self.flip!=_flips(item)
        return part


def _flips(item):
    return isinstance(item,tuple) and len(item)==3 and isinstance(item[2],slice) and item[2].step==-1


def _slice_box(frame,item):
    """Where in the logical frame this slice is, or None if it is not a plain box."""
    if frame.ndim!=3:return None
    if not isinstance(item,tuple):item=(item,)
    if len(item)==2:item=item+(slice(None),)
    if len(item)!=3 or not all(isinstance(v,slice) for v in item):return None
    ys,xs,channels=item
    if ys.step not in (None,1) or xs.step not in (None,1) or channels.indices(3) not in ((0,3,1),(2,-1,-1)):return None
    y0,y1,_=ys.indices(frame.shape[0]);x0,x1,_=xs.indices(frame.shape[1])
    base=frame.source or (0,0,LOGICAL[0],LOGICAL[1])
    return base[0]+x0,base[1]+y0,max(0,x1-x0),max(0,y1-y0)


def make_frame(real,layout=None):
    """Compose the 897x479 frame by this screen's map, so old code that reads a fixed place finds the thing."""
    import cv2
    global _current
    layout=layout or classify(real)
    small=cv2.resize(real,(round(REAL[0]/F),480),interpolation=cv2.INTER_AREA)[:LOGICAL[1]]
    rows=np.arange(LOGICAL[1])[:,None]
    frame=small[rows,layout.picks()]
    made=frame.view(HdFrame);made.hi=real;made.layout=layout
    _current=layout
    return made


def real_of(frame):
    return getattr(frame,'hi',None)


def real_crop(frame,box,scale=4):
    """The box from the real frame, at `scale` times the logical size, as the reader is given it."""
    real=real_of(frame)
    if real is None or frame.shape[:2]!=(LOGICAL[1],LOGICAL[0]):return None
    import cv2
    x,y,w,h=real_box(box,getattr(frame,'layout',None))
    crop=np.asarray(real)[y:y+h,x:x+w]
    if crop.size==0:return None
    return cv2.resize(crop,(box[2]*scale,box[3]*scale),interpolation=cv2.INTER_CUBIC)


def _real_part(image):
    """The real pixels of a slice still holding exactly that box, colour order included, or None."""
    box=getattr(image,'source',None);real=getattr(image,'hi',None)
    if box is None or real is None or image.ndim!=3 or image.dtype!=np.uint8 or image.shape[:2]!=(box[3],box[2]) or not box[2] or not box[3]:return None
    x,y,w,h=real_box(box,image.layout)
    part=np.asarray(real)[y:y+h,x:x+w]
    if part.shape[0]<h or part.shape[1]<w:return None
    return part[:,:,::-1] if image.flip else part


def match_real(image,needle,method,ordinary,scorer=None):
    """Answer a template match from the real frame when this picture has a new cut. Same shape of answer."""
    source=getattr(image,'source',None);real=getattr(image,'hi',None)
    if real is None or method!=5:return None  # 5 is TM_CCOEFF_NORMED
    if source is None and image.shape[:2]!=(LOGICAL[1],LOGICAL[0]):return None
    found=cut_for(needle)
    if found is None:
        _note_missing(needle);return None
    cut,row=found
    h,w=cut.shape[:2]
    box=source or (0,0,LOGICAL[0],LOGICAL[1])
    shift=SHIFTS[row['rule']]
    # Only the region asked for, under this picture's own anchor: it must not answer for another part of the screen.
    margin=4
    left=max(0,round(box[0]*F+shift)-margin);top=max(0,round(box[1]*F)-margin)
    right=min(REAL[0],round((box[0]+box[2])*F+shift)+margin);bottom=min(REAL[1],round((box[1]+box[3])*F)+margin)
    right=max(right,min(REAL[0],left+w));bottom=max(bottom,min(REAL[1],top+h))
    area=np.asarray(real)[top:bottom,left:right]
    if getattr(image,'flip',False):area=area[:,:,::-1]
    if area.shape[0]<h or area.shape[1]<w:return None
    scores=np.nan_to_num(scorer(area,cut) if scorer else ordinary(area.copy(),cut,method),nan=-1)
    rows=max(1,image.shape[0]-np.asarray(needle).shape[0]+1);cols=max(1,image.shape[1]-np.asarray(needle).shape[1]+1)
    answer=np.full((rows,cols),-1.,np.float32)
    ys,xs=np.where(scores>=.3)
    if not len(xs):return answer
    logical_y=np.clip(np.round((top+ys)/F-box[1]).astype(int),0,rows-1)
    logical_x=np.clip(np.round((left+xs-shift)/F-box[0]).astype(int),0,cols-1)
    np.maximum.at(answer,(logical_y,logical_x),scores[ys,xs].astype(np.float32))
    _remember_hits(answer,box,np.asarray(needle).shape,shift)
    return answer


def real_reference(frame,reference,box):
    """For a check that compares pixels itself: the real pixels at this place and the picture's new cut, aligned.
    None when this is not a real frame or the picture has no cut, so the check runs as it always did."""
    real=getattr(frame,'hi',None)
    if real is None:return None
    found=cut_for(reference)
    if found is None:
        _note_missing(reference);return None
    import cv2
    cut,row=found;h,w=cut.shape[:2];shift=SHIFTS[row['rule']]
    left=max(0,round(box[0]*F+shift)-4);top=max(0,round(box[1]*F)-4)
    area=np.asarray(real)[top:top+h+8,left:left+w+8]
    if getattr(frame,'flip',False):area=area[:,:,::-1]
    if area.shape[0]<h or area.shape[1]<w:return None
    _,_,_,at=cv2.minMaxLoc(np.nan_to_num(_PLAIN_MATCH[0](area.copy(),cut,cv2.TM_CCOEFF_NORMED),nan=-1))
    return area[at[1]:at[1]+h,at[0]:at[0]+w],cut


def _remember_hits(answer,box,size,shift):
    best=float(answer.max())
    if best<.85:return
    ys,xs=np.where(answer>=max(.85,best-.05))
    now=time.monotonic()
    with _lock:
        for y,x in list(zip(ys.tolist(),xs.tolist()))[:12]:
            _hits.append((now,box[0]+x-1,box[1]+y-1,box[0]+x+size[1]+1,box[1]+y+size[0]+1,shift))


# ---- installing

def install_reading():
    """Route template matching and enlarging through the real frame. Safe to call again."""
    import cv2
    if getattr(cv2,'_owner_hd',False):return
    cv2._owner_hd=True
    plain_match=cv2.matchTemplate;plain_resize=cv2.resize;plain_convert=cv2.cvtColor
    _PLAIN_MATCH[0]=plain_match
    def matchTemplate(image,templ,method,*args,**kwargs):
        if isinstance(image,HdFrame) and not args and not kwargs:
            answer=match_real(image,templ,method,plain_match)
            if answer is not None:return answer
        return plain_match(np.asarray(image),templ,method,*args,**kwargs)
    def resize(src,dsize,*args,**kwargs):
        if isinstance(src,HdFrame):
            part=_real_part(src)
            fx=kwargs.get('fx',args[1] if len(args)>1 else 0) or 0
            fy=kwargs.get('fy',args[2] if len(args)>2 else 0) or 0
            size=dsize if dsize else (round(src.shape[1]*fx),round(src.shape[0]*fy))
            if part is not None and size[0]>=src.shape[1]*1.2 and size[1]>=src.shape[0]*1.2:
                return plain_resize(part,tuple(size),interpolation=kwargs.get('interpolation',args[3] if len(args)>3 else cv2.INTER_CUBIC))
            src=np.asarray(src)
        return plain_resize(src,dsize,*args,**kwargs)
    def cvtColor(src,code,*args,**kwargs):
        if isinstance(src,HdFrame):
            if code in (cv2.COLOR_RGB2BGR,cv2.COLOR_BGR2RGB) and not args and not kwargs and src.source is not None:
                made=src[:,:,::-1].copy()
                return made
            src=np.asarray(src)
        return plain_convert(src,code,*args,**kwargs)
    cv2.matchTemplate=matchTemplate;cv2.resize=resize;cv2.cvtColor=cvtColor
    import roi_runtime
    plain_masked=roi_runtime._match_ccoeff_normed_masked
    def masked(hay,needle,mask):
        if isinstance(hay,HdFrame):
            def scorer(area,cut):
                return plain_masked(area.copy(),cut,plain_resize(mask,(cut.shape[1],cut.shape[0]),interpolation=cv2.INTER_NEAREST))
            answer=match_real(hay,needle,5,plain_match,scorer=scorer)
            if answer is not None:return answer
            hay=np.asarray(hay)
        return plain_masked(hay,needle,mask)
    roi_runtime._match_ccoeff_normed_masked=masked


_game={};_state={};_PLAIN_MATCH=[None]


def _is_game(hwnd):
    import win32gui
    if hwnd not in _game:
        try:_game[hwnd]=win32gui.GetClassName(hwnd)=='UnityWndClass'
        except Exception:return False
    return _game[hwnd]


def _physical(hwnd):
    import win32gui
    return tuple(win32gui.GetClientRect(hwnd)[2:])


def _click_layout():
    """The map for the screen as it is now: a click can come well after the last capture."""
    last=_last_capture
    if last is None or time.monotonic()-last[3]<=.3:return _current
    hwnd,target,printwindow,_=last
    try:_capture(hwnd,target,printwindow)
    except Exception as exc:LOG.debug('클릭 전 화면 확인 생략 · %s',exc)
    return _current


def _capture(hwnd,target,printwindow):
    global _last_capture
    frame=make_frame(_state['capture'](hwnd,dict(target,client_size=list(REAL)),printwindow=printwindow))
    _last_capture=(hwnd,target,printwindow,time.monotonic())
    return frame


def ensure_size(hwnd,context=None):
    """The game at 1366x768, with no z-order change or activation, kept on the screen."""
    import ctypes,win32gui
    for attempt in range(3):
        if context:context.checkpoint()
        L,T,R,B=win32gui.GetWindowRect(hwnd);size=_physical(hwnd)
        if size==REAL:return
        w,h=REAL[0]+(R-L-size[0]),REAL[1]+(B-T-size[1])
        user=ctypes.windll.user32;screen=(user.GetSystemMetrics(0),user.GetSystemMetrics(1))
        x,y=max(0,min(L,screen[0]-w)),max(0,min(T,screen[1]-h))
        win32gui.SetWindowPos(hwnd,0,x,y,w,h,0x14)
        for _ in range(8):
            if context:context.wait(.04)
            else:time.sleep(.04)
            if _physical(hwnd)==REAL:
                LOG.info('게임 창 크기 %dx%d',*REAL);return
    raise RuntimeError('창 크기 조절 실패: %s (기준 %s)'%(_physical(hwnd),REAL))


def install_window():
    """Safe to call again. The rest of the program keeps seeing 897x479."""
    import win32gui,window_resolution,mdt_owned_capture
    if getattr(window_resolution,'_owner_hd',False):return
    window_resolution._owner_hd=True
    plain_ensure=window_resolution.ensure_client_size;plain_size=window_resolution.client_size
    def client_size(hwnd):
        size=plain_size(hwnd)
        return LOGICAL if tuple(size)==REAL and _is_game(hwnd) else size
    def ensure_client_size(hwnd,expected,context=None):
        if _is_game(hwnd) and tuple(expected)==LOGICAL:return ensure_size(hwnd,context) or LOGICAL
        return plain_ensure(hwnd,expected,context)
    window_resolution.client_size=client_size
    window_resolution.ensure_client_size=ensure_client_size
    _state['capture']=mdt_owned_capture.capture_client
    def capture_client(hwnd,target,printwindow=None):
        if _physical(hwnd)==REAL and _is_game(hwnd):return _capture(hwnd,target,printwindow)
        return _state['capture'](hwnd,target,printwindow=printwindow)
    mdt_owned_capture.capture_client=capture_client
    plain_point=win32gui.ClientToScreen
    def client_to_screen(hwnd,point):
        point=tuple(point)
        if point!=(0,0) and _is_game(hwnd) and _physical(hwnd)==REAL:
            point=to_real_point(point[0],point[1],_click_layout())
        return plain_point(hwnd,point)
    win32gui.ClientToScreen=client_to_screen


def install():
    install_reading();install_window()


def keep_size(gui):
    """While nothing is running: the game at this size and the program beside it. A running job is never disturbed."""
    try:
        state=gui.session.snapshot()
        if state.get('status') not in ('running','paused') and not state.get('worker_alive'):
            hwnd=getattr(getattr(gui,'game_window',None),'hwnd',0)
            if hwnd and _is_game(hwnd):
                ensure_size(hwnd);place_program(gui)
    except Exception as exc:
        LOG.debug('게임 창 크기 확인 생략 · %s',exc)
    if hasattr(gui,'root'):gui.root.after(15000,lambda:keep_size(gui))


def place_program(gui):
    """Keep the program window beside the game instead of under it: a covered game takes no clicks."""
    import win32gui
    try:
        hwnd=getattr(getattr(gui,'game_window',None),'hwnd',0)
        if not hwnd or not win32gui.IsWindow(hwnd):return False
        right=win32gui.GetWindowRect(hwnd)[2]
        root=gui.root
        if root.winfo_rootx()<right:
            root.geometry('+%d+%d'%(right+2,max(0,root.winfo_rooty()-31)))
            return True
    except Exception as exc:
        LOG.debug('프로그램 창 위치 조정 생략 · %s',exc)
    return False


_PLAIN=_plain_layout()
