"""Corrections grounded in saved game frames; no OCR or extra input thread."""
from functools import lru_cache,wraps
from pathlib import Path
import logging,time
LOG=logging.getLogger('project_gui.DKB')
ACQUIRED='체크_보물찾기_아이템획득'

@lru_cache(maxsize=8)
def asset(name):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets'/name).convert('RGB'))

def score(frame,name,x,y):
    import cv2,numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return 0.
    needle=asset(name);h,w=needle.shape[:2];patch=frame[y:y+h,x:x+w]
    if patch.shape!=needle.shape:return 0.
    value=float(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)[0,0])
    return value if np.isfinite(value) else 0.

def sleeping_hunt(frame):
    import numpy as np
    return (score(frame,'sleep-guide-r12.png',333,76)>=.98 and
            score(frame,'sleep-combat-r12.png',415,329)>=.97 and
            float((np.max(frame,axis=2)<24).mean())>.75)

def spirit_detail(frame):
    return (score(frame,'spirit-detail-title-r12.png',421,86)>=.97 and
            score(frame,'spirit-detail-close-r12.png',554,87)>=.97)

def mole_loot(frame,region=None,threshold=.97):
    """The specifically observed mole-album toast, not arbitrary loot text."""
    import cv2,numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return None
    needle=asset('treasure-mole-toast-r12.png');h,w=needle.shape[:2]
    x,y,right,bottom=450,160,790,335
    if region is not None:
        rx,ry,rw,rh=region;x=max(x,rx);y=max(y,ry);right=min(right,rx+rw);bottom=min(bottom,ry+rh)
    hay=frame[y:bottom,x:right]
    if hay.shape[0]<h or hay.shape[1]<w:return None
    scores=cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED)
    scores=np.where(np.isfinite(scores),scores,-1.)
    _,value,_,point=cv2.minMaxLoc(scores)
    if value<max(.97,threshold):return None
    # Two separate matching toasts are ambiguous; overlapping offsets belong
    # to the same current item, not two independent targets.
    px,py=point;other=scores.copy()
    other[max(0,py-h+1):py+h,max(0,px-w+1):px+w]=-1
    if float(other.max(initial=-1))>=max(.97,threshold):return None
    l,t=x+px,y+py
    return (l+w//2,t+h//2,(l,t,l+w,t+h))

def normalize_spirit(service,context,scene):
    """Close the observed detail X, then native Back, on the owning worker.

    Never presses Train or the premium instant-completion button. Three fresh
    observations precede X; a different dialog is left untouched.
    """
    first=service.capture()
    if not spirit_detail(first):return False
    context.wait(.15);context.checkpoint()
    if not spirit_detail(service.capture()):raise RuntimeError('영기 수련 상세창이 변경되어 닫기를 보류합니다.')
    context.checkpoint()
    if not spirit_detail(service.capture()):raise RuntimeError('영기 수련 상세창 닫기 직전 화면 변경')
    service.click_hit((562,95,(556,89,570,103)))
    deadline=time.monotonic()+5
    while True:
        context.checkpoint();frame=service.capture()
        if not spirit_detail(frame):break
        if time.monotonic()>=deadline:raise RuntimeError('영기 수련 상세창 X 닫힘 미확인')
        context.wait(.1)
    # Root screen remains the same known training UI; only native Back is
    # allowed. No learned coordinate is reused on another screen.
    if scene(service.detector,frame)=='spirit_dialog':
        if not service.button('버튼_나가기',wait_before_click=.2,required=False):
            raise RuntimeError('영기 수련 상세창을 닫았지만 뒤로가기 버튼 미확인')
    else:
        if scene(service.detector,frame) not in ('field','inventory'):
            raise RuntimeError('영기 수련 상세창 종료 후 화면 미확인')
    deadline=time.monotonic()+5;normal=0
    while normal<2:
        context.checkpoint();frame=service.capture()
        normal=normal+1 if scene(service.detector,frame) in ('field','inventory') else 0
        if time.monotonic()>=deadline:raise RuntimeError('영기 수련창 종료 후 일반 화면 복귀 미확인')
        if normal<2:context.wait(.1)
    LOG.info('영기 수련 재개 보완 · 기존 상세 X 닫기 · 새 수련·즉시완료 입력 없음')
    return True

def install(gui):
    if getattr(gui,'_owner_diagnostic_repairs',False):return
    from roi_runtime import RoiDetector
    from owner_special_contexts import continue_special as ordinary_special
    import owner_special_contexts as special
    if not getattr(RoiDetector.find,'_owner_mole_receipt',False):
        ordinary=RoiDetector.find
        @wraps(ordinary)
        def find(detector,name,frame,region=None,threshold=.9,*,candidate_filter=None):
            hit=ordinary(detector,name,frame,region,threshold,candidate_filter=candidate_filter)
            if hit is not None or name!=ACQUIRED:return hit
            bounds=None
            if region:
                r=detector.entries[region];bounds=tuple(r[k] for k in ('x','y','w','h'))
            hit=mole_loot(frame,bounds,threshold)
            if hit is not None and (candidate_filter is None or candidate_filter(frame,hit)):
                return hit
            return None
        find._owner_mole_receipt=True;RoiDetector.find=find
    @wraps(ordinary_special)
    def continued(g,a,c,i,s,kind,publish,scene,recheck):
        if kind=='spirit_dialog' and normalize_spirit(s,c,scene):raise recheck()
        return ordinary_special(g,a,c,i,s,kind,publish,scene,recheck)
    special.continue_special=continued
    gui._owner_diagnostic_repairs=True
    LOG.info('진단 보완 준비 · 실제 보물 수령 토스트 · 영기 수련 상세창 정상화 · 기존 입력 검증 유지')
