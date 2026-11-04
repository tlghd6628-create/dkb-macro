"""Read-only: does equal soft blur absorb the update's text rendering change without closing the gap to neighbours?"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from roi_runtime import RoiDetector
import owner_movement as m
D=Path(__file__).resolve().parent
frames={'modal_new':np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png').convert('RGB')),
 'map_new':np.asarray(Image.open(D/'map_frame_897x479.png').convert('RGB')),'modal_old':np.asarray(Image.open(D/'modal_old.png').convert('RGB'))}
names=['버튼_축지술_가운데','버튼_지도_축지술','버튼_보스_축지술']
d=RoiDetector(bootstrap.A/'profiles/DKB',names)
def peaks(hay,needle,n=2):
    r=cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED);r=np.where(np.isfinite(r),r,-1).copy();out=[];hh,ww=needle.shape[:2]
    for _ in range(n):
        _,s,_,p=cv2.minMaxLoc(r);out.append((round(float(s),3),p[0],p[1]));r[max(0,p[1]-hh//2):p[1]+hh//2+1,max(0,p[0]-ww//2):p[0]+ww//2+1]=-1
    return out
def soft(a,s):return cv2.GaussianBlur(a,(0,0),s) if s else a
for fn,f in frames.items():
    print('==',fn)
    for n,t in [(k,d.templates[k][:,:,::-1].copy()) for k in names]+[(a,m.asset(a)) for a in('move-method-title','teleport-b-button')]:
        row={}
        for s in(0,.6,.8,1.0,1.4):row[s]=peaks(soft(f,s),soft(t,s))
        print(' ',n,row)
        rs={}
        for sc in(.9,.95,1.05,1.1):
            tt=cv2.resize(t,None,fx=sc,fy=sc,interpolation=cv2.INTER_AREA if sc<1 else cv2.INTER_CUBIC)
            rs[sc]=peaks(f,tt,1)
        print('    scale',rs)
import os;sys.stdout.flush();os._exit(0)
