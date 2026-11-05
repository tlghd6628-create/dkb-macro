"""On saved pairs only, never a game test: does the 1366x768 frame give the same answers as the 897x479 one?
Prints per screen which screen map it picked, and which pictures and point checks disagree."""
from pathlib import Path
import sys,json,os
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
sys.stdout.reconfigure(encoding='utf-8')
import bootstrap
import numpy as np
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
import owner_hd as hd
hd.install_reading()
P=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(P/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
roi=json.loads(protected_assets.read_text(P/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in roi.items() if e.get('type') in ('template','point') and e.get('target')=='game']
det=RoiDetector(P,names)
D=C/'image_scope_20261104/hd_frames'
only=set(sys.argv[1:])
total=agree=0
for path in sorted(D.glob('*_1x.png')):
    screen=path.stem[:-3]
    if only and screen not in only:continue
    small=np.asarray(Image.open(path).convert('RGB'));real=np.asarray(Image.open(D/(screen+'_hd.png')).convert('RGB'))
    frame=hd.make_frame(real)
    lost=[];false=[];moved=[]
    for n in names:
        a=det.find(n,small,threshold=.9);b=det.find(n,frame,threshold=.9)
        total+=1
        if bool(a)==bool(b):
            agree+=1
            if a and (abs(a[0]-b[0])>4 or abs(a[1]-b[1])>4):moved.append((n,a[:2],b[:2]))
        elif a:lost.append(n+('*' if roi[n]['type']=='point' else ''))
        else:false.append(n+('*' if roi[n]['type']=='point' else ''))
    print(screen,'map',frame.layout.name,'lost',len(lost),lost[:8],'false',len(false),false[:8],'moved',moved[:4],flush=True)
print('agree %d/%d'%(agree,total))
sys.stdout.flush();os._exit(0)
