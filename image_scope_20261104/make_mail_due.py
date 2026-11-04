"""User-approved check: make the mail reward cycle due, so the fixed path runs on the next F1. Program must be closed.
Only this one record's time changes; a backup is kept. Nothing is claimed unless mail is really there."""
from pathlib import Path
import json,shutil,time
S=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\settings\owner-reward-cycle.json')
B=Path(__file__).parent/'user_flags_backup';B.mkdir(exist_ok=True);shutil.copy2(S,B/(time.strftime('%H%M%S')+'_owner-reward-cycle.json'))
d=json.loads(S.read_text(encoding='utf-8'))
for name,row in d['characters'].items():
    item=row.get('auto_rewards.mail.enabled')
    if isinstance(item,dict):print(name[:24],item);item['at']=time.time()-4*3600;item['state']='none';item.pop('rechecks',None)
tmp=S.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=1),encoding='utf-8');tmp.replace(S)
