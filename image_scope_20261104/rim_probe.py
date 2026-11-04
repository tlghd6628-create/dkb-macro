"""Read-only: original gold-rim candidates on saved event frames, with how gold the inside is."""
from pathlib import Path
import sys,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import project_adapter.event_rewards as ev
g=ev.EventGlowDetector(RoiDetector(bootstrap.A/'profiles/DKB',list(ev.NAMES)))
A=bootstrap.A/'logs/scene-corpus/20261104'
def gold(f,box,inset=8):
    x1,y1,x2,y2=box;p=f[y1+inset:y2-inset,x1+inset:x2-inset].astype('int16');r,gg,b=p[:,:,0],p[:,:,1],p[:,:,2]
    return round(float(((r>170)&(gg>120)&(b<110)&(r-b>70)).mean()),3)
rows=collections.OrderedDict()
ds=sorted(p for p in A.iterdir() if p.is_dir() and (('20261104T0002'<=p.name<='20261104T0004') or ('20261104T1040'<=p.name<='20261104T1041')))
for q in ds:
    f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
    for name,box in g.boxes(f):
        box=tuple(int(v) for v in box);rows.setdefault((name,box),[]).append((q.name[9:15],gold(f,box)))
for k,v in rows.items():print(k,v[:4],len(v))
import os;sys.stdout.flush();os._exit(0)
