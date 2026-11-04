"""Read-only: for each live capture, which original images hit exactly, which only via the new layer, and which sit elsewhere."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
import owner_image_scope as scope
D=Path(__file__).parent/'live'
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in store.items() if e.get('type')=='template']
plain=RoiDetector.find
d=RoiDetector(profile,names)
want=sys.argv[1:] or [p.stem for p in sorted(D.glob('*.png'))]
out={}
for stem in want:
    f=np.asarray(Image.open(D/(stem+'.png')).convert('RGB'));exact=[];layer=[];far=[]
    for n in names:
        e=d.entries[n]
        if plain(d,n,f,None,.9,candidate_filter=None):exact.append(n);continue
        h=scope.recover(d,n,f,None,.9,None)
        if h:layer.append((n,h[2][0]-e['x'],h[2][1]-e['y']));continue
        if n in d.masks:continue
        p=scope.peaks(f[:,:,::-1],d.templates[n],(0,0,897,479))
        if p and p[0][0]>=.9 and (len(p)<2 or p[0][0]-p[1][0]>=.1):far.append((n,round(p[0][0],3),p[0][1]-e['x'],p[0][2]-e['y']))
    print('==',stem,'exact',len(exact));print(' exact:',exact);print(' layer:',layer);print(' elsewhere:',far,flush=True)
    out[stem]={'exact':exact,'layer':layer,'elsewhere':far}
path=D/'eval.json';old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {};old.update(out);path.write_text(json.dumps(old,ensure_ascii=False,indent=1),encoding='utf-8')
import os;sys.stdout.flush();os._exit(0)
