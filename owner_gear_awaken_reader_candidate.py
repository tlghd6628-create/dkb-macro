"""Read validated generic stage glyphs and explicit numeric growth lines.

A stage result proves neither the selected item nor sufficient materials.
Those are independently paired by the runtime. Unrecognized symbolic stages
remain unknown instead of being assigned a numerical zero.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import re,math

_ASSETS=Path(__file__).with_name('owner_gear_assets_candidate')
# Game frame coordinates; saved window fixtures were cropped by (1,31).
_BOX=(354,129,431,143)


def asset_score(frame,name,box):
    try:ref=np.asarray(Image.open(_ASSETS/(name+'.png')).convert('RGB'))
    except (OSError,ValueError):return -1.
    l,t,r,b=box;patch=frame[t:b,l:r]
    if patch.shape!=ref.shape:return -1.
    return float(cv2.matchTemplate(patch,ref,cv2.TM_CCOEFF_NORMED)[0,0])

REAL_LINE=(535,205,130,26);REAL_ARROW=597  # real pixels of the 각성 >>> 각성 line, and where its arrow's middle stands

def real_transition(real):
    """각성 >>> 각성 with the blue diamond on the next stage only: a plain item about to take its first awakening."""
    from owner_text import clean,read_area
    x,y,w,h=REAL_LINE;part=np.asarray(real)[y:y+h,x:x+w]
    if ''.join(clean(row['text']) for row in read_area(None,part,scale=3,minimum=.5)).count('각성')!=2:return None
    signed=part.astype(np.int16)
    blue=(signed[:,:,2]-signed[:,:,0]>60)&(signed[:,:,2]>150)
    arrow=REAL_ARROW-x
    if int(blue[:,:arrow].sum())>2 or int(blue[:,arrow:].sum())<8:return None
    return {'current':None,'next':None,'kind':'observed_awakening_line','score':1.}

REAL_NOTICE=(480,612,420,40)  # real pixels of the line under the panel

def real_maximum(real):
    """최대 각성 단계를 달성했습니다, seen the first time a real item reached it (11-05)."""
    from owner_text import clean,read_area
    x,y,w,h=REAL_NOTICE
    if not any('최대각성단계' in clean(row['text']) for row in read_area(None,np.asarray(real)[y:y+h,x:x+w],minimum=.7)):return None
    return {'current':1,'next':1,'maximum':True,'kind':'validated_single_awakening_maximum','score':1.}

def read_observed_transition(frame):
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
    if getattr(frame,'hi',None) is not None:return real_transition(frame.hi)
    x1,y1,x2,y2=_BOX;patch=frame[y1:y2,x1:x2]
    if patch.shape!=(14,77,3):return None
    scores=[]
    for name in ('awaken_zero_gear.png','awaken_zero_blessing.png'):
        try:reference=np.asarray(Image.open(_ASSETS/name).convert('RGB'))
        except (OSError,ValueError):return None
        if reference.shape!=patch.shape:return None
        # The next-stage diamond on the right sparkles: the whole line read .951 to .984
        # on real screens. The current stage and arrow on the left hold still, and a
        # higher current stage changes them. Threshold unchanged.
        score=max(float(cv2.matchTemplate(patch,reference,cv2.TM_CCOEFF_NORMED)[0,0]),
                  float(cv2.matchTemplate(patch[:,:44],reference[:,:44],cv2.TM_CCOEFF_NORMED)[0,0]))
        if np.isfinite(score):scores.append(score)
    if not scores or max(scores)<.965:return None
    return {'current':None,'next':None,'kind':'observed_awakening_line','score':max(scores)}

def read_zero_to_one(frame):
    #2026-11-02: the SAME leather glove was observed before, with one
    # duplicate selected, and after one awakening at the explicit maximum.
    # This validates the native base→single-blue-diamond transition as0→1.
    # It is not the maximum screen itself and does not authorize input alone.
    observed=read_observed_transition(frame)
    if observed is None:return None
    return dict(observed,current=0,next=1,kind='validated_base_to_single_awakening')

def paired_zero_to_one(first,second):
    a,b=read_zero_to_one(first),read_zero_to_one(second)
    if not a or not b:return None
    return {'current':0,'next':1,'kind':'paired_zero_to_one_line',
            'scores':(a['score'],b['score'])}


def parse_explicit_stage(rows,kind):
    """Parse an explicit numeric current→next line, never infer a zero.

    `각성→각성+` has no numeric stage and deliberately remains unknown. Both
    numbers must be on the same labelled OCR line; material ratios and item
    enhancement badges cannot accidentally become a stage counter.
    """
    label={'awaken':'각성','breakthrough':'돌파'}.get(kind)
    if label is None:return None
    answers=[]
    for row in rows or ():
        if (not isinstance(row,dict) or type(row.get('score')) not in (int,float)
            or not math.isfinite(row['score']) or not .95<=row['score']<=1):continue
        text=re.sub(r'\s+','',str(row.get('text','')))
        # OCR commonly renders the double-chevron as >, >>, or the arrow.
        patterns=(rf'{label}\+?([0-9]{{1,3}})(?:단계|회)?(?:→|⇒|>|≫|>>|>>>|\*|☆|★)*{label}\+?([0-9]{{1,3}})(?:단계|회)?',
                  rf'([0-9]{{1,3}}){label}(?:→|⇒|>|≫|>>|>>>)+([0-9]{{1,3}}){label}')
        match=next((m for pattern in patterns if (m:=re.fullmatch(pattern,text))),None)
        if not match:continue
        current,following=map(int,match.groups())
        if following!=current+1:continue
        answers.append((current,following))
    if len(answers)!=1:return None
    current,following=answers[0]
    return {'current':current,'next':following,'kind':'explicit_numeric_'+kind}


def read_explicit_stage(root,frame,kind):
    """Read the central labelled stage line. No input and no guessed count."""
    if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
    if kind=='awaken':
        base=read_zero_to_one(frame)
        if base is not None:return base
        real=getattr(frame,'hi',None)
        if real is not None:return real_maximum(real)
        scores=[]
        for suffix in ('after1','after2'):
            values=[]
            for prefix,box in (('awaken_max_line_',_BOX),('awaken_max_notice_',(332,385,458,403))):
                try:ref=np.asarray(Image.open(_ASSETS/(prefix+suffix+'.png')).convert('RGB'))
                except (OSError,ValueError):return None
                l,t,r,b=box;patch=frame[t:b,l:r]
                if patch.shape!=ref.shape:return None
                values.append(float(cv2.matchTemplate(patch,ref,cv2.TM_CCOEFF_NORMED)[0,0]))
            scores.append(min(values))
        if scores and max(scores)>=.965:
            return {'current':1,'next':1,'maximum':True,'kind':'validated_single_awakening_maximum','score':max(scores)}
    if kind=='breakthrough':
        score=max(asset_score(frame,'break_two_to_three'+suffix,(326,129,469,144)) for suffix in ('1','2'))
        if score>=.965:return {'current':2,'next':3,'kind':'observed_numeric_two_to_three','score':score}
        if (asset_score(frame,'break_three_max_line',_BOX)>=.965
            and asset_score(frame,'break_max_notice',(332,385,458,403))>=.965):
            return {'current':3,'next':3,'maximum':True,'kind':'observed_numeric_three_maximum'}
    from tools.ocr_support import get_paddle_engine
    crop=frame[120:149,312:476]
    image=cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
    rows=[]
    for page in get_paddle_engine(root,language='korean').predict(image):
        rows.extend({'text':str(text),'score':float(score)} for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())))
    if len(rows)>1 and all(r['score']>=.95 for r in rows):
        # The crop contains one stage line only. Both explicit labelled
        # numbers remain required when OCR splits the chevron into parts.
        rows.append({'text':''.join(r['text'] for r in rows),'score':min(r['score'] for r in rows)})
    result=parse_explicit_stage(rows,kind)
    if result is None and kind=='breakthrough' and asset_score(frame,'break_max_notice',(332,385,458,403))>=.965:
        candidates=[]
        for row in rows:
            text=re.sub(r'[\s☆★*]','',row['text'])
            found=re.fullmatch(r'돌파([0-9]{1,3})단계',text)
            if found and row['score']>=.95:candidates.append(int(found[1]))
        if len(candidates)==1:result={'current':candidates[0],'next':candidates[0],'maximum':True,'kind':'explicit_breakthrough_maximum'}
    if result is not None:result['proof_box']=(312,120,164,29)
    return result


FAILURE_NOTICE_BOX=(340,180,560,215)


def read_failure_overlay(root,frame):
    """A breakthrough result window that states failure in text.

    The exact wording and layout are not yet confirmed by a saved screen, so
    every condition must hold: the observed result window's own close button,
    and exactly one confident notice line naming both 돌파 and 실패. Anything
    else stays a result-unknown hold, which never allows another input.
    """
    if max(asset_score(frame,'break_result_close'+suffix,(421,446,474,460)) for suffix in ('1','2'))<.965:return None
    from tools.ocr_support import get_paddle_engine
    l,t,r,b=FAILURE_NOTICE_BOX
    crop=cv2.resize(frame[t:b,l:r],None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC);found=[]
    for page in get_paddle_engine(root,language='korean').predict(crop):
        for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
            value=re.sub(r'\s+','',str(text))
            if '돌파' in value and '실패' in value and .95<=float(score)<=1:found.append(value)
    return {'overlay_failure':True,'kind':'observed_breakthrough_failure'} if len(found)==1 else None


def read_success_overlay(root,frame):
    """The observed breakthrough-success view; numerical stage stays explicit."""
    notice=max(asset_score(frame,'break_success_notice'+suffix,(386,189,511,207)) for suffix in ('1','2'))
    close=max(asset_score(frame,'break_result_close'+suffix,(421,446,474,460)) for suffix in ('1','2'))
    if notice<.965 or close<.965:return None
    if max(asset_score(frame,'break_success_stage_three'+suffix,(411,255,488,278)) for suffix in ('1','2'))>=.965:
        return {'current':3,'next':3,'overlay_success':True,'kind':'observed_numeric_breakthrough_success_three'}
    from tools.ocr_support import get_paddle_engine
    crop=cv2.resize(frame[255:278,411:488],None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC);values=[]
    for page in get_paddle_engine(root,language='korean').predict(crop):
        for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
            found=re.fullmatch(r'돌파([0-9]{1,3})단계',re.sub(r'[\s☆★*]','',str(text)))
            if found and .95<=float(score)<=1:values.append(int(found[1]))
    return {'current':values[0],'next':values[0],'overlay_success':True} if len(values)==1 else None
