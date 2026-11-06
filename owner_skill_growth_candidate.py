"""Candidate style-enhancement worker for an already-open skill growth tab.

Uses existing SkillUI capture/OCR/input worker. Caller must own that worker,
provide its verified current-character ledger/settings, open/close the growth
tab with the existing menu navigation and respect cancellation. No entry into
this module runs a game action. Real execution/receipt E2E remains untested.
"""
import hashlib,logging,re,time
from decimal import Decimal,InvalidOperation
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from owner_skill_goal import Pending
from owner_growth_policy_candidate import SKILL_REINFORCEMENT_TARGETS

TAB=Path(__file__).parent/'skill_assets_candidate/growth_header.png'
TAB_HASH='c27c372522b872f0309200d76f9794130d733aebd0639eae393b5978d25cbdae'
STYLE_READ_TRIES=3;STYLE_READ_MISSES=('두 화면 판독 불일치','원본 글자·대상 변경','새 화면 글자','판독 지연','화면 변경','선택 확인 필요');SELECT_WAIT=1.5
RATIO_TEXT=(372,396,46,16);OBSERVE_TRIES=6
LIST_READ_TRIES=3;LIST_SETTLE_SECONDS=2;LIST_STILL=.6
LIST=(704,65,170,370);TRANSITION=(350,123,85,25);OPEN_CURRENT=(365,123,20,25);OPEN_NEXT=(397,123,23,25);RATIO=(370,380,50,45);PRICE=(372,435,145,33);BALANCE=(409,10,36,16)

class SkillGrowthNavigationError(RuntimeError):
    """The caller must not continue gameplay on an unverified menu."""

def skill_section(frame):
    if getattr(frame,'shape',None)!=(479,897,3):return False
    data=TAB.read_bytes()
    if hashlib.sha256(data).hexdigest()!=TAB_HASH:return False
    with Image.open(TAB) as im:needle=np.asarray(im.convert('RGB'))
    roi=frame[3:36,30:120]
    result=cv2.matchTemplate(roi,needle,cv2.TM_CCOEFF_NORMED)
    style_selected=(float((frame[41:57,163:188].min(axis=2)>80).mean())>=.90
                    and float((frame[41:57,210:232].min(axis=2)>80).mean())>=.90)
    return bool(np.isfinite(result).all() and result.max()>=.96 and style_selected)

def tab(frame):
    return skill_section(frame) and float((frame[69:91,12:77].min(axis=2)>170).mean())>=.80

def awakening_tab(frame):
    return skill_section(frame) and float((frame[102:124,12:77].min(axis=2)>170).mean())>=.80

def awaken_selected(frame,y):
    if not awakening_tab(frame) or type(y) is not int or not 20<=y<459:return False
    return int((frame[y-14:y+20,705:711].min(axis=2)>170).sum())>=8

def awaken_center_icon(frame):
    """Existing public icon matching at the actual growth detail size.

    Only the already catalogued icons are available; this never interprets a
    missing icon as an unlearned skill or authorizes an action by itself.
    """
    from owner_skill_ui import catalog,icon
    if not awakening_tab(frame):return None
    patch=frame[83:140,365:425];scores=[]
    for sid in map(int,catalog()['skills']):
        best=-1.
        for width in (34,35,36):
            needle=icon(sid,width);values=cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)
            best=max(best,float(np.where(np.isfinite(values),values,-1).max()))
        scores.append((best,sid))
    scores.sort(reverse=True)
    return scores[0][1] if scores and scores[0][0]>=.90 and len(scores)>1 and scores[0][0]-scores[1][0]>=.07 else None

def _fixed_template(frame,filename,expected,box,threshold):
    path=Path(__file__).parent/'skill_assets_candidate'/filename
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:return False
    with Image.open(path) as im:needle=np.asarray(im.convert('RGB'))
    x,y,w,h=box;region=frame[y:y+h,x:x+w]
    if region.shape!=needle.shape:return False
    score=float(cv2.matchTemplate(region,needle,cv2.TM_CCOEFF_NORMED)[0,0])
    return bool(np.isfinite(score) and score>=threshold)

def awaken_zero_stage(frame):
    """Only the observed no-star → one-blue-star stage; no action authority."""
    if not awakening_tab(frame):return False
    current_side=cv2.cvtColor(frame[127:147,355:396],cv2.COLOR_RGB2HSV)
    blue=(current_side[:,:,0]>=85)&(current_side[:,:,0]<=135)&(current_side[:,:,1]>110)&(current_side[:,:,2]>130)
    if int(blue.sum())>=3:return False
    return _fixed_template(frame,'awaken_zero_stage.png',
        'ca0893066d35099f4fe9aefd54a0762f2281e5cf0a7ebfa14728d3d045d390c0',(355,127,74,20),.96)

def awaken_red_zero100(frame):
    """Only the captured red 0/100 insufficient-fragment glyph."""
    if not awakening_tab(frame):return False
    patch=frame[396:409,380:390];hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
    red=((hsv[:,:,0]<12)|(hsv[:,:,0]>165))&(hsv[:,:,1]>90)&(hsv[:,:,2]>100)
    return int(red.sum())>=4 and _fixed_template(frame,'awaken_red_zero100.png',
        'f72bb55fdb0f199e221cf94819b9530686760e4384ca8847f36462268f89471a',(380,396,30,13),.98)

def awaken_unselected(frame):
    return tab(frame) and _fixed_template(frame,'awaken_tab_unselected.png',
        '76ab578589b8ab8af8a5ee157cb380457da87eb574138b0480349bd959862803',(12,100,66,26),.96)

def inspect_awaken_selected(frames,requested):
    """Read known selected skill and observed zero stage, never consume."""
    from owner_skill_ui import catalog,identify_icon
    if len(frames)!=2 or not all(awakening_tab(f) for f in frames):return None
    known=catalog()['all_skill_names'].get(requested)
    if not known:return None
    sid=known.get('id')
    if not isinstance(sid,int) or any(awaken_center_icon(f)!=sid for f in frames):return None
    for index in range(9):
        y=85+45*index
        if all(awaken_selected(f,y) and identify_icon(f,(704,75+45*index,41,38))==sid for f in frames):
            if not all(awaken_zero_stage(f) for f in frames):return None
            return {'name':requested,'awaken':0,'insufficient_zero100':all(awaken_red_zero100(f) for f in frames)}
    return None

def unselected_enhance(frame):
    """Actual gray 강화 tab recorded while the 도술 각성 tab was selected."""
    path=Path(__file__).parent/'skill_assets_candidate/growth_enhance_unselected.png'
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!='2b2c05cb22f7baf8502c1f0cc24297f9d83649a514374dbc679f36ae0fd05779':return False
    with Image.open(path) as im:needle=np.asarray(im.convert('RGB'))
    if getattr(frame,'shape',None)!=(479,897,3):return False
    roi=frame[64:100,7:85];result=cv2.matchTemplate(roi,needle,cv2.TM_CCOEFF_NORMED)
    return bool(np.isfinite(result).all() and result.max()>=.96)

def material_short(frame):
    x,y,w,h=RATIO_TEXT;part=frame[y:y+h,x:x+w].astype('int16')
    return int(((part[:,:,0]>170)&(part[:,:,1]<95)&(part[:,:,2]<95)).sum())>=4

def selected(frame,y):
    if not tab(frame) or type(y) is not int or not 20<=y<459:return False
    # On the captured +9 opening screen the selected white edge is dimmer;
    # neighbouring rows remain below 110 in this same stripe.
    if int((frame[y-14:y+20,705:711].min(axis=2)>150).sum())<8:return False
    if not 70<=y<=420:return False
    # A cursor/row border can make the old six-pixel stripe positive on an
    # unselected row. The actual selected tile also has a distinctly lighter
    # empty right-hand body than its neighbours (observed 86..95 vs 64..67).
    body=float(frame[y-8:y+16,813:848].mean())
    neighbours=[float(frame[yy-8:yy+16,813:848].mean()) for step in (-2,-1,1,2)
                for yy in [round(y+40.5*step)] if 70<=yy<=420]
    return bool(neighbours and body>=75 and body-float(np.median(neighbours))>=12)


STYLE_ICON=(378,94,33,22)


def _style_icon_mask(patch):
    hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
    return (hsv[:,:,1]<45)&(hsv[:,:,2]>170)


def same_style_icon(first,second):
    if first.shape!=second.shape:return False
    a,b=_style_icon_mask(first),_style_icon_mask(second)
    union=int((a|b).sum());intersection=int((a&b).sum())
    return bool(int(a.sum())>=8 and int(b.sum())>=8 and union and intersection/union>=.90)


def bind_style_identity(ui,name,frames,y):
    """Bind a dynamically selected row to its paired central emblem.

    No fixed twelve-label template bank or weak tiny-title OCR is required.
    This is scoped to this UI/context and is checked again on fresh frames.
    """
    if len(frames)!=2 or not all(selected(f,y) for f in frames):raise Pending('도술 계열 강한 선택 행 확인 필요')
    x,t,w,h=STYLE_ICON;patches=[f[t:t+h,x:x+w].copy() for f in frames]
    if not same_style_icon(*patches):raise Pending('도술 중앙 계열 아이콘 두 화면 확인 필요')
    bindings=getattr(ui,'_owner_style_bindings',None)
    if not isinstance(bindings,dict) or getattr(ui,'_owner_style_bindings_context',None) is not ui.context:
        bindings={};ui._owner_style_bindings=bindings;ui._owner_style_bindings_context=ui.context
    prior=bindings.get(name)
    if prior is not None and not same_style_icon(prior,patches[-1]):raise Pending('같은 도술 계열의 중앙 아이콘 변경')
    if any(other!=name and same_style_icon(patch,patches[-1]) for other,patch in bindings.items()):
        raise Pending('다른 도술 계열의 중앙 아이콘이 그대로 남아 있습니다')
    bindings[name]=patches[-1]
    return patches[-1]

def active(frame):
    if not tab(frame):return False
    patch=cv2.cvtColor(frame[438:462,445:505],cv2.COLOR_RGB2HSV)
    bright=lambda p:(p[:,:,0]>15)&(p[:,:,0]<45)&(p[:,:,1]>50)&(p[:,:,2]>190)
    if float(bright(patch).mean())>=.75:return True
    # The actual successful +1 frames retain a large custom cursor over the
    # left half of the still-active button. Its rightmost inner gold fill is
    # unobscured in both captures; the disabled material-shortage button has
    # no bright gold here. Keep the original full-button threshold unchanged.
    right=cv2.cvtColor(frame[440:456,489:502],cv2.COLOR_RGB2HSV)
    return float(bright(right).mean())>=.98

def open_button(frame):
    """Actual 개방 label; separate from the same-colour 강화 button."""
    if not tab(frame):return False
    path=Path(__file__).parent/'skill_assets_candidate/open_button.png'
    if hashlib.sha256(path.read_bytes()).hexdigest()!='615c591cd1135b5ef674a8d9f565555b1a28bff7af3f369e198a71c7a9f95262':return False
    with Image.open(path) as im:needle=np.asarray(im.convert('RGB'))
    region=frame[435:463,457:502]
    scores=cv2.matchTemplate(region,needle,cv2.TM_CCOEFF_NORMED)
    return bool(np.isfinite(scores).all() and scores.max()>=.96)

def named_row(rows,name):
    out=[]
    for row in rows:
        if row.get('score',0)<.80:continue
        text=re.sub(r'\s+','',str(row.get('text','')))
        m=re.fullmatch(re.escape(name)+r'(?:\+(\d{1,3}))?',text)
        if m:out.append((row,int(m.group(1) or 0)))
    if len(out)!=1:raise Pending(name+' 도술 계열·수치 판독 필요')
    return out[0]

def number(rows,kind):
    matches=[]
    for row in rows:
        if row.get('score',0)<(.90 if kind=='balance' else .98):continue
        text=re.sub(r'\s+','',str(row.get('text','')))
        if kind=='ratio':
            m=re.fullmatch(r'(\d{1,5}|\d{1,3}(?:,\d{3}){1,2})/(\d{1,5}|\d{1,3}(?:,\d{3}){1,2})',text)
            if m:matches.append((int(m.group(1).replace(',','')),int(m.group(2).replace(',',''))))
        elif kind=='price':
            if re.fullmatch(r'\d{1,3}(?:,\d{3})*',text):matches.append(int(text.replace(',','')))
        else:
            # A plain count, or K/M with its decimals. "1.14M" misread as "114M" is
            # a hundred times the real balance, and the game always prints the point.
            m=re.fullmatch(r'(\d+\.\d+)([KM])|(\d+)()',text)
            if m:
                m=re.fullmatch(r'(\d+(?:\.\d+)?)([KM]?)',text)
                value=Decimal(m.group(1));unit={'':1,'K':1000,'M':1000000}[m.group(2)]
                # Rounding convention is unknown: subtract one displayed unit.
                precision=len(m.group(1).partition('.')[2]);lower=(value-Decimal(1).scaleb(-precision))*unit
                matches.append(max(0,int(lower)))
    if len(matches)!=1:raise Pending('도술 '+kind+' 재료·가격 판독 필요')
    result=matches[0]
    if kind=='ratio' and (result[1]<=0 or result[0]<0):raise Pending('도술 재료 수량 불명')
    if kind=='price' and not 0<result<=100000000:raise Pending('도술 비용 불명')
    return result


def nondecreasing_balance(first,second):
    """Two independently confident amounts; normal income may increase them."""
    try:return number(second,'balance')>=number(first,'balance')
    except Pending:return False


def numeric_pair_verifier(kind,*,increasing=False):
    """Retain confident per-frame values across same-frame OCR variants."""
    observed=[set(),set()]
    def agreement(first,second):
        parsed=[]
        for index,rows in enumerate((first,second)):
            try:value=number(rows,kind)
            except Pending:parsed.append(None);continue
            observed[index].add(value);parsed.append(value)
        if any(len(values)>1 for values in observed) or None in parsed:return False
        return parsed[1]>=parsed[0] if increasing else parsed[0]==parsed[1]
    return agreement

def transition(rows,current):
    """Independent displayed current→next number confirmation."""
    matches=[]
    for row in rows:
        text=str(row.get('text',''))
        if row.get('score',0)<.90 or not re.fullmatch(r'[\d\s+\-]+',text):continue
        digits=''.join(c for c in text if c.isdecimal())
        if digits==str(current)+str(current+1):matches.append(digits)
    if len(matches)!=1:raise Pending('도술 현재·다음 강화 수치 대조 필요')

# Words on real pixels take seconds to read while the game runs. Every proof is still read again on the frame before input.
REAL_PROOF_SECONDS=12;PIXEL_PROOF_SECONDS=3
WORD_PAD=14;WORD_SHIFT=6  # real pixels

def _proof_seconds(frame):
    return REAL_PROOF_SECONDS if getattr(frame,'hi',None) is not None else PIXEL_PROOF_SECONDS

def _real_words(frame,box):
    """(the words, where they start) in this box of the real screen, or None. Reads the box's own words whatever they are:
    a name, a level, a count or a price."""
    from owner_hd import real_box
    from owner_text import clean,read_area
    x,y,w,h=real_box(box,getattr(frame,'layout',None))
    # With room around it, so no line comes back cut in half, and the one line nearest the middle of the box is the answer.
    left=max(0,x-WORD_PAD);top=max(0,y-WORD_PAD);crop=np.asarray(frame.hi)[top:y+h+WORD_PAD,left:x+w+WORD_PAD]
    if not crop.size:return None
    middle=(x+w/2,y+h/2)
    for language in ('korean','number'):
        rows=[r for r in read_area(None,crop,left=left,top=top,language=language,scale=3) if clean(r['text'])]
        if rows:
            row=min(rows,key=lambda r:abs(r['ry']-middle[1])+abs(r['rx']-middle[0])/4)
            return clean(row['text']),row['rx'],row['ry']
    return None

def same_real_words(frame,box,source):
    """The same words at the same place. The panels are see-through and the world moves behind them, so on the real screen
    the pixels of an unchanged name, level, count or price never held still."""
    now,then=_real_words(frame,box),_real_words(source,box)
    return bool(now and then and now[0]==then[0] and abs(now[1]-then[1])<=WORD_SHIFT and abs(now[2]-then[2])<=WORD_SHIFT)

def _same(frame,proof):
    box,source,tick=proof[:3];mode=proof[3] if len(proof)>3 else 'rgb'
    if not 0<=time.monotonic()-tick<=_proof_seconds(frame):return False
    return _same_pixels(frame,box,source,mode)

def _same_pixels(frame,box,source,mode='rgb'):
    x,y,w,h=box;patch=frame[y:y+h,x:x+w]
    if patch.shape!=source.shape or not source.size or float(source.std())<5:return False
    if mode in ('text','gold') and getattr(frame,'hi',None) is not None and getattr(source,'hi',None) is not None:
        return same_real_words(frame,box,source)
    if mode=='exact':return bool(np.array_equal(patch,source))
    if mode=='style_icon':return same_style_icon(patch,source)
    if mode in ('text','gold'):
        def foreground(im):
            if mode=='text':return cv2.cvtColor(im,cv2.COLOR_RGB2GRAY)>120
            hsv=cv2.cvtColor(im,cv2.COLOR_RGB2HSV)
            return (hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>120)&(hsv[:,:,2]>150)
        a,b=foreground(source),foreground(patch)
        return bool(3<=int(a.sum())<a.size-3 and np.array_equal(a,b))
    if mode!='rgb':return False
    score=float(cv2.matchTemplate(patch,source,cv2.TM_CCOEFF_NORMED)[0,0])
    return bool(np.isfinite(score) and score>=.98)


def refresh_evidence(ui,guard,frames,ticks,proofs,predicate):
    """OCR age cannot authorize input; unchanged fresh source regions can.

    Classification may take longer than the final input proof's lifetime.
    Require the same classified glyphs in the original pair and two new
    target-checked frames, then publish a new bounded input proof. A changed
    glyph, tab, selection, character or settings revision is never refreshed.
    """
    now=time.monotonic()
    if (len(frames)!=2 or len(ticks)!=2 or not proofs
            or any(type(t) not in (int,float) or not np.isfinite(t) or t>now for t in ticks)
            or not 0<=ticks[1]-ticks[0]<=3 or not all(predicate(f) for f in frames)):
        raise Pending('도술 원본 두 화면 근거 확인 필요')
    for frame in frames:
        if any(not _same_pixels(frame,p[0],p[1],p[3] if len(p)>3 else 'rgb') for p in proofs):
            raise Pending('도술 원본 글자·대상 변경')
    def checkpoint():
        ui.context.checkpoint()
        if guard() is not True:raise Pending('현재 캐릭터·도술 설정 변경')
    checkpoint();started=time.monotonic();first=ui.frame().copy();tick1=time.monotonic()
    ui.context.wait(.12);checkpoint();second=ui.frame().copy();tick2=time.monotonic()
    if tick2-started>3 or not predicate(first) or not predicate(second):
        raise Pending('도술 새 화면·대상 재확인 지연')
    for frame in (first,second):
        if any(not _same_pixels(frame,p[0],p[1],p[3] if len(p)>3 else 'rgb') for p in proofs):
            raise Pending('도술 새 화면 글자·재료·대상 변경')
    fresh=[(p[0],p[1],tick2,p[3] if len(p)>3 else 'rgb') for p in proofs]
    ui._owner_last_rows_pair=([first,second],[tick1,tick2],[])
    return fresh

class StyleGrowth:
    def __init__(self,ui,ledger,guard,observe=None):
        if not callable(guard):raise ValueError('캐릭터·설정 확인기 필요')
        self.ui=ui;self.ledger=ledger;self.guard=guard;self.observe=observe
        self._published_values={}
    def _observe(self,section,key,values):
        if self.observe is None or self.guard() is not True:return
        previous=self._published_values.get((section,key),{})
        if all(previous.get(field)==value for field,value in values.items()):return
        self.observe(section,key,values)
        self._published_values[(section,key)]={**previous,**values}
    def _guard(self):
        self.ui.context.checkpoint()
        deadline=getattr(self.ui,'_owner_growth_deadline',None)
        if type(deadline) in (int,float) and time.monotonic()>=deadline:
            raise Pending('도술 성장 방문 시간 종료 · 나머지는 다음 점검에서 계속')
        if self.guard() is not True:raise Pending('현재 캐릭터·도술 설정 변경')
    def _rows(self,box,**kwargs):
        rows=self.ui.rows(box,**kwargs)
        frame=self.ui.last_text_frame;tick=self.ui.last_text_tick
        pair=getattr(self.ui,'_owner_last_rows_pair',None)
        if not pair or len(pair[1])!=2 or not tab(frame):raise Pending('도술 성장 화면 전환·판독 지연')
        x,y,w,h=box
        proof=(box,frame[y:y+h,x:x+w].copy(),tick,'rgb')
        if all(0<=time.monotonic()-t<=3 for t in pair[1]):return rows,proof[:3]
        fresh=refresh_evidence(self.ui,self.guard,pair[0],pair[1],[proof],tab)
        return rows,fresh[0][:3]
    def _style_rows(self,name):
        if not callable(getattr(self.ui,'rows_batch',None)):
            return self._rows(LIST,pair_minimum=.80)
        relevant=lambda r:bool(re.fullmatch(re.escape(name)+r'(?:\+\d{1,3})?',re.sub(r'\s+','',str(r.get('text','')))))
        # The list keeps gliding after a drag, so two frames can disagree on the row.
        # Reading again spends nothing; only a pair that agrees comes out of here.
        for attempt in range(LIST_READ_TRIES):
            try:
                rows=self.ui.rows_batch([(LIST,'korean',.80,'original',relevant)])[0];break
            except Pending as exc:
                if attempt==LIST_READ_TRIES-1 or '두 화면 판독 불일치' not in str(exc):raise
                self._settle_list()
        frames,ticks,_=self.ui._owner_last_rows_pair
        if not all(tab(f) for f in frames):
            raise Pending('도술 계열 판독 지연')
        if not rows:return rows,None
        row,_=named_row(rows,name);bounds=row.get('bounds')
        if not bounds or len(bounds)!=4:raise Pending('도술 계열 글자 위치 확인 필요')
        l,t,r,b=map(int,bounds)
        if not (0<=l<r<=897 and 0<=t<b<=479):raise Pending('도술 계열 글자 위치 확인 필요')
        box=(l,t,r-l,b-t)
        proof=(box,frames[-1][t:b,l:r].copy(),ticks[-1],'text')
        if all(0<=time.monotonic()-value<=_proof_seconds(frames[-1]) for value in ticks):
            self._publish_visible_styles();return rows,proof
        fresh=refresh_evidence(self.ui,self.guard,frames,ticks,[proof],tab)
        self._publish_visible_styles()
        return rows,fresh[0]
    def _publish_visible_styles(self):
        """Reuse already computed OCR for the view, never for action authority."""
        raw=getattr(self.ui,'_owner_last_rows_raw',None)
        pair=getattr(self.ui,'_owner_last_rows_pair',None)
        if self.observe is None or not raw or not pair or not raw[2] or self.guard() is not True:return
        source_frames,source_ticks,answers=raw
        current_frames,current_ticks,_=pair
        if (len(source_frames)!=2 or len(current_frames)!=2 or len(answers[0])!=2
                or any(not 0<=time.monotonic()-tick<=_proof_seconds(current_frames[-1]) for tick in current_ticks)
                or not all(tab(f) for f in current_frames)):return
        real=getattr(current_frames[-1],'hi',None) is not None
        for style in SKILL_REINFORCEMENT_TARGETS:
            try:
                a,av=named_row(answers[0][0],style);b,bv=named_row(answers[0][1],style)
                if av!=bv:continue
                bounds=b.get('bounds')
                if not bounds or len(bounds)!=4:continue
                l,t,r,bottom=map(int,bounds)
                if not 0<=l<r<=897 or not 0<=t<bottom<=479:continue
                box=(l,t,r-l,bottom-t);source=source_frames[-1][t:bottom,l:r]
                # For the table only. Two frames just read the same words, and reading each row four times more cost seconds.
                if not real and not all(_same_pixels(f,box,source,'text') for f in (*source_frames,*current_frames)):continue
                self._observe('skills',style,{'enhance':av})
            except Pending:continue
    def _settle_list(self):
        """Wait out the list's glide. Input-free, and bounded so a moving row only delays."""
        x,y,w,h=LIST
        end=time.monotonic()+LIST_SETTLE_SECONDS;before=self.ui.frame()[y:y+h,x:x+w].astype(int)
        while time.monotonic()<end:
            self.ui.context.wait(.15);self._guard()
            now=self.ui.frame()[y:y+h,x:x+w].astype(int)
            if float(np.abs(now-before).mean())<LIST_STILL:return True
            before=now
        return False
    def _select(self,name):
        # Previous style may have left the twelve-row list scrolled down.
        # Return towards the start before looking for each next style.
        for _ in range(3):
            self._guard();self.ui.drag((790,110),(790,408),lambda f:tab(f) and self.guard() is True)
        self._settle_list()
        previous=None
        for _ in range(12):
            self._guard()
            rows,proof=self._style_rows(name)
            try:row,_=named_row(rows,name)
            except Pending:
                signature=tuple((r['text'],r['y']) for r in rows if r.get('score',0)>=.80)
                if not callable(getattr(self.ui,'rows_batch',None)) and (not signature or signature==previous):
                    raise Pending(name+' 도술 계열 위치 확인 필요')
                previous=signature;self._guard();self.ui.drag((790,408),(790,110),lambda f:tab(f) and self.guard() is True);self._settle_list();continue
            y=row['y']
            before=self.ui.frame();was_selected=selected(before,y)
            x,t,w,h=STYLE_ICON;before_icon=before[t:t+h,x:x+w].copy()
            self.ui.click(790,y,lambda f:tab(f) and _same(f,proof) and self.guard() is True)
            # The row lights up a moment after the click; reading sooner sees it unselected.
            end=time.monotonic()+SELECT_WAIT
            while not selected(self.ui.frame(),y) and time.monotonic()<end:
                self.ui.context.wait(.1);self._guard()
            rows,proof=self._style_rows(name);row,current=named_row(rows,name)
            frames,_,_=self.ui._owner_last_rows_pair
            if not all(selected(frame,row['y']) for frame in frames):raise Pending(name+' 도술 선택 확인 필요')
            after_icon=bind_style_identity(self.ui,name,frames,row['y'])
            if not was_selected and same_style_icon(before_icon,after_icon):
                raise Pending(name+' 선택 후 중앙 계열 아이콘이 바뀌지 않았습니다')
            return row,current,proof
        raise Pending(name+' 도술 목록 끝 확인 필요')
    def _observation(self,name,*,opening=False,use_balance=True):
        # A red count is the game itself saying there is not enough. No number is
        # needed for that, and "0/1" in red reads too weakly to be read at all.
        first=self.ui.frame();self.ui.context.wait(.12);self._guard()
        if material_short(first) and material_short(self.ui.frame()):
            raise Pending(name+' 도술 재료 부족 · 입력 없음')
        relevant=lambda r:bool(re.fullmatch(re.escape(name)+r'(?:\+\d{1,3})?',re.sub(r'\s+','',str(r.get('text','')))))
        levels=([(OPEN_CURRENT,'number',.98,'binary'),(OPEN_NEXT,'number',.98,'binary')]
                if opening else [(TRANSITION,'number',.90)])
        specs=[(LIST,'korean',.80,'original',relevant),*levels,
               (RATIO,'number',.98,'original_or_clahe',None,numeric_pair_verifier('ratio')),
               (PRICE,'number',.98)]
        if use_balance:specs.append((BALANCE,'number',.90,'original_or_clahe',None,numeric_pair_verifier('balance',increasing=True)))
        batched=callable(getattr(self.ui,'rows_batch',None))
        if batched:
            all_rows=self.ui.rows_batch(specs);frames,ticks,_=self.ui._owner_last_rows_pair
            raw=getattr(self.ui,'_owner_last_rows_raw',None)
            if not all(tab(f) for f in frames):raise Pending('도술 성장 화면 변경')
            source=frames[-1];proofs=[(spec[0],source[y:y+h,x:x+w].copy(),ticks[-1],'exact')
                for spec in specs for x,y,w,h in [spec[0]]]
        else: # isolated fake UI and older tests; runtime SkillUI has rows_batch
            all_rows=[];proofs=[]
            for spec in specs:
                box,lang,minimum=spec[:3]
                rows,proof=self._rows(box,language=lang,pair_minimum=minimum)
                all_rows.append(rows);proofs.append((*proof,'exact'))
            frames,_,_=self.ui._owner_last_rows_pair
        row,level=named_row(all_rows[0],name)
        if not all(selected(f,row['y']) for f in frames):raise Pending(name+' 도술 선택 변경')
        offset=3 if opening else 2;fallback_next=None;current_row=None;next_row=None
        def digit(rows,expected,minimum=.98):
            found=[r for r in rows if r.get('score',0)>=minimum and re.fullmatch(r'\d{1,2}',str(r.get('text',''))) and int(r['text'])==expected]
            if len(found)!=1:raise Pending('도술 현재·다음 개별 수치 확인 필요 · 기대 '+str(expected)+' · 판독 '+str([(str(r.get('text','')),round(float(r.get('score',0)),3)) for r in rows]))
            return found[0]
        if opening:
            next_row=digit(all_rows[2],level+1)
            try:current_row=digit(all_rows[1],level)
            except Pending:
                # The centre "19" scores .96 to .99 frame by frame. The list saying
                # style+19 at .98 and the centre saying 20 at .98 are two separate
                # reads of the same fact; nothing here invents a missing digit.
                # The list row at its own bar with the centre at .90 is the same three
                # reads agreeing: list, centre and next.
                weak=[r for r in all_rows[1] if r.get('score',0)>=.90 and str(r.get('text','')).strip()==str(level)]
                listed=batched and re.sub(r'\s+','',str(row.get('text','')))==name+'+'+str(level)
                if not listed or (row.get('score',0)<.98 and len(weak)!=1):raise
                current_row=weak[0] if len(weak)==1 else None
        else:
            try:
                transition(all_rows[1],level)
                current_row=next((r for r in all_rows[1] if r.get('score',0)>=.90 and ''.join(c for c in str(r.get('text','')) if c.isdecimal())==str(level)+str(level+1)),None)
            except Pending:
                # The whole "20 >> 21" reads .82 to .94 on real pages, while each digit
                # read alone gives .96 and up. Three separate reads must say the same
                # thing: the selected list row, the centre current and the centre next.
                # A digit only counts when it equals the value expected; none is invented.
                if (not batched or row.get('score',0)<.90 or level<1
                        or re.sub(r'\s+','',str(row.get('text','')))!=name+'+'+str(level)):
                    raise Pending('도술 현재·다음 강화 수치 대조 필요')
                extra_rows=self.ui.rows_batch([(OPEN_CURRENT,'number',.90,'binary'),(OPEN_NEXT,'number',.90,'binary')])
                extra_frames,extra_ticks,_=self.ui._owner_last_rows_pair
                try:digit(extra_rows[0],level,.90);minimum=.90
                except Pending:
                    # Native +1 reads its centre "1" weakly at any scale. With that read
                    # missing, the list row and the next digit must each reach .98.
                    if row.get('score',0)<.98:raise Pending('도술 현재·다음 강화 수치 대조 필요')
                    minimum=.98
                next_row=digit(extra_rows[1],level+1,minimum)
                if not all(tab(f) and selected(f,row['y']) for f in extra_frames):raise Pending('도술 다음 수치 판독 중 계열 변경')
                bounds=next_row.get('bounds')
                if not bounds or len(bounds)!=4:raise Pending('도술 다음 수치 글자 위치 확인 필요')
                l,t,r,b=map(int,bounds)
                if not 0<=l<r<=897 or not 0<=t<b<=479:raise Pending('도술 다음 수치 글자 위치 변경')
                fallback_next=((l,t,r-l,b-t),extra_frames[-1][t:b,l:r].copy(),extra_ticks[-1],'gold')
        have,need=number(all_rows[offset],'ratio');cost=number(all_rows[offset+1],'price')
        funds=number(all_rows[offset+2],'balance') if use_balance else None
        changing_funds=bool(use_balance and batched and raw and len(raw[2])==len(specs))
        if changing_funds:
            first_funds,second_funds=raw[2][-1]
            if not nondecreasing_balance(first_funds,second_funds):raise Pending('도술 엽전 잔액 감소·판독 변경')
            funds=min(number(first_funds,'balance'),number(second_funds,'balance'))
        if batched:
            # Isolate just the OCR glyph bounds, ignoring animated background.
            # Each extracted binary mask must match exactly in both newer
            # frames and again immediately at the input boundary.
            def tight(index,item,mode):
                bounds=item.get('bounds')
                if not bounds or len(bounds)!=4:raise Pending('도술 글자 위치 확인 필요')
                l,t,r,b=map(int,bounds)
                if not (0<=l<r<=897 and 0<=t<b<=479):raise Pending('도술 글자 위치 확인 필요')
                box=(l,t,r-l,b-t);proofs[index]=(box,source[t:b,l:r].copy(),ticks[-1],mode)
            def selected_value(rows,kind):
                candidates=[]
                for item in rows:
                    try:number([item],kind);candidates.append(item)
                    except Pending:pass
                if len(candidates)!=1:raise Pending('도술 글자 중복 확인 필요')
                return candidates[0]
            # Older isolated UI ports can omit glyph bounds; their full ROI
            # must still remain pixel-identical. Real paired OCR always
            # supplies bounds, so animated scenery is excluded from its proof.
            if row.get('bounds'):tight(0,row,'text')
            # The centre current digit shimmers at every step: on the real 파멸 pages it
            # kept its mask on 1 of 12 opening pages and 2 of 7 mid-step pages, the
            # combined "20 >> 21" on 1 of 7. The list row, gold next digit, ratio and
            # price held. It is still read above; those fixed glyphs carry it to the input.
            proofs[1]=fallback_next
            if opening and next_row.get('bounds'):tight(2,next_row,'gold')
            for index,kind in ((offset,'ratio'),(offset+1,'price'),(offset+2,'balance'))[:3 if use_balance else 2]:
                item=selected_value(all_rows[index],kind)
                if item.get('bounds'):tight(index,item,'text')
        if changing_funds:
            # Money changes independently of fixed target/cost glyphs. Do not
            # require the old balance's pixels to remain identical for the
            # duration of all other OCR; read its current pair last instead.
            proofs.pop()
            # Bind the unchanged normal-coin HUD glyph separately from its
            # changing amount. A currency/layout change cannot be refreshed.
            coin_box=(394,10,14,14)
            proofs.append((coin_box,source[10:24,394:408].copy(),ticks[-1],'rgb'))
        proofs=[proof for proof in proofs if proof is not None]
        # OCR runs sequentially and can exceed the original evidence lifetime.
        # Refresh the evidence only if BOTH current frames contain exactly the
        # same pixels for every previously classified region. Never reuse OCR
        # for a changed crop, and keep the final input-time guard below.
        self._guard();tick=time.monotonic();first=self.ui.frame().copy()
        self.ui.context.wait(.12);self._guard();second=self.ui.frame().copy()
        if (time.monotonic()-tick>_proof_seconds(first) or not tab(first) or not tab(second)
                or not selected(first,row['y']) or not selected(second,row['y'])):
            raise Pending('도술 재료·가격·대상 화면 재확인 지연')
        if opening and not (open_button(first) and open_button(second)):
            raise Pending('도술 개방 버튼 확인 필요')
        if not opening and (open_button(first) or open_button(second)):
            raise Pending('도술 개방 단계 재확인 필요')
        for box,source,_,mode in proofs:
            if not _same_pixels(first,box,source,mode) or not _same_pixels(second,box,source,mode):
                raise Pending('도술 재료·가격·대상 화면 변경: '+str(box))
        fresh=[(box,source,tick,mode) for box,source,_,mode in proofs]
        icon=bind_style_identity(self.ui,name,[first,second],row['y'])
        fresh.append((STYLE_ICON,icon,tick,'style_icon'))
        if changing_funds:
            latest=self.ui.rows_batch([(BALANCE,'number',.90,'original_or_clahe',None,numeric_pair_verifier('balance',increasing=True))])
            latest_rows=latest[0]
            latest_frames,latest_ticks,_=self.ui._owner_last_rows_pair
            latest_raw=self.ui._owner_last_rows_raw[2][0]
            if (not nondecreasing_balance(*latest_raw) or number(latest_raw[0],'balance')<number(second_funds,'balance')
                    or not all(tab(f) and selected(f,row['y']) for f in latest_frames)
                    or any(not 0<=time.monotonic()-t<=3 for t in latest_ticks)):
                raise Pending('도술 최신 엽전 잔액·대상 재확인 필요')
            if any(not _same_pixels(f,p[0],p[1],p[3]) for f in latest_frames for p in fresh):
                raise Pending('도술 잔액 확인 중 대상·비용·재료 변경')
            funds=min(funds,number(latest_raw[0],'balance'),number(latest_raw[1],'balance'))
            item=selected_value(latest_rows,'balance');l,t,r,b=map(int,item.get('bounds') or (0,0,0,0))
            if not 0<=l<r<=897 or not 0<=t<b<=479:raise Pending('도술 최신 잔액 글자 위치 확인 필요')
            latest_proof=((l,t,r-l,b-t),latest_frames[-1][t:b,l:r].copy(),latest_ticks[-1],'text')
            # The final click still requires this exact latest balance crop.
            fresh.append(latest_proof)
        return {'style':name,'level':level,'y':row['y'],'have':have,'need':need,'price':cost,'funds':funds},fresh
    def run(self,name,target,max_steps=5,*,breakthrough_target=0):
        if name not in SKILL_REINFORCEMENT_TARGETS or type(target) is not int or not 0<=target<=50:
            raise Pending('도술 계열·목표 수치 확인 필요')
        if type(max_steps) is not int or not 1<=max_steps<=10:raise ValueError('반복 제한 오류')
        if type(breakthrough_target) is not int or not 0<=breakthrough_target<=9999:
            raise Pending('도술 계열 돌파 목표 확인 필요')
        # A positive breakthrough target requires reaching +50 first. This
        # does not insert another +50 cycle between consecutive breakthroughs.
        if breakthrough_target>0:target=50
        self._select(name);verified=None
        for _ in range(max_steps):
            self._guard();step_started=time.monotonic()
            if verified and time.monotonic()-verified[2]<=2 and all(selected(f,verified[0]['y']) for f in [self.ui.frame()]):
                # The step before just proved this row at this level on two frames: no second read of the list (3 s a step).
                row,current=verified[0],verified[1]
            else:
                rows,_=self._style_rows(name);row,current=named_row(rows,name)
                if not all(selected(f,row['y']) for f in self.ui._owner_last_rows_pair[0]):raise Pending('도술 대상 선택 확인 필요')
            rows_read=time.monotonic()
            self._observe('skills',name,{'enhance':current})
            intents=self.ledger.item.setdefault('style_growth_intents',{})
            if not isinstance(intents,dict) or any(not isinstance(v,dict) for v in intents.values()):
                raise Pending('도술 계열 강화 입력 기록 형식 확인 필요')
            prior=intents.get(name)
            if prior and prior.get('status')=='prepared':
                prior['status']='aborted_before_input';self.ledger.event('style_growth_aborted',style=name)
            if prior and prior.get('status') in ('intent','sent'):
                if current==prior.get('before',-2)+1:
                    prior.update(status='observed_after',current=current);self.ledger.event('style_growth_reconciled',style=name,current=current)
                else:raise Pending('이전 도술 강화 결과 확인 필요: '+name)
            if current>=target:return {'status':'target_reached','style':name,'level':current}
            if any(style!=name and old.get('status') in ('intent','sent') for style,old in intents.items()):
                raise Pending('다른 도술 계열의 미확인 강화 결과 우선 확인 필요')
            from owner_skill_upgrade_candidate import has_pending
            if has_pending(self.ledger):raise Pending('이전 도술 각성·돌파 결과 우선 확인 필요')
            opening=current%10==9
            # Several reads must agree here and any one can miss by chance. Each is
            # read-only, and the first shortage or real change still ends it.
            # The game dims this button without the coins, and the input below requires it lit.
            use_balance=False
            for attempt in range(OBSERVE_TRIES):
                try:
                    obs,proofs=self._observation(name,opening=opening,use_balance=use_balance);break
                except Pending as exc:
                    if attempt==OBSERVE_TRIES-1 or not any(word in str(exc) for word in STYLE_READ_MISSES+('개별 수치','판독 필요','재확인 지연','수치 대조','아이콘 두 화면')):raise
                    # The balance is small, animated text ("1.17M" read as "17M"). The
                    # game itself dims this button without the coins, and the input
                    # below requires it lit, so an unread balance need not stop it.
                    if attempt>=1 and str(BALANCE) in str(exc):use_balance=False
                    self.ui.context.wait(.3);self._guard()
            observed_at=time.monotonic()
            if obs['level']!=current or obs['have']<obs['need'] or (obs['funds'] is not None and obs['funds']<obs['price']):
                raise Pending(name+' 도술 재료·엽전 부족 또는 변경')
            intents[name]={'status':'prepared','before':current,'target':target,'price':obs['price'],'at':time.time()}
            self.ledger.event('style_growth_intent',style=name,before=current,price=obs['price'])
            def commit_guard(frame):
                valid=(self.guard() is True and tab(frame) and selected(frame,obs['y'])
                       and active(frame) and (open_button(frame) if opening else not open_button(frame))
                       and all(_same(frame,p) for p in proofs))
                if not valid:return False
                # Persist before issuing input. Any exception from the click
                # after this point is uncertain and must not be replayed.
                intents[name]['status']='sent';self.ledger.event('style_growth_sent',style=name,before=current)
                return self.guard() is True and all(_same(frame,p) for p in proofs)
            try:self.ui.click(480,449,commit_guard)
            except BaseException:
                if intents[name]['status']=='prepared':
                    intents[name]['status']='aborted_before_input';self.ledger.event('style_growth_aborted',style=name)
                raise
            self.ui.context.wait(.5)
            from owner_short_notice import shown
            def out_of_coins():
                if not shown(self.ui.frame()):return None
                intents[name].update(status='short_of_coins',after=current)
                self.ledger.event('style_growth_short',style=name,before=current)
                return {'status':'short_of_coins','style':name,'level':current}
            short=out_of_coins()
            if short:return short
            # Reading the rows gives the message the moment it needs, if it was not up yet.
            try:
                rows,_=self._style_rows(name);newrow,new=named_row(rows,name)
                if new!=current+1 or not all(selected(f,newrow['y']) for f in self.ui._owner_last_rows_pair[0]):
                    raise Pending(name+' 도술 강화 후 수치 재확인 필요')
            except Pending:
                short=out_of_coins()
                if short:return short
                raise
            # A confirmed step redraws the emblem (18:37 real hold). The list row just
            # proved +1 on this selected style, so the next settled read learns it again.
            bindings=getattr(self.ui,'_owner_style_bindings',None)
            if isinstance(bindings,dict):bindings.pop(name,None)
            intents[name].update(status='confirmed',after=new)
            self.ledger.event('style_growth_verified',style=name,before=current,after=new)
            self._observe('skills',name,{'enhance':new});verified=(newrow,new,time.monotonic())
            # Where the time goes, for speeding it up (user 11-06): list read, checks before the press, press and result.
            now=time.monotonic()
            logging.getLogger('project_gui.DKB').info('도술 %s %d→%d · 목록 %.1f초 · 확인 %.1f초 · 입력·결과 %.1f초',
                name,current,new,rows_read-step_started,observed_at-rows_read,now-observed_at)
        return {'status':'partial','style':name,'level':new}

def run_configured(ui,ledger,document,guard,*,max_steps=10,observe=None,include_individual=True):
    """Run enabled style targets, continuing only past safely held rows.

    The outer caller must open the actual growth style tab, give a guard that
    checks current character + unchanged settings revision, and close it. This
    function never runs automatically on import or opens a game menu itself.
    """
    from owner_gear_settings_candidate import validate
    validate(document)
    from owner_skill_upgrade_candidate import SkillUpgrade,SkillUpgradePort,has_pending
    statuses=[];worker=StyleGrowth(ui,ledger,guard,observe)
    if has_pending(ledger):
        return [{'status':'held','reason':'이전 도술 각성·돌파 결과 우선 재확인 필요'}]
    # Reconcile a sent enhancement before any unrelated style may consume.
    prior_styles=ledger.item.get('style_growth_intents',{})
    if not isinstance(prior_styles,dict) or any(not isinstance(v,dict) for v in prior_styles.values()):
        raise Pending('도술 계열 강화 입력 기록 형식 확인 필요')
    for name,prior in prior_styles.items():
        if prior.get('status') not in ('intent','sent'):continue
        before=prior.get('before')
        if name not in document['skills'] or type(before) is not int or not 0<=before<50:
            return [{'status':'held','style':name,'reason':'이전 도술 강화 대상·단계 확인 필요'}]
        try:statuses.append(worker.run(name,before+1,max_steps=1))
        except Pending as exc:return statuses+[{'status':'held','style':name,'reason':str(exc)}]
    for name,row in document['skills'].items():
        if not row['enabled']:continue
        worker._guard()
        for attempt in range(STYLE_READ_TRIES):
            try:
                from owner_growth_reading import breakthrough_allowed
                breakthrough=row.get('breakthrough',0) if breakthrough_allowed() else 0
                result=worker.run(name,row['enhance'],max_steps=max_steps,breakthrough_target=breakthrough)
                statuses.append(result)
                if result.get('status')=='short_of_coins':return statuses
                if breakthrough>0 and result.get('level',0)>=50:
                    statuses.append(SkillUpgrade(SkillUpgradePort(ui,guard),ledger,guard,observe).run(
                        name,'breakthrough',breakthrough,max_steps=max_steps))
                break
            except Pending as exc:
                sent=ledger.item.get('style_growth_intents',{}).get(name,{}).get('status') in ('intent','sent') or has_pending(ledger)
                # Gold and hit numbers change behind the menu, so a read can miss by
                # chance. Reading again spends nothing; a sent input is never retried.
                if not sent and attempt<STYLE_READ_TRIES-1 and any(word in str(exc) for word in STYLE_READ_MISSES):
                    ui.context.wait(.4);continue
                statuses.append({'status':'held','style':name,'reason':str(exc)})
                break
        if ledger.item.get('style_growth_intents',{}).get(name,{}).get('status') in ('intent','sent') or has_pending(ledger):break
    for name,row in document.get('individual',{}).items():
        if include_individual and row.get('enabled'):
            statuses.append({'status':'held','individual':name,
                'reason':'개별 도술 각성 화면 확인 필요'})
    return statuses

def _nav(ui,detector,name,guard,extra=lambda f:True):
    """Two independent detections plus the existing immediate input guard."""
    ui.context.checkpoint();first=ui.frame();ui.context.wait(.12);second=ui.frame()
    a=detector.find(name,first,threshold=.95);b=detector.find(name,second,threshold=.95)
    if not a or not b or abs(a[0]-b[0])>3 or abs(a[1]-b[1])>3:
        raise Pending('도술 성장 메뉴 확인 필요: '+name)
    def fresh(frame):return guard() is True and extra(frame) and bool(detector.find(name,frame,threshold=.95))
    ui.click(b[0],b[1],fresh)

def _return_from_growth(ui,context,detector,return_guard):
    """Restore only our positively identified growth menu; otherwise stop."""
    stopped=getattr(context,'stop',None)
    if stopped is not None and stopped.is_set():
        context.checkpoint()
        raise SkillGrowthNavigationError('중지 중 도술 화면 복귀 보류')
    try:
        # The native growth exit can be a blurred transition. Wait without
        # input for a positively identified menu or field before deciding
        # cleanup failed; never click that transitional frame.
        end=time.monotonic()+8
        while True:
            context.checkpoint();frame=ui.frame();context.wait(.12);second=ui.frame()
            field=ui.normal_frame(frame) and ui.normal_frame(second)
            menu=bool(detector.find('체크_성장',frame,threshold=.95) and detector.find('체크_성장',second,threshold=.95))
            if field or menu or time.monotonic()>=end:break
            context.wait(.2)
        if ui.normal_frame(frame) and ui.normal_frame(second):return
        if not (return_guard() is True and detector.find('체크_성장',frame,threshold=.95)
                and detector.find('체크_성장',second,threshold=.95)):
            raise SkillGrowthNavigationError('도술 메뉴 복귀 화면 확인 필요')
        ui.click(21,19,lambda f:return_guard() is True and bool(detector.find('체크_성장',f,threshold=.95)))
        ui.wait(ui.normal_frame,seconds=5);context.wait(.12)
        if not ui.normal_frame(ui.frame()):raise SkillGrowthNavigationError('도술 메뉴 종료 후 게임 화면 확인 필요')
    except SkillGrowthNavigationError:
        raise
    except Exception as exc:
        raise SkillGrowthNavigationError('도술 메뉴 복귀 실패') from exc

def _select_visible_awaken_icon(ui,name,guard):
    """Select a requested visible row only when both icon frames agree."""
    from owner_skill_ui import catalog,identify_icon
    cat=catalog();entry=cat['all_skill_names'].get(name)
    if not entry or str(entry.get('id')) not in cat['skills']:return False
    sid=entry['id'];start=time.monotonic();first=ui.frame();ui.context.wait(.12);second=ui.frame()
    if time.monotonic()-start>3 or guard() is not True or not awakening_tab(first) or not awakening_tab(second):return False
    matches=[]
    for index in range(9):
        box=(704,75+45*index,41,38)
        if all(identify_icon(f,box)==sid for f in (first,second)):matches.append((index,box))
    if len(matches)!=1:return False
    index,box=matches[0];y=85+45*index
    if all(awaken_selected(f,y) for f in (first,second)):return True
    def proof(frame):
        return guard() is True and time.monotonic()-start<=3 and awakening_tab(frame) and identify_icon(frame,box)==sid
    ui.click(755,y,proof)
    return True

def _exact_skill_name(name):
    from owner_skill_ui import clean
    return lambda r:r.get('score',0)>=.94 and clean(r.get('text',''))==clean(name)

def _select_visible_awaken_name(ui,name,guard):
    """Fallback for catalogued skills without a reusable icon asset."""
    if not callable(getattr(ui,'rows_batch',None)):return False
    rows=ui.rows_batch([((728,70,128,365),'korean',.94,'original',_exact_skill_name(name))])[0]
    frames,ticks,_=ui._owner_last_rows_pair;now=time.monotonic()
    if len(rows)!=1 or not _exact_skill_name(name)(rows[0]) or any(not 0<=now-t<=3 for t in ticks) or not all(awakening_tab(f) for f in frames):return False
    row=rows[0];bounds=row.get('bounds')
    if not bounds or len(bounds)!=4:return False
    l,t,r,b=map(int,bounds)
    if not (0<=l<r<=897 and 0<=t<b<=479):return False
    box=(l,t,r-l,b-t);source=frames[-1][t:b,l:r].copy();tick=ticks[-1]
    if all(awaken_selected(f,row['y']) for f in frames):return True
    ui.click(755,row['y'],lambda f:guard() is True and awakening_tab(f) and _same(f,(box,source,tick,'text')))
    return True

def _inspect_awaken_name(ui,name,guard):
    if not callable(getattr(ui,'rows_batch',None)):return None
    exact=_exact_skill_name(name)
    specs=[((728,70,128,365),'korean',.94,'original',exact),((345,62,105,28),'korean',.94,'original',exact)]
    matches=ui.rows_batch(specs);frames,ticks,_=ui._owner_last_rows_pair;now=time.monotonic()
    if (any(len(rows)!=1 or not exact(rows[0]) for rows in matches) or any(not 0<=now-t<=3 for t in ticks)
            or guard() is not True or not all(awakening_tab(f) and awaken_zero_stage(f) for f in frames)):
        return None
    y=matches[0][0]['y']
    if not all(awaken_selected(f,y) for f in frames):return None
    return {'name':name,'awaken':0,'insufficient_zero100':all(awaken_red_zero100(f) for f in frames)}

def _awaken_list_unchanged(a,b):
    if not awakening_tab(a) or not awakening_tab(b):return False
    left=a[70:435,704:856];right=b[70:435,704:856]
    if left.shape!=right.shape or not left.size or float(left.std())<5:return False
    score=float(cv2.matchTemplate(left,right,cv2.TM_CCOEFF_NORMED)[0,0])
    return bool(np.isfinite(score) and score>=.999)

def _seek_awaken(ui,name,guard,*,max_pages=20):
    """Bounded use of the existing list drag, with cancellation fences."""
    if type(max_pages) is not int or not 1<=max_pages<=20:raise ValueError('도술 목록 탐색 범위 오류')
    def checkpoint():
        ui.context.checkpoint()
        if guard() is not True:raise Pending('개별 도술 캐릭터·설정 변경')
    def slide(start,end):
        checkpoint();before=ui.frame()
        if not awakening_tab(before):raise Pending('개별 도술 목록 화면 변경')
        ui.drag(start,end,lambda f:guard() is True and awakening_tab(f))
        checkpoint();after=ui.frame()
        return _awaken_list_unchanged(before,after)
    checkpoint()
    if _select_visible_awaken_icon(ui,name,guard):return True
    if _select_visible_awaken_name(ui,name,guard):return True
    # Rewind toward the start. Two stationary drags establish a bounded top
    # condition; the cap prevents an endless retry if the view keeps changing.
    stopped=0
    for _ in range(max_pages):
        stopped=stopped+1 if slide((790,110),(790,408)) else 0
        if stopped>=2:break
    stopped=0
    for _ in range(max_pages):
        checkpoint()
        if _select_visible_awaken_icon(ui,name,guard):return True
        if _select_visible_awaken_name(ui,name,guard):return True
        stopped=stopped+1 if slide((790,408),(790,110)) else 0
        if stopped>=2:return False
    return False

def inspect_configured_awaken(ui,document,guard,observe,*,ledger=None,max_steps=5):
    """Reuse bounded selection; a supplied durable ledger enables guarded steps.

    Legacy/read-only callers omit ledger and never receive action authority.
    """
    names=[name for name,row in document.get('individual',{}).items() if row.get('enabled')]
    if not names:return []
    ui.context.checkpoint()
    if guard() is not True:raise Pending('개별 도술 캐릭터·설정 확인 필요')
    if not awakening_tab(ui.frame()):
        ui.click(44,113,lambda f:guard() is True and awaken_unselected(f))
    statuses=[]
    for name in names:
        first=ui.wait(awakening_tab);ui.context.wait(.12);second=ui.frame()
        if not awakening_tab(first) or not awakening_tab(second) or guard() is not True:
            raise Pending('개별 도술 각성 화면 재확인 필요')
        observed=inspect_awaken_selected((first,second),name);selected=False
        if observed is None:
            selected=_seek_awaken(ui,name,guard)
            if selected:
                first=ui.wait(awakening_tab);ui.context.wait(.12);second=ui.frame()
                if guard() is not True:raise Pending('개별 도술 캐릭터·설정 변경')
                observed=inspect_awaken_selected((first,second),name)
                if observed is None:observed=_inspect_awaken_name(ui,name,guard)
        if ledger is not None:
            from owner_skill_upgrade_candidate import SkillUpgrade,SkillUpgradePort,has_pending
            try:
                if observed is None and not selected:raise Pending('선택된 도술·각성 단계 확인 필요')
                target=document['individual'][name].get('awaken')
                if type(target) is not int:raise Pending('개별 도술 각성 목표 확인 필요')
                statuses.append(SkillUpgrade(SkillUpgradePort(ui,guard),ledger,guard,observe).run(
                    name,'awaken',target,max_steps=max_steps))
            except Pending as exc:statuses.append({'status':'held','individual':name,'reason':str(exc)})
            if has_pending(ledger):break
            continue
        if observed:
            observe('individual',name,{'awaken':observed['awaken']})
            goal=document['individual'][name].get('awaken')
            if goal==0:statuses.append({'status':'target_reached','individual':name,'awaken':0})
            elif observed['insufficient_zero100']:
                statuses.append({'status':'held','individual':name,'reason':'각성 조각 0/100 · 재료 부족'})
            else:statuses.append({'status':'held','individual':name,'reason':'각성 재료·실행 조건 확인 필요'})
        else:statuses.append({'status':'held','individual':name,'reason':'선택된 도술·각성 단계 확인 필요'})
    return statuses


def reconcile_pending_upgrades(ui,ledger,guard,observe):
    """Read only a previous sent action's exact next stage; never replay it."""
    from owner_skill_upgrade_candidate import SkillUpgrade,SkillUpgradePort,has_pending
    statuses=[]
    if not has_pending(ledger):return statuses
    for receipt in ledger.item.get('skill_upgrade_intents',{}).values():
        if receipt.get('status') not in ('intent','sent'):continue
        name=receipt.get('name');kind=receipt.get('kind');before=receipt.get('before')
        if not isinstance(name,str) or type(before) is not int or not 0<=before<9999:
            raise Pending('이전 도술 입력 대상·단계 기록 확인 필요')
        if kind=='breakthrough':
            if not tab(ui.frame()):ui.click(44,81,lambda f:guard() is True and unselected_enhance(f))
            StyleGrowth(ui,ledger,guard)._select(name)
        elif kind=='awaken':
            if not awakening_tab(ui.frame()):ui.click(44,113,lambda f:guard() is True and awaken_unselected(f))
            if not _seek_awaken(ui,name,guard):raise Pending('이전 각성 도술 위치 재확인 필요')
        else:raise Pending('이전 도술 입력 종류 기록 확인 필요')
        # A matching +1 result returns before quote/commit. An unchanged or
        # unknown stage raises Pending while leaving the sent receipt intact.
        statuses.append(SkillUpgrade(SkillUpgradePort(ui,guard),ledger,guard,observe).run(
            name,kind,before+1,max_steps=1,result_only=True))
    return statuses

def run_after_native(adapter,context,inputs):
    """One bounded same-worker visit after native growth has returned."""
    from owner_progression import state
    from owner_quest_preflight import read_power
    from owner_hunt_rules_candidate import configured_identity
    from owner_gear_settings_candidate import Store
    from owner_skill_goal import runtime_ledger
    from owner_skill_ui import SkillUI
    from roi_runtime import RoiDetector
    root=adapter.project.root
    if adapter.values.get('auto_growth.taoist.enabled') is not True:return []
    identity=configured_identity(root);store=Store(root,identity);document,revision=store.snapshot()
    if revision=='missing':return []
    styles_enabled=any(r['enabled'] for r in document['skills'].values())
    individuals=[name for name,row in document.get('individual',{}).items() if row.get('enabled')]
    started=time.monotonic();progress=state(adapter)
    if not read_power(adapter,context,inputs) or progress.observed<started or not progress.character:
        raise Pending('도술 성장 캐릭터 재확인 필요')
    character=progress.character;ledger=runtime_ledger(adapter,character)
    from owner_skill_upgrade_candidate import has_pending
    if not styles_enabled and not individuals and not has_pending(ledger):return []
    def guard():
        try:
            current=state(adapter);age=time.monotonic()-current.observed
            return (current.character==character and 0<=age<=180
                    and configured_identity(root)==identity and store.revision()==revision)
        except (OSError,ValueError,TypeError):return False
    def return_guard():
        # Closing our own verified menu is safe after the user edits targets;
        # resource actions continue to require the original revision guard.
        try:
            current=state(adapter);age=time.monotonic()-current.observed
            return current.character==character and 0<=age<=180 and configured_identity(root)==identity
        except (OSError,ValueError,TypeError):return False
    names=('버튼_전체매뉴','버튼_전체매뉴_성장','체크_성장','버튼_성장_도술탭')
    detector=RoiDetector(Path(root)/'profiles/DKB',list(names));ui=SkillUI(adapter,context,inputs)
    # Keep a return margin inside the existing180-second identity lifetime.
    # This visit limit never overrides Stop or reconciles an uncertain input.
    # The guard holds a reading 180 s; 165 of it are used (was 120: three levels a visit, pc1 16:04).
    ui._owner_growth_deadline=progress.observed+165
    if styles_enabled:ui.prepare_batch_engines()
    if not ui.normal() or guard() is not True:raise Pending('도술 성장 시작 화면 확인 필요')
    entered=False
    try:
        entered=True # first navigation may succeed before its caller returns
        _nav(ui,detector,'버튼_전체매뉴',guard,ui.normal_frame)
        ui.wait(lambda f:bool(detector.find('버튼_전체매뉴_성장',f,threshold=.95)))
        _nav(ui,detector,'버튼_전체매뉴_성장',guard)
        ui.wait(lambda f:bool(detector.find('체크_성장',f,threshold=.95)))
        if not skill_section(ui.frame()):
            _nav(ui,detector,'버튼_성장_도술탭',guard,lambda f:bool(detector.find('체크_성장',f,threshold=.95)))
        if styles_enabled and not tab(ui.frame()):
            ui.click(44,81,lambda f:guard() is True and bool(detector.find('체크_성장',f,threshold=.95)) and unselected_enhance(f))
        statuses=[]
        def observe(section,key,values):
            if guard() is not True:return
            try:
                from owner_growth_current import observe_value
                observe_value(root,identity,section,key,values,verified=True)
            except (ImportError,OSError,ValueError,TypeError):pass
        if has_pending(ledger):
            try:statuses.extend(reconcile_pending_upgrades(ui,ledger,guard,observe))
            except Pending as exc:
                return statuses+[{'status':'held','reason':str(exc)}]
        if styles_enabled:
            if not tab(ui.frame()):ui.click(44,81,lambda f:guard() is True and unselected_enhance(f))
            first=ui.wait(tab);context.wait(.12);second=ui.frame()
            if not tab(first) or not tab(second):raise Pending('도술 강화 탭 재확인 필요')
            statuses.extend(run_configured(ui,ledger,document,guard,observe=observe,include_individual=False))
            if any(v.get('status') in ('intent','sent') for v in ledger.item.get('style_growth_intents',{}).values()):
                return statuses
        if individuals:
            statuses.extend(inspect_configured_awaken(ui,document,guard,observe,ledger=ledger))
        return statuses
    finally:
        # Do not send any cleanup input after stop or on an unknown screen.
        try:
            if entered:_return_from_growth(ui,context,detector,return_guard)
        finally:
            ui._owner_rows_cache=None;ui._owner_rows_context=None;ui._owner_rows_engines={}
            ui._owner_last_rows_raw=None;ui._owner_last_rows_pair=None
            ui._owner_style_bindings={};ui._owner_style_bindings_context=None
            ui._owner_growth_deadline=None

def dispatch_after_native(adapter,context,inputs):
    """Invoke only after the native feature loop has returned to the field."""
    import logging
    log=logging.getLogger('project_gui.DKB')
    if getattr(adapter,'_owner_growth_reconcile_only',False) is True:
        adapter._owner_style_growth_outcome={'state':'reconcile_only'};return True
    if adapter.values.get('auto_growth.taoist.enabled') is not True:
        adapter._owner_style_growth_outcome={'state':'disabled'};return True
    try:
        statuses=run_after_native(adapter,context,inputs)
        for row in statuses:log.info('도술 성장 · %s',row)
        adapter._owner_style_growth_outcome={'state':'processed_unverified','statuses':statuses}
    except (Pending,OSError,ValueError,TypeError) as exc:
        adapter._owner_style_growth_outcome={'state':'held','reason':str(exc)[:120]}
        log.info('도술 성장 보류 · %s',str(exc))
    return True

def install(gui):
    """The timetable and quest service own post-native dispatch.

    A bare growth-entry result only proves that its menu opened; it must not
    start style growth from inside that menu.
    """
    gui._owner_style_growth=True
