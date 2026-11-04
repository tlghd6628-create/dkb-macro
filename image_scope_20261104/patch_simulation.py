"""Simulated update on real frames: move each registered button by today's distance and soften its text.
Synthetic, so it shows the mechanism per window, not that the game will really change this way."""
from pathlib import Path
import sys,json,collections,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from roi_runtime import RoiDetector
import owner_image_scope as scope
D=Path(__file__).resolve().parent
profile=bootstrap.A/'profiles/DKB'
plain=RoiDetector.find
members=[n for w in scope.WINDOWS.values() for n in w['members']]
d=RoiDetector(profile,list(dict.fromkeys(members)))
frames=[]
for day in sorted(p for p in (bootstrap.A/'logs/scene-corpus').iterdir() if p.is_dir()):
    ds=sorted(x for x in day.iterdir() if x.is_dir() and (x/'screen.png').exists() and (x/'observation.json').exists())
    by=collections.defaultdict(list)
    for q in ds:
        try:by[json.loads((q/'observation.json').read_text(encoding='utf-8')).get('predicted_kind')].append(q)
        except Exception:pass
    random.seed(5)
    for k,v in by.items():frames+=random.sample(v,min(len(v),15 if k in('field','dungeon') else 150))
print('frames',len(frames),flush=True)
seen={}
for q in frames:
    f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
    if f.shape!=(479,897,3):continue
    for n in members:
        if n in seen and len(seen[n])>=3:continue
        if plain(d,n,f,None,.9,candidate_filter=None) is not None and scope.window_open(profile,scope.MEMBER[n],f):
            seen.setdefault(n,[]).append((q.name,f))
scope.install()
rows={}
for n in members:
    key=scope.MEMBER[n];rows[n]={'window':key,'frames':len(seen.get(n,[])),'moved_found':0,'wrong':0,'absent_clean':0}
    for name,f in seen.get(n,[]):
        e=d.entries[n];x,y,w,h=e['x'],e['y'],e['w'],e['h']
        for dx,dy in ((-46,2),(-68,0),(40,-3)):
            nx,ny=x+dx,y+dy
            if nx<0 or ny<0 or nx+w>897 or ny+h>479:continue
            g=f.copy();patch=f[y:y+h,x:x+w].copy()
            g[y:y+h,x:x+w]=cv2.GaussianBlur(f[max(0,y-6):y+h+6,max(0,x-6):x+w+6],(0,0),6)[:h,:w]
            g[ny:ny+h,nx:nx+w]=cv2.GaussianBlur(patch,(0,0),.45)
            spec=scope.WINDOWS[key]
            if spec.get('zone'):
                zx,zy,zw,zh=spec['zone']
                if not(zx<=nx and zy<=ny and nx+w<=zx+zw and ny+h<=zy+zh):continue
            scope.LOCAL.frame=None
            hit=d.find(n,g)
            if hit is None:continue
            if hit[2][:2]==(nx,ny):rows[n]['moved_found']+=1
            else:rows[n]['wrong']+=1
        g=f.copy();g[y:y+h,x:x+w]=cv2.GaussianBlur(f[max(0,y-6):y+h+6,max(0,x-6):x+w+6],(0,0),6)[:h,:w];scope.LOCAL.frame=None
        if d.find(n,g) is None:rows[n]['absent_clean']+=1
(D/'patch_simulation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf-8')
cov=[k for k,v in rows.items() if v['moved_found']];none=[k for k,v in rows.items() if not v['frames']]
print(json.dumps({'members':len(rows),'found_moved':len(cov),'no_saved_frame':len(none),'wrong_total':sum(v['wrong'] for v in rows.values())},ensure_ascii=False))
for k,v in rows.items():print(k,v)
import os;sys.stdout.flush();os._exit(0)
