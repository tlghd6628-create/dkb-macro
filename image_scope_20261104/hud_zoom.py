"""Read-only: plain post-update field frame HUD against the owner's HUD assets."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
import owner_movement as m
D=Path(__file__).resolve().parent
c=bootstrap.A/'logs/scene-corpus/20261104'
f=np.asarray(Image.open(c/'20261104T104142-'.__str__() if False else next(c.glob('20261104T104142-*'))/'screen.png').convert('RGB'))
b=f[425:479,640:897];top=f[0:40,640:897]
home=m.asset('home-hud');sett=m.asset('settings-hud')
Image.fromarray(np.vstack([b,top])).resize((b.shape[1]*3,(b.shape[0]+40)*3),Image.NEAREST).save(D/'post_plain_hud_3x.png')
for name,box,n in (('home',(662,441,25,29),home),('settings',(758,440,26,30),sett)):
    x,y,w,h=box;p=f[y:y+h,x:x+w];white=n.min(axis=2)>170
    print(name,'asset ink px',int(white.sum()),'patch ink>150 share',round(float((p.min(axis=2)[white]>150).mean()),3),'mean abs',round(float(np.abs(p.astype('float32')-n.astype('float32'))[white].mean()),1),'patch ink mean',round(float(p[white].mean()),1),'asset ink mean',round(float(n[white].mean()),1))
    r=cv2.matchTemplate(f[400:479,600:897],n,cv2.TM_CCOEFF_NORMED);_,s,_,q=cv2.minMaxLoc(r);print(' best ccoeff',round(float(s),4),'at',q[0]+600,q[1]+400,'vs',x,y)
hp=f[411:423,394:502].astype('float32');rr,g,bb=hp[:,:,0],hp[:,:,1],hp[:,:,2];print('hp green px',int(((g>90)&(g>rr*1.20)&(g>bb*1.15)).sum()))
print('mean frame',round(float(f.mean()),1))
import os;sys.stdout.flush();os._exit(0)
