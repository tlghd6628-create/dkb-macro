"""User-requested: raid uses preset 2 (B), everyday preset 1 (A). Program must be closed. Backs up first."""
from pathlib import Path
import json,shutil,time
S=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\settings\auto-settings.json')
B=Path(__file__).parent/'user_flags_backup';B.mkdir(exist_ok=True)
shutil.copy2(S,B/(time.strftime('%H%M%S')+'_auto-settings.json'))
d=json.loads(S.read_text(encoding='utf-8-sig'))
for key,value in (('auto_schedule.boss_raid.skill_preset.enabled',True),('auto_schedule.boss_raid.skill_preset.choice','B'),
                  ('common.skill_preset.enabled',True),('common.skill_preset.choice','A')):
    print(key,d['values'].get(key),'->',value);d['values'][key]=value
tmp=S.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(S)
