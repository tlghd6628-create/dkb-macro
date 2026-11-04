"""Read-only: real dot crops against every small red blob on real frames."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
D=Path(__file__).parent/'live';C=bootstrap.A/'logs/scene-corpus/20261104'
def load(n):return np.asarray(Image.open(D/(n+'.png')).convert('RGB'))
def blobs(f,box=(305,204,420,182)):
    x,y,w,h=box;p=f[y:y+h,x:x+w].astype('int16');r,g,b=p[:,:,0],p[:,:,1],p[:,:,2]
    m=((r>170)&(g<95)&(b<95)).astype('uint8');n,l,s,_=cv2.connectedComponentsWithStats(m,8)
    return [(int(s[i,0])+x,int(s[i,1])+y,int(s[i,2]),int(s[i,3]),int(s[i,4])) for i in range(1,n) if s[i,4]>=4]
def crop(f,b,pad=3):
    cx,cy=b[0]+b[2]//2,b[1]+b[3]//2;return f[cy-5:cy+6,cx-5:cx+6]
refs={'p03':crop(load('p03'),(580,257,6,6)),'p05':crop(load('p05'),(590,328,5,6)),'p06':crop(load('p06'),(590,224,6,6))}
tile=np.hstack([cv2.resize(v,(99,99),interpolation=cv2.INTER_NEAREST) for v in refs.values()]);Image.fromarray(tile).save(Path(__file__).parent/'dots_9x.png')
for k,v in refs.items():print(k,v[5,5],v[3,5],v[0,0],v[0,10])
frames=[(p.stem,load(p.stem)) for p in sorted(D.glob('p0*.png'))]+[('c'+q.name[9:15],np.asarray(Image.open(q/'screen.png').convert('RGB'))) for q in sorted(x for x in C.iterdir() if x.is_dir() and '20261104T104013'<=x.name<='20261104T104054')][::3]
for name,f in frames:
    row=[]
    for b in blobs(f):
        c=crop(f,b)
        if c.shape!=(11,11,3):continue
        s=max(float(cv2.matchTemplate(c,v,cv2.TM_CCOEFF_NORMED)[0,0]) for v in refs.values())
        row.append((b[0],b[1],b[2],b[3],b[4],round(s,2)))
    print(name,sorted(row,key=lambda v:-v[5])[:6])
import os;sys.stdout.flush();os._exit(0)
