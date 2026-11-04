"""Read-only: scene() and HUD pieces on frames before and after today's update."""
from pathlib import Path
import sys,json,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_startup_stage as st,owner_movement as m
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES
D=Path(__file__).resolve().parent
c=bootstrap.A/'logs/scene-corpus/20261104'
dirs=sorted(p for p in c.iterdir() if p.is_dir() and (p/'screen.png').exists())
post=[p for p in dirs if p.name>='20261104T1000'];pre=[p for p in dirs if p.name<'20261104T0500']
print('post',len(post),post[0].name if post else None,post[-1].name if post else None,'pre',len(pre))
d=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
def load(p):return np.asarray(Image.open(p/'screen.png').convert('RGB'))
for label,group in (('post',post),('pre',pre[::max(1,len(pre)//60)])):
    t=collections.Counter();h=collections.Counter();k=collections.Counter()
    for p in group:
        f=load(p)
        if f.shape!=(479,897,3):t['badshape']+=1;continue
        t[st.scene(d,f)]+=1
        h['field_hud']+=bool(m.field_hud(f));h['home']+=bool(m.hud_anchor(f,'home-hud',(662,441,25,29)));h['settings']+=bool(m.hud_anchor(f,'settings-hud',(758,440,26,30)))
        h['menu']+=bool(d.find(st.MENU,f,threshold=.95))
        for n in AUTO_NAMES:h[n]+=bool(d.find(n,f,threshold=.95))
        try:k[json.loads((p/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')]+=1
        except Exception:pass
    print(label,'scene',dict(t),'pieces',dict(h),'archived_kind',dict(k))
if post and pre:
    choose=[p for p in post if json.loads((p/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')=='field'] or post
    a=load(pre[len(pre)//2]);b=load(choose[len(choose)//2])
    print('compare',pre[len(pre)//2].name,choose[len(choose)//2].name)
    canvas=np.vstack([a[425:479,640:897],b[425:479,640:897],a[0:40,640:897],b[0:40,640:897]])
    Image.fromarray(canvas).resize((canvas.shape[1]*3,canvas.shape[0]*3),Image.NEAREST).save(D/'hud_pre_post_3x.png')
    Image.fromarray(b).save(D/'post_sample.png')
import os;sys.stdout.flush();os._exit(0)
