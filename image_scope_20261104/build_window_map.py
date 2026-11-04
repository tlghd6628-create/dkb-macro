"""Offline: learn which window every native button belongs to, from which images are visible together.

For each button, an anchor is an image that is on screen when the button is, and rarely otherwise.
Nothing is hand-listed; no image is added. Output: assets/image-scope/window_map.json."""
from pathlib import Path
import sys,json,collections,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
ROOT=Path(__file__).resolve().parents[1];L=Path(__file__).parent/'live'
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in store.items() if e.get('type')=='template']
d=RoiDetector(profile,names);plain=RoiDetector.find
paths=sorted(L.glob('*.png'))
for day in sorted(p for p in (bootstrap.A/'logs/scene-corpus').iterdir() if p.is_dir()):
    by=collections.defaultdict(list)
    for q in sorted(x for x in day.iterdir() if x.is_dir() and (x/'screen.png').exists() and (x/'observation.json').exists()):
        try:by[json.loads((q/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')].append(q/'screen.png')
        except Exception:pass
    random.seed(3)
    for k,v in by.items():paths+=random.sample(v,min(len(v),25 if k in('field','dungeon') else 200))
print('frames',len(paths),flush=True)
seen=[];
for i,p in enumerate(paths):
    f=np.asarray(Image.open(p).convert('RGB'))
    if f.shape!=(479,897,3):continue
    seen.append(frozenset(n for n in names if plain(d,n,f,None,.93,candidate_filter=None) is not None))
    if i%300==0:print(i,flush=True)
total=len(seen);count=collections.Counter(n for s in seen for n in s)
pair=collections.Counter()
for s in seen:
    for a in s:
        for b in s:
            if a!=b:pair[(a,b)]+=1
rows={}
for n in names:
    if not n.startswith('버튼_') or count[n]==0:continue
    x=d.entries[n]
    anchors=[]
    for a in names:
        if a==n or count[a]==0:continue
        e=d.entries[a]
        # Sharing a spot means it may be a state of the same control, not a separate witness.
        ix,iy=min(x['x']+x['w'],e['x']+e['w'])-max(x['x'],e['x']),min(x['y']+x['h'],e['y']+e['h'])-max(x['y'],e['y'])
        if ix>0 and iy>0:continue
        if e['w']*e['h']<80:continue
        together=pair[(n,a)]/count[n]
        elsewhere=(count[a]-pair[(n,a)])/max(1,total-count[n])
        if together>=.8 and elsewhere<=.12:anchors.append((round(together-elsewhere,3),a))
    anchors=[a for _,a in sorted(anchors,reverse=True)[:6]]
    if len(anchors)>=2:rows[n]={'anchors':anchors,'need':max(2,(len(anchors)+1)//2),'seen':count[n]}
out=ROOT/'assets/image-scope';out.mkdir(parents=True,exist_ok=True)
(out/'window_map.json').write_text(json.dumps({'frames':total,'rows':rows},ensure_ascii=False,indent=0),encoding='utf-8')
b=[n for n in names if n.startswith('버튼_')]
print('buttons',len(b),'seen',sum(1 for n in b if count[n]),'mapped',len(rows))
print('unseen',[n for n in b if not count[n]][:200])
for n in list(rows)[:30]:print(n,rows[n])
import os;sys.stdout.flush();os._exit(0)
