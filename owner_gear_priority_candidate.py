"""Paired worn-slot icon matching for priority, without inputs or persistence.

Caller must first independently verify that both supplied frames show the
same character's equipment inventory. Unclear/duplicate icons return None.
"""
import cv2
import numpy as np
from owner_equipment_boxes import SLOTS

PRIORITY=('무기','팔찌','반지')

def _scores(source,frame,rows,part):
    if not isinstance(source,np.ndarray) or not isinstance(frame,np.ndarray) or source.shape!=(479,897,3) or frame.shape!=(479,897,3):return []
    x,y,w,h=SLOTS[part];needle=source[y+3:y+h-4,x+3:x+w-4]
    if needle.size==0:return []
    out=[]
    for row in rows:
        s=row.get('slot') or {};x=s.get('cell_x',-100);y=s.get('cell_y',-100)
        cell=frame[y:y+34,x:x+34]
        if cell.shape!=(34,34,3):return []
        best=-1.
        for factor in (.8,1.,1.2):
            size=(max(4,int(needle.shape[1]*factor)),max(4,int(needle.shape[0]*factor)))
            pattern=cv2.resize(needle,size,interpolation=cv2.INTER_AREA)
            score=float(cv2.minMaxLoc(cv2.matchTemplate(cell,pattern,cv2.TM_CCOEFF_NORMED))[1])
            if np.isfinite(score):best=max(best,score)
        out.append((best,row.get('index')))
    return sorted(out,reverse=True)

def priority_indices(inventory_pair,growth_pair,rows,verified_worn):
    if not isinstance(inventory_pair,(tuple,list)) or len(inventory_pair)!=2:return {}
    if not isinstance(growth_pair,(tuple,list)) or len(growth_pair)!=2:return {}
    if not isinstance(verified_worn,dict):return {}
    result={}
    for part in PRIORITY:
        if verified_worn.get(part) is not True:continue
        matches=[]
        for source in inventory_pair:
            for frame in growth_pair:
                ranked=_scores(source,frame,rows,part)
                if len(ranked)<2 or ranked[0][0]<.67 or ranked[0][0]-ranked[1][0]<.07:
                    matches=[];break
                matches.append(ranked[0][1])
            if not matches:break
        if len(matches)==4 and len(set(matches))==1 and type(matches[0]) is int:result[part]=matches[0]
    # A single grid item must never identify two body parts.
    for part,index in list(result.items()):
        if sum(i==index for i in result.values())>1:result.pop(part,None)
    return result
