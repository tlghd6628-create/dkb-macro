"""User-requested 21:40: raid stage 2. Program must be closed. Backs up first, changes this one value."""
from pathlib import Path
import os
import json,shutil,time
S=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'vendor/DKB_Auto/settings/auto-settings.json'
B=Path(__file__).parent/'user_flags_backup';B.mkdir(exist_ok=True);shutil.copy2(S,B/(time.strftime('%H%M%S')+'_auto-settings.json'))
d=json.loads(S.read_text(encoding='utf-8-sig'));key='auto_schedule.boss_raid.stage'
print(key,d['values'][key],'-> 2단계');d['values'][key]='2단계'
tmp=S.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(S)
