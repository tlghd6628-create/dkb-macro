"""Read-only: how much of the program's recognition does the shared layer reach?"""
from pathlib import Path
import sys,json,re,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from project_adapter import protected_assets
import owner_image_scope as scope
C=Path(__file__).resolve().parents[1]
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
kinds=collections.Counter(e.get('type') for e in store.values() if isinstance(e,dict))
t=[n for n,e in store.items() if isinstance(e,dict) and e.get('type')=='template']
b=[n for n in t if n.startswith('버튼_')];c=[n for n in t if n.startswith('체크_')]
commit=[n for n in b if scope.committed(n) and n!='버튼_축지술_가운데'];lst=[n for n in b if scope.listed(n) and n not in commit]
win=[n for n in b if n in scope.MEMBER and n not in commit]
map_=[n for n in b if n in scope.learned() and n not in commit and n not in lst and n not in scope.MEMBER]
rest=[n for n in b if n not in commit and n not in lst and n not in scope.MEMBER and n not in map_]
print(dict(kinds));print('buttons',len(b),'checks',len(c))
print('window table',len(win),'learned',len(map_),'commit exact only',len(commit),'list rows exact only',len(lst),'not yet mapped',len(rest))
print('commit',commit);print('unmapped',rest)
own=collections.Counter();px=collections.Counter()
for p in sorted(C.glob('owner_*.py')):
    s=p.read_text(encoding='utf-8')
    n=len(re.findall(r'cv2\.matchTemplate',s));
    if n:own[p.name]=n
    k=len(re.findall(r'\.click\(\s*\d{2,3}\s*,\s*\d{2,3}',s))
    if k:px[p.name]=k
print('private matchTemplate',sum(own.values()),'in',len(own),own.most_common(14))
print('fixed coordinate clicks',sum(px.values()),'in',len(px),px.most_common(14))
import os;sys.stdout.flush();os._exit(0)
