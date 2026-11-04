"""Read-only: scene() before and after this change across saved frames, and native quest slots after the update."""
from pathlib import Path
import sys,json,collections,time,importlib.util,importlib.machinery
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_startup_stage as st,owner_movement as m,owner_image_scope as scope
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES
import project_adapter.main_quest as mq
D=Path(__file__).resolve().parent
profile=bootstrap.A/'profiles/DKB'
names=list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES]))
def load_old(mod,src):
    spec=importlib.util.spec_from_file_location(mod,src,loader=importlib.machinery.SourceFileLoader(mod,str(src)));x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x
old_mv=load_old('old_movement',D/'before/owner_movement.py');old_mv.asset=m.asset
frames=[]
for day in sorted(p for p in (bootstrap.A/'logs/scene-corpus').iterdir() if p.is_dir()):
    ds=sorted(x for x in day.iterdir() if x.is_dir() and (x/'screen.png').exists())
    frames+=ds if day.name=='20261104' else ds[::max(1,len(ds)//400)]
det=RoiDetector(profile,names)
def before(f):
    # scene() with the previous movement helpers, before the shared layer installs.
    saved=(m.field_hud,m.tower_combat,m.hud_dimmed)
    m.field_hud,m.tower_combat,m.hud_dimmed=old_mv.field_hud,old_mv.tower_combat,lambda f:False
    try:return st.scene(det,f)
    finally:m.field_hud,m.tower_combat,m.hud_dimmed=saved
loaded=[]
for q in frames:
    f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
    if f.shape==(479,897,3):loaded.append((q.name,f))
print('frames',len(loaded),flush=True)
t=time.perf_counter();old=[before(f) for _,f in loaded];told=time.perf_counter()-t
scope.install()
det2=RoiDetector(profile,names)
t=time.perf_counter();new=[st.scene(det2,f) for _,f in loaded];tnew=time.perf_counter()-t
flip=collections.Counter();ex=collections.defaultdict(list)
for (name,_),a,b in zip(loaded,old,new):
    era='post' if name>='20261104T1000' else 'pre';flip[(era,a,b)]+=1
    if a!=b:ex[(era,a,b)].append(name)
out={'frames':len(loaded),'scene_ms_per_frame':{'before':round(told/len(loaded)*1000,3),'after':round(tnew/len(loaded)*1000,3)},
 'tally':{'|'.join(k):v for k,v in sorted(flip.items())},'changed':{'|'.join(k):v[:25] for k,v in ex.items()}}
print(json.dumps(out,ensure_ascii=False,indent=1),flush=True)
slots=mq.StateROIs(profile,mode='sub_quest');tally=collections.Counter();sample={}
for name,f in loaded:
    if name<'20261104T1000':continue
    for key in slots.by_key:
        if slots.by_key[key].get('roi') is None:continue
        try:r=slots.match(key,f)
        except KeyError:continue
        a=r.get('appearance') or {}
        if r.get('score',0)>=.75 or r.get('hit'):
            tally[(key,'hit' if r.get('hit') else 'no',str(a.get('valid')))]+=1
            sample[key]=(round(r.get('score',0),3),{k:(round(v,3) if isinstance(v,float) else v) for k,v in a.items()})
out['slots_post']={'|'.join(k):v for k,v in tally.items()};out['slots_sample']=sample
(D/'scene_slots.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps({'slots_post':out['slots_post'],'slots_sample':sample},ensure_ascii=False,indent=1))
import os;sys.stdout.flush();os._exit(0)
