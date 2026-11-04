"""Follow-up private apply: only proceeds if the install still holds what the first apply wrote."""
from pathlib import Path
import hashlib,json,shutil,time,os,sys
C=Path(__file__).resolve().parents[1];I=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\owner');D=Path(__file__).parent
FILES=sys.argv[1:]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((D/'receipt.json').read_text(encoding='utf-8'));known={r['file']:r['after'] for r in receipt['files']}
for extra in receipt.get('followups',[]):
    for r in extra['files']:known[r['file']]=r['after']
for name in FILES:
    if name in known and sha(I/name)!=known[name]:raise SystemExit('install changed since last apply: '+name)
stamp=time.strftime('%Y%m%d_%H%M%S');backup=D/'installed_backup'/stamp;rows=[]
for name in FILES:
    target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);(I/name).exists() and shutil.copy2(I/name,target)
    temp=(I/name).with_name((I/name).name+'.imagescope.tmp');shutil.copy2(C/name,temp);os.replace(temp,I/name)
    if sha(I/name)!=sha(C/name):raise SystemExit('hash mismatch: '+name)
    rows.append({'file':name,'after':sha(I/name)})
receipt.setdefault('followups',[]).append({'applied_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'backup':str(backup),'files':rows})
(D/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=1),encoding='utf-8');print('applied',FILES)
