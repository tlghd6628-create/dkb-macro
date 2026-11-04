"""Read-only inventory of native ROI names, used only to plan window scopes."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from project_adapter import protected_assets
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
lines=[]
for n,e in sorted(store.items()):
    lines.append(f"{n}\t{e.get('type')}\t{e.get('x')},{e.get('y')},{e.get('w',1)},{e.get('h',1)}\t{e.get('group')}\t{e.get('updated_at','')[:10]}")
(Path(__file__).parent/'store_names.tsv').write_text('\n'.join(lines),encoding='utf-8')
print(len(lines))
import os;sys.stdout.flush();os._exit(0)
