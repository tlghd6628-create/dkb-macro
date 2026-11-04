"""Read-only: colour vs text-foreground scoring on the real modal and map, old layout, and neighbours."""
from pathlib import Path
import os
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from roi_runtime import RoiDetector
import owner_movement as m
D=Path(__file__).resolve().parent
L=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'owner/current_checks/live'
frames={'modal_new':np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png').convert('RGB')),
 'map_new':np.asarray(Image.open(D/'map_frame_897x479.png').convert('RGB')),
 'modal_old':np.asarray(Image.open(L/'b-move-dialog.png').convert('RGB')),'field_old':np.asarray(Image.open(L/'b-move-field.png').convert('RGB'))}
names=['버튼_축지술_가운데','버튼_지도_축지술','버튼_보스_축지술','버튼_귀환']
d=RoiDetector(bootstrap.A/'profiles/DKB',names)
def views(a):
    a=a.astype('float32')
    return {'rgb':a,'gray':cv2.cvtColor(a.astype('uint8'),cv2.COLOR_RGB2GRAY),'min':a.min(axis=2),
            'edge':cv2.magnitude(cv2.Sobel(cv2.cvtColor(a.astype('uint8'),cv2.COLOR_RGB2GRAY).astype('float32'),cv2.CV_32F,1,0),cv2.Sobel(cv2.cvtColor(a.astype('uint8'),cv2.COLOR_RGB2GRAY).astype('float32'),cv2.CV_32F,0,1))}
def peaks(hay,needle,n=3):
    r=cv2.matchTemplate(hay.astype('float32'),needle.astype('float32'),cv2.TM_CCOEFF_NORMED);r=np.where(np.isfinite(r),r,-1).copy();out=[];hh,ww=needle.shape[:2]
    for _ in range(n):
        _,s,_,p=cv2.minMaxLoc(r);out.append((round(float(s),3),p[0],p[1]));r[max(0,p[1]-hh//2):p[1]+hh//2+1,max(0,p[0]-ww//2):p[0]+ww//2+1]=-1
    return out
for fn,f in frames.items():
    print('==',fn,f.shape);fv=views(f)
    for n in names[:3]:
        tv=views(d.templates[n][:,:,::-1])
        print(' ',n,{k:peaks(fv[k],tv[k]) for k in fv})
    for a in('move-method-title','teleport-b-button'):
        tv=views(m.asset(a));print(' ',a,{k:peaks(fv[k],tv[k],2) for k in fv})
Image.fromarray(frames['modal_old']).save(D/'modal_old.png')
import project_adapter.favorite_hunt as fh,project_adapter.field_boss as fb,project_adapter.town_services as ts
print('favorite',fh.NAMES);print('boss',fb.NAMES);print('town',ts.TOWN_NAMES)
import os;sys.stdout.flush();os._exit(0)
