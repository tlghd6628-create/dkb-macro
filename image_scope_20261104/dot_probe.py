"""Read-only: red blobs in the event body on real frames: is a true notification dot separable from red art?"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
D=Path(__file__).parent/'live';C=bootstrap.A/'logs/scene-corpus/20261104'
def blobs(f,box=(305,204,420,182)):
    x,y,w,h=box;p=f[y:y+h,x:x+w].astype('int16');r,g,b=p[:,:,0],p[:,:,1],p[:,:,2]
    m=((r>170)&(g<95)&(b<95)).astype('uint8')
    n,l,s,_=cv2.connectedComponentsWithStats(m,8);out=[]
    for i in range(1,n):
        a=int(s[i,4])
        if a>=4:out.append((int(s[i,0])+x,int(s[i,1])+y,int(s[i,2]),int(s[i,3]),a))
    return sorted(out,key=lambda v:-v[4])[:10]
for p in [D/('p%02d.png'%i) for i in range(1,8)]:
    print(p.stem,blobs(np.asarray(Image.open(p).convert('RGB'))))
for q in sorted(x for x in C.iterdir() if x.is_dir() and '20261104T104013'<=x.name<='20261104T104054'):
    print(q.name[9:15],blobs(np.asarray(Image.open(q/'screen.png').convert('RGB'))))
import os;sys.stdout.flush();os._exit(0)
