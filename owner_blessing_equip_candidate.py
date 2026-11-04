"""Verified same-slot blessing compare and one equip input; opt-in only.

The caller opens a comparison dialog on the existing input-owning worker.
No in-game action occurs on import. Unreadable or different slots are held.
"""
from pathlib import Path
import base64,hashlib,json,os,re,tempfile,time
import cv2
import numpy as np
from PIL import Image
from owner_blessing_priority_candidate import compare,PATTERNS,GRADES

ASSET=Path(__file__).with_name('owner_blessing_assets_candidate')/'compare_equip_button.png'
WORN=ASSET.with_name('compare_worn_mark.png')
SINGLE_MARK=ASSET.with_name('worn_single_mark.png')
SINGLE_REMOVE=ASSET.with_name('worn_remove_button.png')
SINGLE_CLOSE=ASSET.with_name('worn_close_button.png')
_scan_cursor={}

def parse_title(value):
    text=re.sub(r'\s+','',str(value));match=re.match(r'^(봉황|나비|도깨비|연꽃|토끼)가호장식([1-5])(?:\(귀속\))?$',text)
    if not match:return None
    return {'pattern':match.group(1),'slot':int(match.group(2))}

def read_compare(root,frame):
    from tools.ocr_support import get_paddle_engine
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    engine=get_paddle_engine(root,language='korean')
    def texts(box):
        x1,y1,x2,y2=box;crop=frame[y1:y2,x1:x2]
        if not crop.size:return []
        result=[]
        for page in engine.predict(cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_LINEAR)):
            result.extend((str(t),float(s)) for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',())))
        return result
    result=[]
    for title_box,grade_box,digit_base in (((300,94,431,120),(304,125,363,145),366),((453,94,590,120),(456,125,516,145),522)):
        titles=[p for text,score in texts(title_box) if score>=.80 for p in [parse_title(text)] if p]
        if not titles:
            # The current font splits a title: 토끼가호 + 장식1 + 1(귀속), the slot digit read twice.
            pieces=texts(title_box)
            if pieces and all(score>=.80 for _,score in pieces):
                joined=re.sub(r'\s+','',''.join(text for text,_ in pieces))
                match=re.fullmatch(r'(봉황|나비|도깨비|연꽃|토끼)가호장식([1-5])\2?(?:\(귀속\))?',joined)
                if match:titles=[{'pattern':match.group(1),'slot':int(match.group(2))}]
        if not titles:
            # Korean OCR can read the small slot digit as ']' or omit it. Only
            # a separately high-confidence numerical crop may supply it.
            names=[]
            for text,score in texts(title_box):
                clean=re.sub(r'\s+','',str(text))
                match=re.fullmatch(r'(봉황|나비|도깨비|연꽃|토끼)가호장식\]?(?:\(귀속\))?',clean)
                if score>=.80 and match:names.append(match.group(1))
            if len(names)==1:
                x=digit_base+(8 if names[0]=='도깨비' else 0)
                crop=frame[99:113,x:x+8]
                number_engine=get_paddle_engine(root,language='number');values=[]
                for page in number_engine.predict(cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_LINEAR)):
                    for value,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
                        if re.fullmatch(r'[1-5]',str(value)) and float(score)>=.97:values.append(int(value))
                if len(values)==1:titles=[{'pattern':names[0],'slot':values[0]}]
        grades=[text.strip() for text,score in texts(grade_box) if score>=.90 and text.strip() in GRADES]
        if len(titles)!=1 or len(grades)!=1:return None
        result.append(dict(titles[0],grade=grades[0],verified=True))
    # The comparison must be for the same equipment category.
    if result[0]['slot']!=result[1]['slot']:return None
    # Independently compare the printed slot glyphs despite different panel
    # background colours; OCR alone may misread a small digit on both sides.
    left_x=366+(8 if result[0]['pattern']=='도깨비' else 0)
    right_x=522+(8 if result[1]['pattern']=='도깨비' else 0)
    left=cv2.cvtColor(frame[99:113,left_x:left_x+8],cv2.COLOR_RGB2GRAY)
    right=cv2.cvtColor(frame[99:113,right_x:right_x+8],cv2.COLOR_RGB2GRAY)
    if left.shape!=(14,8) or right.shape!=(14,8):return None
    score=float(cv2.matchTemplate(left,right,cv2.TM_CCOEFF_NORMED)[0,0])
    if not np.isfinite(score) or score<.90:return None
    return tuple(result)

def equip_hit(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    try:needle=np.asarray(Image.open(ASSET).convert('RGB'))
    except OSError:return None
    if needle.shape!=(23,66,3):return None
    x1,y1,x2,y2=525,347,600,379;patch=frame[y1:y2,x1:x2]
    _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED))
    if score<.96:return None
    x,y=x1+pos[0],y1+pos[1]
    return (x+33,y+11,(x,y,x+66,y+23))

def compare_worn_mark(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
    try:needle=np.asarray(Image.open(WORN).convert('RGB'))
    except OSError:return False
    if needle.shape!=(12,12,3):return False
    def score(x):return float(cv2.minMaxLoc(cv2.matchTemplate(frame[112:140,x:x+25],needle,cv2.TM_CCOEFF_NORMED))[1])
    return score(340)>=.90 and score(495)<.75

def same_compare_appearance(first,second):
    """Conservative pixel check when OCR splits identical titles differently."""
    if not isinstance(first,np.ndarray) or not isinstance(second,np.ndarray) or first.shape!=(479,897,3) or second.shape!=first.shape:return False
    a=first[94:163,296:600];b=second[94:163,296:600]
    delta=float(np.abs(a.astype(np.float32)-b.astype(np.float32)).mean())
    corr=float(cv2.matchTemplate(a,b,cv2.TM_CCOEFF_NORMED)[0,0])
    return bool(np.isfinite(corr) and corr>=.995 and delta<=1.)

def _intent_path(root,identity):
    key=hashlib.sha256(identity.strip().encode('utf-8')).hexdigest()[:24]
    return Path(root)/'settings'/('owner-blessing-equip-'+key+'.json')

def _save(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.blessing-equip-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf8') as out:json.dump(doc,out,ensure_ascii=False);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def equip_selected(service,context,identity,order,*,settings_check,reader=read_compare,candidate_icon=None,candidate_check=None,expected_category=None):
    """Return pending after one input; an uncertain prior input blocks reuse."""
    if not isinstance(identity,str) or not identity.strip() or not callable(settings_check):return 'hold_identity'
    root=Path(service.adapter.project.root);path=_intent_path(root,identity)
    try:
        if path.exists():
            pending=json.loads(path.read_text(encoding='utf8')).get('pending')
            if isinstance(pending,dict) and pending.get('phase')=='prepared':
                _save(path,{'version':1,'pending':None,'last_result':'preinput_aborted'})
            elif pending is not None:return 'hold_pending'
    except (OSError,ValueError,AttributeError):return 'hold_history'
    values=[];frames=[];candidate_proven=callable(candidate_check)
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture()
        if callable(candidate_check) and candidate_check(frame) is not True:candidate_proven=False
        value=reader(root,frame)
        if equip_hit(frame) is None or not compare_worn_mark(frame):
            from owner_gear_hold_capture_candidate import enqueue
            enqueue(service.adapter.project.root,'blessing-compare','장착 버튼=%s · 착용 표시=%s'%(equip_hit(frame) is not None,bool(compare_worn_mark(frame))),(frame,))
            return 'hold_screen'
        values.append(value);frames.append(frame);context.wait(.12)
    if values[0] is None and values[1] is not None and same_compare_appearance(frames[0],frames[1]):values[0]=values[1]
    if values[1] is None and values[0] is not None and same_compare_appearance(frames[0],frames[1]):values[1]=values[0]
    if any(value is None for value in values):
        from owner_gear_hold_capture_candidate import enqueue
        enqueue(service.adapter.project.root,'blessing-compare','글자 판독 실패',(frames[-1],))
        return 'hold_screen'
    if expected_category is not None and (values[0][0].get('slot')!=expected_category or values[0][1].get('slot')!=expected_category):return 'hold_category'
    if values[0]!=values[1] or compare(values[0][0],values[0][1],order)!='replace':return 'hold_policy'
    if settings_check() is not True:return 'hold_settings'
    icon=None
    if candidate_proven and isinstance(candidate_icon,np.ndarray) and candidate_icon.shape==(18,18,3) and candidate_icon.dtype==np.uint8:
        icon=base64.b64encode(candidate_icon.tobytes()).decode('ascii')
    _save(path,{'version':1,'pending':{'phase':'prepared','before':values[0][0],
          'candidate':values[0][1],'icon':icon,'created_at':time.time()}})
    try:
        context.checkpoint();service.check();frame=service.capture()
        if callable(candidate_check) and candidate_check(frame) is not True:icon=None
        fresh=reader(root,frame);hit=equip_hit(frame)
        if fresh is None and same_compare_appearance(frames[1],frame):fresh=values[1]
        if fresh!=values[0] or hit is None or not compare_worn_mark(frame) or settings_check() is not True:return 'hold_final_preinput'
        _save(path,{'version':1,'pending':{'phase':'sent','before':fresh[0],
              'candidate':fresh[1],'icon':icon,'created_at':time.time()}})
        context.checkpoint();service.check()
        if settings_check() is not True:return 'hold_sent_unknown'
        service.click_hit(hit)
        return 'pending_confirmation'
    finally:
        # Only prepared records can be removed; sent remains until an
        # independently verified post-equip observation reconciles it.
        try:
            doc=json.loads(path.read_text(encoding='utf8'))
            if doc.get('pending',{}).get('phase')=='prepared':_save(path,{'version':1,'pending':None,'last_result':'preinput_aborted'})
        except (OSError,ValueError,AttributeError):pass

def reconcile(service,context,identity,current_reader):
    """Current reader must independently identify the worn item twice."""
    if not isinstance(identity,str) or not identity.strip() or not callable(current_reader):return 'hold_identity'
    path=_intent_path(service.adapter.project.root,identity)
    try:doc=json.loads(path.read_text(encoding='utf8'));pending=doc.get('pending')
    except (OSError,ValueError,AttributeError):return 'hold_history'
    if not isinstance(pending,dict):return 'nothing_pending'
    observed=[]
    for _ in range(2):
        context.checkpoint();service.check();observed.append(current_reader(service.capture()));context.wait(.12)
    if observed[0]!=observed[1] or observed[0]!=pending.get('candidate'):return 'hold_result_unknown'
    _save(path,{'version':1,'pending':None,'last_result':'observed_equipped'})
    return 'observed_equipped'

def selected_filter(frame):
    """Return only a single visibly selected 1..5 filter."""
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    selected=[]
    for index,y in enumerate((78,110,141,173,204),1):
        hsv=cv2.cvtColor(frame[y-9:y+10,868:887],cv2.COLOR_RGB2HSV)
        gold=(hsv[:,:,0]>=5)&(hsv[:,:,0]<=30)&(hsv[:,:,1]>45)&(hsv[:,:,2]>70)
        if int(gold.sum())>=100:selected.append(index)
    return selected[0] if len(selected)==1 else None

def _single_detail_controls(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return None
    checks=((SINGLE_MARK,(421,115,443,137),.96),(SINGLE_REMOVE,(446,348,524,379),.96),
            (SINGLE_CLOSE,(499,96,521,117),.96))
    hits=[]
    for path,(x1,y1,x2,y2),threshold in checks:
        try:needle=np.asarray(Image.open(path).convert('RGB'))
        except OSError:return None
        area=frame[y1:y2,x1:x2]
        if area.shape[0]<needle.shape[0] or area.shape[1]<needle.shape[1]:return None
        _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED))
        if score<threshold:return None
        x,y=x1+pos[0],y1+pos[1];h,w=needle.shape[:2];hits.append((x+w//2,y+h//2,(x,y,x+w,y+h)))
    return hits[-1]

def read_worn_detail(root,frame):
    """Read worn tuple only on positively identified filtered detail."""
    from tools.ocr_support import get_paddle_engine
    category=selected_filter(frame)
    if category is None or _single_detail_controls(frame) is None:return None
    engine=get_paddle_engine(root,language='korean')
    def texts(box):
        x1,y1,x2,y2=box;crop=frame[y1:y2,x1:x2]
        if not crop.size:return []
        result=[]
        for page in engine.predict(cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_LINEAR)):
            result.extend((str(t),float(s)) for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',())))
        return result
    titles=[]
    for text,score in texts((376,94,512,120)):
        if score<.80:continue
        value=parse_title(text)
        if value:titles.append(value);continue
        # One observed font renders the numeric suffix as ']'.  The active
        # category and the uniquely E-marked selected row supply that digit.
        clean=re.sub(r'\s+','',text)
        match=re.fullmatch(r'(봉황|나비|도깨비|연꽃|토끼)가호장식\](?:\(귀속\))?',clean)
        if match:titles.append({'pattern':match.group(1),'slot':category})
    grades=[text.strip() for text,score in texts((381,125,430,146)) if score>=.90 and text.strip() in GRADES]
    if len(titles)!=1 or len(grades)!=1 or titles[0]['slot']!=category:return None
    return dict(titles[0],grade=grades[0],verified=True)

def _filtered_rows(service,frame,category):
    from project_adapter import achievement_rewards as reward,market_inventory as native
    if selected_filter(frame)!=category or not service.detector.find(reward.BLESSING_CHECK,frame,threshold=.95):return None
    return native.inspect_growth_equipment(service.detector,frame,reward_slots=True)

def _paired_rows(service,context,category):
    frames=[];rows=[];times=[]
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture();times.append(time.monotonic())
        evidence=_filtered_rows(service,frame,category)
        if evidence is None:return None
        frames.append(frame);rows.append(evidence);context.wait(.12)
    if not 0<times[1]-times[0]<=1.5 or time.monotonic()-times[1]>1.5:return None
    def summary(items):return [(r.get('index'),r.get('equipped'),r.get('equipped_state'),r.get('grade'),r.get('slot')) for r in items]
    if summary(rows[0])!=summary(rows[1]):return None
    return frames,rows[1],times[1]

def reconcile_filtered(service,context,identity,category):
    """Clear sent intent only after the same unique candidate has worn E twice."""
    path=_intent_path(service.adapter.project.root,identity)
    try:doc=json.loads(path.read_text(encoding='utf8'));pending=doc.get('pending')
    except (OSError,ValueError,AttributeError):return 'hold_history'
    if not isinstance(pending,dict):return 'nothing_pending'
    if pending.get('phase')=='prepared':
        _save(path,{'version':1,'pending':None,'last_result':'preinput_aborted'});return 'preinput_aborted'
    expected=pending.get('candidate') or {}
    if expected.get('slot')!=category or not pending.get('icon'):return 'hold_result_unknown'
    try:raw=base64.b64decode(pending['icon'],validate=True);icon=np.frombuffer(raw,dtype=np.uint8).reshape((18,18,3))
    except (ValueError,TypeError):return 'hold_result_unknown'
    pair=_paired_rows(service,context,category)
    if pair is None:return 'hold_result_unknown'
    frames,rows,_=pair;grade={'일반':'흰','희귀':'파랑','영웅':'보라'}.get(expected.get('grade'))
    if grade is None:return 'hold_result_unknown'
    found=[]
    for frame in frames:
        scored=[]
        for row in rows:
            s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8;cell=frame[y:y+18,x:x+18]
            if cell.shape!=(18,18,3):return 'hold_result_unknown'
            score=float(cv2.matchTemplate(cell,icon,cv2.TM_CCOEFF_NORMED)[0,0])
            if not np.isfinite(score):return 'hold_result_unknown'
            scored.append((score,row))
        if len(scored)<2:return 'hold_result_unknown'
        scored.sort(key=lambda item:item[0],reverse=True)
        score,row=scored[0]
        if score<.98 or score-scored[1][0]<.15 or row.get('equipped') is not True or row.get('equipped_state')!='장착' or row.get('grade')!=grade:return 'hold_result_unknown'
        found.append(row['index'])
    if found[0]!=found[1]:return 'hold_result_unknown'
    _save(path,{'version':1,'pending':None,'last_result':'observed_equipped'})
    return 'observed_equipped'

class BlessingNavigationError(RuntimeError):pass

def reconcile_worn_detail(service,context,identity,category,*,settings_check,reader=read_worn_detail):
    """Reconcile a sent equip by inspecting the uniquely worn item, without equipping."""
    path=_intent_path(service.adapter.project.root,identity)
    try:doc=json.loads(path.read_text(encoding='utf8'));pending=doc.get('pending')
    except (OSError,ValueError,AttributeError):return 'hold_history'
    if not isinstance(pending,dict):return 'nothing_pending'
    if pending.get('phase')=='prepared':
        _save(path,{'version':1,'pending':None,'last_result':'preinput_aborted'});return 'preinput_aborted'
    expected=pending.get('candidate') or {}
    if expected.get('slot')!=category or not callable(settings_check) or settings_check() is not True:return 'hold_settings'
    pair=_paired_rows(service,context,category)
    if pair is None:return 'hold_filter'
    frames,rows,stamp=pair
    worn=[row for row in rows if row.get('equipped') is True and row.get('equipped_state')=='장착']
    if len(worn)!=1:return 'hold_worn_row'
    row=worn[0];slot=row['slot'];x,y=slot['cell_x']+8,slot['cell_y']+8
    a=frames[0][y:y+18,x:x+18];b=frames[1][y:y+18,x:x+18]
    if a.shape!=(18,18,3) or b.shape!=a.shape or not np.array_equal(a,b):return 'hold_worn_row'
    from project_adapter import market_inventory as native
    cx,cy=native._click_xy(slot);left,top,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
    if not (left<=cx<left+w and top<=cy<top+h) or time.monotonic()-stamp>1.5:return 'hold_worn_row'
    context.checkpoint();service.check()
    if settings_check() is not True:return 'hold_settings'
    service.click_hit((cx,cy,(left,top,left+w,top+h)));context.wait(.25)
    images=[];stamps=[]
    for _ in range(2):
        context.checkpoint();service.check();frame=service.capture();stamps.append(time.monotonic())
        if selected_filter(frame)!=category or _single_detail_controls(frame) is None:
            raise BlessingNavigationError('가호 착용 상세를 확인하지 못해 다음 작업을 중지합니다')
        images.append(frame);context.wait(.12)
    if not 0<stamps[1]-stamps[0]<=1.5:raise BlessingNavigationError('가호 착용 상세 갱신 지연')
    observed=[reader(Path(service.adapter.project.root),frame) for frame in images]
    # The only available close action is the X on the independently verified
    # worn detail. Never use the nearby unequip button.
    context.checkpoint();service.check();frame=service.capture();close=_single_detail_controls(frame)
    if selected_filter(frame)!=category or close is None:
        raise BlessingNavigationError('가호 착용 상세 종료 위치 확인 필요')
    service.click_hit(close);context.wait(.2)
    after=_paired_rows(service,context,category)
    if after is None:raise BlessingNavigationError('가호 목록 복귀 확인 필요')
    after_frames,after_rows,_=after
    after_worn=[r for r in after_rows if r.get('equipped') is True and r.get('equipped_state')=='장착']
    if len(after_worn)!=1 or after_worn[0]['index']!=row['index']:return 'hold_result_unknown'
    for frame in after_frames:
        if not np.array_equal(frame[y:y+18,x:x+18],b):return 'hold_result_unknown'
    if observed!=[expected,expected] or settings_check() is not True:return 'hold_result_unknown'
    _save(path,{'version':1,'pending':None,'last_result':'observed_equipped'})
    return 'observed_equipped'

def scan_filtered(service,context,identity,category,order,*,settings_check,reader=read_compare):
    """On an already verified filter, inspect one unequipped candidate.

    Opens only its detail and delegates the one permitted equip action. Caller
    owns filter navigation and returning from a comparison panel. It must not
    continue other work while a comparison panel/result remains unverified.
    """
    if not isinstance(identity,str) or not identity.strip() or category not in range(1,6) or not callable(settings_check) or settings_check() is not True:return 'hold_settings'
    if _intent_path(service.adapter.project.root,identity).exists():
        status=reconcile_worn_detail(service,context,identity,category,settings_check=settings_check)
        if status not in ('nothing_pending','observed_equipped','preinput_aborted'):return status
    pair=_paired_rows(service,context,category)
    if pair is None:return 'hold_filter'
    frames,rows,stamp=pair
    rank={'흰':0,'파랑':1,'보라':2}
    candidates=[r for r in rows if r.get('equipped') is False and r.get('equipped_state')=='미장착' and r.get('grade') in rank]
    if not candidates:return 'no_candidate'
    candidates.sort(key=lambda r:(-rank[r['grade']],r['index']))
    previous=_scan_cursor.get((identity,category));i=next((j for j,r in enumerate(candidates) if r['index']==previous),-1)
    row=candidates[(i+1)%len(candidates)];s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8
    a=frames[0][y:y+18,x:x+18];b=frames[1][y:y+18,x:x+18]
    if a.shape!=(18,18,3) or b.shape!=(18,18,3):return 'hold_candidate'
    score=float(cv2.matchTemplate(a,b,cv2.TM_CCOEFF_NORMED)[0,0])
    if not np.isfinite(score) or score<.99 or float(np.abs(a.astype(np.float32)-b.astype(np.float32)).mean())>2:return 'hold_candidate'
    from project_adapter import market_inventory as native
    cx,cy=native._click_xy(s);left,top,w,h=(s[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
    if not (left<=cx<left+w and top<=cy<top+h) or time.monotonic()-stamp>1.5:return 'hold_candidate'
    context.checkpoint();service.check()
    if settings_check() is not True:return 'hold_settings'
    service.click_hit((cx,cy,(left,top,left+w,top+h)));context.wait(.25)
    _scan_cursor[(identity,category)]=row['index']
    def same_candidate(frame):
        if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
        center=frame[105:160,500:550];scores=[]
        for entry in rows:
            cell=entry['slot'];xx,yy=cell['cell_x']+5,cell['cell_y']+5;icon=frames[1][yy:yy+24,xx:xx+24]
            if icon.shape!=(24,24,3):return False
            value=float(cv2.minMaxLoc(cv2.matchTemplate(center,icon,cv2.TM_CCOEFF_NORMED))[1])
            if not np.isfinite(value):return False
            scores.append((value,entry['index']))
        scores.sort(reverse=True)
        return bool(len(scores)>1 and scores[0][1]==row['index'] and scores[0][0]>=.80 and scores[0][0]-scores[1][0]>=.20)
    return equip_selected(service,context,identity,order,settings_check=settings_check,reader=reader,candidate_icon=b,candidate_check=same_candidate,expected_category=category)
