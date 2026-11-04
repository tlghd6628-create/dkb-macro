"""Read-only: why were plain field frames called dimmed? Several HUD icons on each changed frame."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
import owner_movement as m,owner_image_scope as scope
D=Path(__file__).parent
A=bootstrap.A/'logs/scene-corpus'
data=json.loads((D/'scene_slots.json').read_text(encoding='utf-8'))['changed']
def row(f):
    out={}
    n=m.asset('settings-hud');x,y,w,h=758,440,26,30;p=scope.peaks(f,n,scope._clip(x-6,y-6,w+12,h+12),count=1)[0];l,t=p[1:];q=f[t:t+h,l:l+w];white=n.min(axis=2)>170
    out['set']=(round(p[0],3),l-x,t-y,round(float(q[white].mean())/float(n[white].mean()),3),round(float(q[~white].mean()),1))
    hp=f[411:423,394:502].astype('float32');out['hp']=int(((hp[:,:,1]>90)&(hp[:,:,1]>hp[:,:,0]*1.2)&(hp[:,:,1]>hp[:,:,2]*1.15)).sum())
    out['hpmax']=round(float(hp[:,:,1].max()),0)
    out['skill']=round(float(f[345:425,660:890].mean()),1);out['top']=round(float(f[2:34,650:890].mean()),1)
    return out
for key in('pre|field|unknown','post|field|unknown'):
    for name in data[key]:
        f=np.asarray(Image.open(A/name[:8]/name/'screen.png').convert('RGB'));print(name[4:15],row(f))
c=A/'20261104'
for pat in('20261104T104142-*','20261104T104208-*','20261104T105416-*'):
    q=next(c.glob(pat));f=np.asarray(Image.open(q/'screen.png').convert('RGB'));print('plainnew',q.name[9:15],row(f))
import os;sys.stdout.flush();os._exit(0)
