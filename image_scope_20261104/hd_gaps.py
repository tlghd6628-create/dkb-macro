"""Name the pictures the running program asked for that have no new cut yet (owner/assets/hd-missing.txt)."""
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
P=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(P/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
roi=json.loads(protected_assets.read_text(P/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in roi.items() if e.get('type')=='template' and e.get('target')=='game']
det=RoiDetector(P,names)
labels={hd.key_of(det.templates[n]):'native:'+n for n in names}
for root in (C/'assets',C/'skill_assets_candidate'):
    if not root.exists():continue
    for path in root.rglob('*.png'):
        if 'hd' in path.parts:continue
        try:image=np.asarray(Image.open(path).convert('RGB'))
        except OSError:continue
        labels[hd.key_of(image)]='owner:'+str(path.relative_to(C));labels.setdefault(hd.key_of(image[:,:,::-1]),'owner(bgr):'+str(path.relative_to(C)))
path=Path(sys.argv[1]) if len(sys.argv)>1 else bootstrap.A.parents[0]/'owner/assets/hd-missing.txt'
if not path.exists():path=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'owner/assets/hd-missing.txt'
seen=set()
for line in path.read_text(encoding='utf-8').splitlines():
    key=line.split(' ',1)[0]
    if key in seen:continue
    seen.add(key);print(labels.get(key,'?'),line.split(' ',1)[1] if ' ' in line else '')
sys.stdout.flush();os._exit(0)
