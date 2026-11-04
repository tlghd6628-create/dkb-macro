"""Read-only corpus replay: what does the shared layer change? Pre-update layouts are the control:
any recovered template there is a suspect. Saved frames only; no game, no input."""
from pathlib import Path
import sys,json,time,collections,importlib.util,importlib.machinery,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
import owner_startup_stage as st,owner_movement as m,owner_image_scope as scope
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES
D=Path(__file__).resolve().parent
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in store.items() if e.get('type')=='template']
plain=RoiDetector.find
d=RoiDetector(profile,names)
def load_old(mod,src):
    spec=importlib.util.spec_from_file_location(mod,src,loader=importlib.machinery.SourceFileLoader(mod,str(src)));x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x
old_mv=load_old('old_movement',D/'before/owner_movement.py');old_mv.asset=m.asset;old_st=load_old('old_stage',D/'before/owner_startup_stage.py')
sd_old=RoiDetector(profile,list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
sd_new=RoiDetector(profile,list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
frames=[]
for day in sorted(p for p in (bootstrap.A/'logs/scene-corpus').iterdir() if p.is_dir()):
    ds=sorted(x for x in day.iterdir() if x.is_dir() and (x/'screen.png').exists() and (x/'observation.json').exists())
    if day.name=='20261104':frames+=ds
    else:
        by=collections.defaultdict(list)
        for q in ds:
            try:by[json.loads((q/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')].append(q)
            except Exception:pass
        random.seed(11)
        for k,v in by.items():frames+=random.sample(v,min(len(v),40 if k in('field','dungeon','unknown') else 120))
print('frames',len(frames),flush=True)
LOGGED=[];scope._hit.seen=set()
real=scope._hit
recovered=collections.Counter();examples={};scene_flip=collections.Counter();flip_ex=collections.defaultdict(list);hud=collections.Counter();cost=[];missing=0
installed=False
for i,q in enumerate(frames):
    f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
    if f.shape!=(479,897,3):continue
    era='post' if q.name>='20261104T1000' else 'pre'
    a=old_st.scene.__wrapped__ if False else None
    # old scene needs old field_hud, plain find
    import owner_movement
    saved=(owner_movement.field_hud,owner_movement.hud_dimmed)
    x=old_st.scene(sd_old,f) if False else None
    for n in names:
        e=d.entries[n]
        if plain(d,n,f,None,.9,candidate_filter=None) is not None:continue
        s=time.perf_counter();h=scope.recover(d,n,f,None,.9,None);cost.append(time.perf_counter()-s)
        if h is not None:
            key=(era,n);recovered[key]+=1
            examples.setdefault(key,{'frame':q.name,'hit':h[:2],'roi':[e['x'],e['y']]})
    nh=bool(m.field_hud(f));oh=bool(old_mv.field_hud(f));hud[(era,oh,nh)]+=1
    if oh!=nh:flip_ex[('hud',era,oh,nh)].append(q.name)
    if i%200==0:print(i,flush=True)
cost.sort()
out={'frames':len(frames),'templates':len(names),'recover_ms':{'n':len(cost),'p50':round(cost[len(cost)//2]*1000,3),'p95':round(cost[int(len(cost)*.95)]*1000,3),'p99':round(cost[int(len(cost)*.99)]*1000,3),'max':round(cost[-1]*1000,3)},
 'recovered':{f'{k[0]}|{k[1]}':{'count':v,**examples[k]} for k,v in recovered.most_common()},'field_hud':{str(k):v for k,v in hud.items()},'field_hud_flips':{str(k):v[:15] for k,v in flip_ex.items()}}
(D/'corpus_replay.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps({k:out[k] for k in('frames','recover_ms','field_hud','field_hud_flips')},ensure_ascii=False,indent=1))
for k,v in recovered.most_common(80):print(k,v,examples[k])
import os;sys.stdout.flush();os._exit(0)
