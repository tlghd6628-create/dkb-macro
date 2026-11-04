"""User asked for dungeons to run on schedule. Restores the timetable switch left off by the 11-03 quest-only trial.
Backs up the file first and changes only `enabled`."""
from pathlib import Path
import json,shutil,time,os
S=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\settings\owner-timetable.json')
D=Path(__file__).parent/'timetable_backup';D.mkdir(exist_ok=True)
copy=D/('owner-timetable.%s.json'%time.strftime('%Y%m%d_%H%M%S'));shutil.copy2(S,copy)
data=json.loads(S.read_text(encoding='utf-8-sig'));print('before',data['enabled'],'backup',copy.name)
data['enabled']=True
tmp=S.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,S)
print('after',json.loads(S.read_text(encoding='utf-8-sig'))['enabled'])
