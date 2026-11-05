"""Recognize the observed available-story label only in the quest tracker.

Existing handlers and input guards execute the click and accept workflow.
No separate input worker, whole-screen search, or lowered threshold is added.
"""
from functools import wraps
from pathlib import Path
import time

NAME='버튼_개발용_서사수락가능'
RANGE='범위_개발용_서사목록'

def match_available(slots,frame,clock=time.monotonic):
    import cv2
    from PIL import Image
    import numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return None
    d=slots.detector
    if NAME not in d.templates:
        assets=Path(__file__).resolve().parent/'assets'
        needle=np.asarray(Image.open(assets/'story_quest_available.png').convert('RGB'))[:,:,::-1].copy()
        mask=np.asarray(Image.open(assets/'story_quest_available_mask.png').convert('L')).copy()
        h,w=mask.shape
        d.templates[NAME]=needle;d.masks[NAME]=mask
        d.entries[NAME]={'type':'template','x':732,'y':100,'w':w,'h':h,'capture_size':[897,479],'target':'game'}
        d.entries[RANGE]={'type':'range','x':730,'y':88,'w':125,'h':150,'capture_size':[897,479],'target':'game'}
    spec=dict(slots.by_key['progress'],roi=NAME,range=RANGE,require_mask=True,threshold=.95)
    result=slots.match_roi(NAME,frame,spec)
    hit=result.get('hit')
    if not hit:
        slots._owner_story_seen=None
        return None
    now=clock();point=tuple(hit[:2]);seen=getattr(slots,'_owner_story_seen',None)
    if not seen or max(abs(a-b) for a,b in zip(point,seen['point']))>1 or now-seen['last']>2:
        slots._owner_story_seen={'point':point,'first':now,'last':now}
        return None
    seen['last']=now
    if now-seen['first']<.15:return None
    # Native progress stability compares an icon-sized patch against the
    # original icon mask. Prove the full label above, then preserve that
    # native patch contract and original ROI identity for guarded clicking.
    left,top,_,_=hit[2]
    original_name=slots.names['progress'];entry=d.entries[original_name]
    x,y=left+1,top+1;w,h=entry['w'],entry['h']
    return dict(result,name=original_name,
                hit=(x+w//2,y+h//2,(x,y,x+w,y+h)),
                owner_story_available=True)

def install(gui):
    from project_adapter.main_quest import StateROIs
    if getattr(StateROIs.match,'_owner_story_tracker',False):return
    ordinary=StateROIs.match
    @wraps(ordinary)
    def match(slots,key,frame,*,threshold_override=None):
        result=ordinary(slots,key,frame,threshold_override=threshold_override)
        if key!='progress' or slots.mode!='sub_quest' or result.get('hit'):return result
        # A diagnostic lower-threshold request must retain its original result.
        if threshold_override is not None:return result
        return match_available(slots,frame) or result
    match._owner_story_tracker=True;StateROIs.match=match
    gui._owner_quest_tracker=True
