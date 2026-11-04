"""Read-only: the real move-method modal, where its pieces are, and every peak for the button text."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from roi_runtime import RoiDetector
import owner_movement as m
frame=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png').convert('RGB'))
d=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_축지술_가운데','버튼_지도_축지술','버튼_보스_축지술'])
def peaks(hay,needle,n=6,box=None):
    x,y,w,h=box or (0,0,hay.shape[1],hay.shape[0]);part=hay[y:y+h,x:x+w]
    r=cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED);r=np.where(np.isfinite(r),r,-1).copy();out=[];hh,ww=needle.shape[:2]
    for _ in range(n):
        _,s,_,p=cv2.minMaxLoc(r);out.append((round(float(s),4),p[0]+x,p[1]+y))
        l,t=max(0,p[0]-ww//2),max(0,p[1]-hh//2);r[t:p[1]+hh//2+1,l:p[0]+ww//2+1]=-1
    return out
print('choice()',m.choice(frame),'moving_bar',bool(m.moving_bar(frame)),'field_hud',m.field_hud(frame))
for name in ('move-method-title','teleport-b-button'):
    n=m.asset(name);print(name,n.shape,'peaks(rgb,all)',peaks(frame,n,4))
    x=np.asarray(Image.open(Path(m.__file__).parent/'assets/movement'/(name+'.png')).convert('RGB'))
    Image.fromarray(x).resize((x.shape[1]*5,x.shape[0]*5),Image.NEAREST).save(Path(__file__).parent/(name+'_5x.png'))
n=d.templates['버튼_축지술_가운데']
print('native peaks',peaks(frame[:,:,::-1].copy(),n,6))
print('map/boss peaks',peaks(frame[:,:,::-1].copy(),d.templates['버튼_지도_축지술'],3),peaks(frame[:,:,::-1].copy(),d.templates['버튼_보스_축지술'],3))
Image.fromarray(frame).save(Path(__file__).parent/'failure_frame.png')
Image.fromarray(frame[130:340,300:600]).resize((900,630),Image.NEAREST).save(Path(__file__).parent/'failure_modal_3x.png')
import os;sys.stdout.flush();os._exit(0)
