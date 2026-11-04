"""User-requested 19:10: world boss on, equipment disassembly off. Program must be closed.
Backs up the settings file first and changes only these two values. Daily dungeon was already the only dungeon on."""
from pathlib import Path
import json,shutil,sys,time
S=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\settings\auto-settings.json')
B=Path(__file__).parent/'user_flags_backup';B.mkdir(exist_ok=True)
shutil.copy2(S,B/(time.strftime('%H%M%S')+'_auto-settings.json'))
raw=S.read_text(encoding='utf-8-sig');d=json.loads(raw)
for key,value in (('auto_schedule.field_boss.enabled',True),('auto_register.equipment_disassembly.enabled',False)):
    print(key,d['values'][key],'->',value);d['values'][key]=value
tmp=S.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(S)
check=json.loads(S.read_text(encoding='utf-8'))['values']
print('dungeons',{k:v for k,v in check.items() if k.endswith('.enabled') and not k.startswith('custom') and ('secret' in k or 'folktale' in k)})
