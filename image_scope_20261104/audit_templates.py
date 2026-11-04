"""Read-only: which native templates miss their fixed ROI but match elsewhere? Saved frames only; no game, no input."""
from pathlib import Path
import sys,json,time,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
D=Path(__file__).resolve().parent
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
kinds=collections.Counter(e.get('type') for e in store.values())
names=[n for n,e in store.items() if e.get('type')=='template' and e.get('target')=='game' and tuple(e.get('capture_size',()))==tuple(target['client_size'])]
detector=RoiDetector(profile,names)
corpus=bootstrap.A/'logs/scene-corpus/20261104'
dirs=sorted(p for p in corpus.iterdir() if p.is_dir())
post=[p/'screen.png' for p in dirs if p.name>='20261104T1000' and (p/'screen.png').exists()]
post.append(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png')
pre=[p/'screen.png' for p in dirs if p.name<'20261104T0500' and (p/'screen.png').exists()]
pre=pre[::max(1,len(pre)//150)]
def load(p):
    f=np.asarray(Image.open(p).convert('RGB'));return f if f.shape==(479,897,3) else None
def scan(paths,label):
    moved=collections.defaultdict(list);exact=collections.Counter();far=collections.Counter();t=[];n=0
    for p in paths:
        f=load(p)
        if f is None:continue
        n+=1;hay=f[:,:,::-1].copy()
        for name in names:
            e=detector.entries[name]
            if detector.find(name,f,threshold=.9):exact[name]+=1;continue
            needle=detector.templates[name];s=time.perf_counter()
            mask=detector.masks.get(name)
            if mask is not None:continue
            r=cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED);t.append(time.perf_counter()-s)
            _,score,_,pos=cv2.minMaxLoc(np.where(np.isfinite(r),r,-1))
            if score>=.9:
                far[name]+=1
                moved[name].append({'frame':p.parent.name,'score':round(float(score),4),'at':list(pos),'dx':pos[0]-e['x'],'dy':pos[1]-e['y']})
    print(label,'frames',n,'whole-frame match ms p50',round(sorted(t)[len(t)//2]*1000,3) if t else None,flush=True)
    return {'frames':n,'exact_hits':dict(exact),'elsewhere':{k:{'count':far[k],'exact':exact[k],'first':v[0],'offsets':sorted({(x['dx'],x['dy']) for x in v})[:8]} for k,v in moved.items()}}
result={'scope':'saved frames + original detector; not live','store_kinds':dict(kinds),'templates':len(names),
 'masked_templates':len(detector.masks),'sizes':{'area_le_400':sum(1 for n in names if detector.entries[n]['w']*detector.entries[n]['h']<=400)}}
result['post_patch']=scan(post,'post');result['pre_patch']=scan(pre,'pre')
(D/'audit_templates.json').write_text(json.dumps(result,ensure_ascii=False,indent=1,default=list),encoding='utf-8')
for label in('post_patch','pre_patch'):
    print(label,len(result[label]['elsewhere']),'templates matched elsewhere')
    for k,v in sorted(result[label]['elsewhere'].items(),key=lambda kv:-kv[1]['count'])[:45]:
        print(' ',k.encode('unicode_escape').decode() if False else k,v['count'],'exact',v['exact'],v['first']['score'],v['offsets'][:3])
sys.stdout.flush()
import os;os._exit(0)
