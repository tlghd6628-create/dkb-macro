"""Read-only: user's world-map screenshot against the original map templates. No game, no input."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
D=Path(__file__).resolve().parent
shot=np.asarray(Image.open(r'C:\Users\홍이\Pictures\Screenshots\스크린샷 2026-11-04 111255.png').convert('RGB'))
print('shot',shot.shape)
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in store.items() if e.get('type')=='template' and ('지도' in n or '축지' in n or n in('버튼_전체매뉴','버튼_나가기','버튼_보스_세계지도이동','버튼_X'))]
d=RoiDetector(profile,names)
best=(-1,None)
for top in (30,31,32):
  for left in (0,1):
    f=shot[top:top+479,left:left+897]
    if f.shape!=(479,897,3):continue
    s=sum(float(cv2.matchTemplate(f[e['y']-3:e['y']+e['h']+3,max(0,e['x']-3):e['x']+e['w']+3][:,:,::-1].copy(),d.templates[n],cv2.TM_CCOEFF_NORMED).max()) for n,e in ((n,d.entries[n]) for n in ('버튼_지도_일반','버튼_지도_즐겨찾기','버튼_지도_저장위치')))
    print('crop',top,left,round(s,3))
    if s>best[0]:best=(s,(top,left))
top,left=best[1];f=shot[top:top+479,left:left+897].copy();Image.fromarray(f).save(D/'map_frame_897x479.png');print('chosen',top,left)
def peaks(needle,mask,n=4):
    r=cv2.matchTemplate(f[:,:,::-1].copy(),needle,cv2.TM_CCOEFF_NORMED);r=np.where(np.isfinite(r),r,-1).copy();out=[];hh,ww=needle.shape[:2]
    for _ in range(n):
        _,s,_,p=cv2.minMaxLoc(r);out.append((round(float(s),3),p[0],p[1]));r[max(0,p[1]-hh//2):p[1]+hh//2+1,max(0,p[0]-ww//2):p[0]+ww//2+1]=-1
    return out
for n in names:
    e=d.entries[n];hit=d.find(n,f)
    print(n,(e['x'],e['y'],e['w'],e['h']),'exact.9',bool(hit),'peaks',peaks(d.templates[n],None))
Image.fromarray(f[425:479,640:897]).resize((771,162),Image.NEAREST).save(D/'map_buttons_3x.png')
for n in('버튼_지도_축지술','버튼_보스_축지술','버튼_축지술_가운데'):
    t=d.templates[n][:,:,::-1];Image.fromarray(t).resize((t.shape[1]*6,t.shape[0]*6),Image.NEAREST).save(D/(n+'_6x.png'))
import os;sys.stdout.flush();os._exit(0)
