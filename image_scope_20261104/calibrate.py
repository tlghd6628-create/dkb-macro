"""Read-only: HUD foreground numbers by screen kind, and native slot appearance guards after the update."""
from pathlib import Path
import sys,json,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
import owner_movement as m,owner_image_scope as scope
import project_adapter.main_quest as mq
c=bootstrap.A/'logs/scene-corpus'
def stat(f,name,box):
    n=m.asset(name);x,y,w,h=box;found=scope.peaks(f,n,scope._clip(x-6,y-6,w+12,h+12),count=1)
    s,l,t=found[0];p=f[t:t+h,l:l+w].astype('float32');white=n.min(axis=2)>170;g=float(p[white].mean())/float(n[white].mean())
    q=p/g;return round(s,3),l-x,t-y,round(g,3),round(float((q.min(axis=2)[white]>150).mean()),3),round(float(np.abs(q-n.astype('float32'))[white].mean()),1)
rows=collections.defaultdict(list)
days=[p for p in sorted(c.iterdir()) if p.is_dir()]
for day in days:
    ds=sorted(x for x in day.iterdir() if x.is_dir())
    step=1 if day.name=='20261104' else max(1,len(ds)//250)
    for q in ds[::step]:
        png=q/'screen.png'
        if not png.exists():continue
        try:kind=json.loads((q/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')
        except Exception:continue
        f=np.asarray(Image.open(png).convert('RGB'))
        if f.shape!=(479,897,3):continue
        era='post' if q.name>='20261104T1000' else 'pre'
        rows[(era,kind)].append((stat(f,'home-hud',(662,441,25,29)),stat(f,'settings-hud',(758,440,26,30)),bool(m.field_hud(f))))
def summ(v,i):
    a=np.array([r[i][j] for r in v for j in (0,)]);
    return {'score':[round(float(np.percentile([r[i][0] for r in v],p)),3) for p in(5,50,95)],'gain':[round(float(np.percentile([r[i][3] for r in v],p)),3) for p in(5,50,95)],'share':[round(float(np.percentile([r[i][4] for r in v],p)),3) for p in(5,50,95)],'abs':[round(float(np.percentile([r[i][5] for r in v],p)),1) for p in(5,50,95)]}
for k,v in sorted(rows.items(),key=str):
    print(k,len(v),'old_field_hud',sum(r[2] for r in v),'home',summ(v,0),'set',summ(v,1))
slots=mq.StateROIs(bootstrap.A/'profiles/DKB',mode='sub_quest')
D=c/'20261104';tally=collections.Counter();ex={}
for q in sorted(x for x in D.iterdir() if x.is_dir() and x.name>='20261104T1000'):
    f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
    for key in slots.by_key:
        r=slots.match(key,f);a=r.get('appearance') or {}
        if r.get('score',0)>=.8 or r.get('hit'):
            tally[(key,bool(r.get('hit')),a.get('valid'))]+=1;ex[key]=(round(r.get('score',0),3),{k:(round(v,3) if isinstance(v,float) else v) for k,v in a.items()})
print(dict(tally));print(ex)
print(slots.detector.__class__,slots.config if False else '')
import os;sys.stdout.flush();os._exit(0)
