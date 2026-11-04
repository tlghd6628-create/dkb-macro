"""Private apply of this batch to the installed owner folder: backup, hash guard, atomic replace, receipt."""
from pathlib import Path
import hashlib,json,shutil,time,os,sys
C=Path(__file__).resolve().parents[1];I=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\owner');D=Path(__file__).parent
FILES=['owner_image_scope.py','owner_reward_flow.py','owner_movement.py','owner_startup_stage.py','owner_support.py','owner_rewards.py','owner_reward_cycle.py','owner_reward_visual_guard.py','owner_reward_action_test.py',
       'assets/reward-proof/notice-dot.png','assets/image-scope/window_map.json']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
stamp=time.strftime('%Y%m%d_%H%M%S');backup=D/'installed_backup'/stamp;rows=[]
for name in FILES:
    before=D/'before'/name;now=I/name
    if now.exists() and before.exists() and sha(before)!=sha(now):raise SystemExit('install changed since snapshot: '+name)
    if now.exists() and not before.exists() and not name.startswith('assets/'):raise SystemExit('unexpected existing file: '+name)
for name in FILES:
    now=I/name
    if now.exists():
        target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(now,target)
for name in FILES:
    src=C/name;now=I/name;now.parent.mkdir(parents=True,exist_ok=True);old=sha(now)
    temp=now.with_name(now.name+'.imagescope.tmp');shutil.copy2(src,temp);os.replace(temp,now)
    if sha(now)!=sha(src):raise SystemExit('hash mismatch after copy: '+name)
    rows.append({'file':name,'before':old,'after':sha(now)})
(D/'receipt.json').write_text(json.dumps({'applied_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'backup':str(backup),'files':rows},ensure_ascii=False,indent=1),encoding='utf-8')
print('applied',len(rows),'backup',backup)
