"""Native material classifier with an exact-ratio fallback for unread text.

This is one-frame classification only, never action permission. Callers keep
their selected-item, paired-frame, resource-button and final-input guards.
Native sufficient/shortage results are preserved; no threshold is lowered.
"""
import re

def ratios(pages,threshold):
    found=[];integer=r'(?:\d{1,3}(?:,\d{3})+|\d+)'
    for page in pages:
        for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
            value=re.sub(r'\s+','',str(text))
            match=re.fullmatch('('+integer+')/('+integer+')',value)
            if match and float(score)>=threshold:
                a,b=(int(part.replace(',','')) for part in match.groups())
                if 0<=a<=10**9 and 0<b<=10**9:found.append((a,b))
    return found

def material_ink(frame,box):
    """Locate white/red glyph bounds, retain antialiasing in a gray ROI."""
    import cv2,numpy as np
    x,y,w,h=box;crop=frame[y:y+h,x:x+w]
    white=(crop.min(axis=2)>160)&((crop.max(axis=2).astype(int)-crop.min(axis=2))<70)
    red=(crop[:,:,0]>130)&(crop[:,:,0].astype(float)>crop[:,:,1]*1.4)&(crop[:,:,0].astype(float)>crop[:,:,2]*1.4)
    ink=white|red
    if int(ink.sum())<8 or float(ink.mean())>.40:return None
    # A hard binary3 loses antialiased strokes in actual837/2 (.937).
    # Bound only the text horizontally, then preserve its gray edges. The
    # bounds come from this frame, never from a count/digit/item template.
    ys,xs=np.nonzero(ink);left=max(0,int(xs.min())-2);right=min(w,int(xs.max())+4)
    strength=np.where(red,crop[:,:,0],crop.min(axis=2))
    gray=np.clip((strength.astype(float)-80)*255/175,0,255).astype('uint8')[:,left:right]
    mono=np.repeat(gray[:,:,None],3,axis=2)
    image=cv2.resize(mono,None,fx=8,fy=8,interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(image,12,12,12,12,cv2.BORDER_CONSTANT,value=(0,0,0))

def inspect_materials(native,detector,frame,root):
    result=native.inspect_growth_materials(detector,frame)
    if not isinstance(result,dict):return result
    if result.get('status') in ('재료 충분','재료 부족'):return result
    if getattr(frame,'shape',None)!=(479,897,3):return result
    entry=detector.entries.get('범위_성장_장비_재료수량',{})
    box=tuple(entry.get(k) for k in ('x','y','w','h'))
    if (entry.get('type')!='rect' or not all(type(v) is int for v in box)
        or min(box[2:])<=0 or not 0<=box[0]<box[0]+box[2]<=897
        or not 0<=box[1]<box[1]+box[3]<=479):return result
    if not detector.find('체크_성장',frame,threshold=.95):return result
    from tools.ocr_support import get_paddle_engine
    from owner_progression import resized
    try:
        engine=get_paddle_engine(root,language='number')
        pages=list(engine.predict(resized(frame,box)))
    except Exception:return result
    found=ratios(pages,.98);source='native_region_exact_ratio'
    if not found:
        # The actual793/2 pair reads ~.90 on translucent brown, .997 on
        # isolated glyphs. Require agreement with exactly one raw ratio AND
        # one >=.98 normalized ratio. Never promote raw confidence alone.
        raw=ratios(pages,.85)
        if len(raw)!=1:return result
        ink=material_ink(frame,box)
        if ink is None:return result
        try:clean=ratios(list(engine.predict(ink)),.98)
        except Exception:return result
        if clean!=raw:return result
        found=clean;source='native_region_exact_ratio_ink_agreement'
    if len(found)!=1:return result
    current,required=found[0]
    return {'status':'재료 충분' if current>=required else '재료 부족',
            'current':current,'required':required,'reason':'원본 재료 영역의 명시된 수량/필요량 OCR',
            'source':source}
