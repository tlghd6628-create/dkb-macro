"""Read-only: HUD ink brightness by screen type, before and after the update."""
from pathlib import Path
import sys,json,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
import owner_movement as m
c=bootstrap.A/'logs/scene-corpus/20261104'
n=m.asset('settings-hud');white=n.min(axis=2)>170
def stat(f):
    x,y,w,h=758,440,26,30;p=f[y:y+h,x:x+w].astype('float32')
    ink=float(p[white].mean());bg=float(p[~white].mean());r=cv2.matchTemplate(f[y-3:y+h+3,x-3:x+w+3],n,cv2.TM_CCOEFF_NORMED)
    return round(ink,1),round(bg,1),round(float(r.max()),3)
post=sorted(p for p in c.iterdir() if p.is_dir() and p.name>='20261104T1000' and (p/'screen.png').exists())
for p in post:
    f=np.asarray(Image.open(p/'screen.png').convert('RGB'))
    print(p.name[9:15],'modal' if m.find(f,'teleport-b-button',(340,270,200,70),.9,.5) else '-',stat(f))
L=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\owner\current_checks\live')
for name in('town-field.png','b-move-field.png','b-move-dialog.png','new-map-field.png'):
    f=np.asarray(Image.open(L/name).convert('RGB'));print(name,stat(f),'field_hud',m.field_hud(f))
pre=[p for p in sorted((bootstrap.A/'logs/scene-corpus').iterdir()) if p.is_dir() and p.name>='20261102' and p.name<='20261103']
cnt=collections.Counter()
for day in pre:
    for q in list(sorted(x for x in day.iterdir() if x.is_dir()))[::60]:
        if not (q/'screen.png').exists():continue
        f=np.asarray(Image.open(q/'screen.png').convert('RGB'))
        if f.shape!=(479,897,3):continue
        s=stat(f);print(q.name[:15],json.loads((q/'observation.json').read_text(encoding='utf-8')).get('predicted_kind'),s,m.field_hud(f))
import os;sys.stdout.flush();os._exit(0)
