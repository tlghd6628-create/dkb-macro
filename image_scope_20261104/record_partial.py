"""The 21:20 apply stopped at a missing asset folder after copying the Python files, so it wrote no receipt.
Record what it put in the install. Their differences from the candidate were checked by hand: only this session's own edits."""
from pathlib import Path
import os
import hashlib,json,time
I=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'owner';D=Path(__file__).parent
FILES=['owner_boss_range.py','owner_boss_gate.py','owner_hunt_memory.py','owner_startup_stage.py','owner_membership.py','owner_schedule_priority.py','owner_task_flow.py','owner_energy_native_candidate.py','owner_hunt_settings_candidate.py','owner_settings_console.py','owner_timetable.py']
receipt=json.loads((D/'receipt.json').read_text(encoding='utf-8'))
rows=[{'file':n,'after':hashlib.sha256((I/n).read_bytes()).hexdigest()} for n in FILES]
receipt.setdefault('followups',[]).append({'applied_at':'2026-11-04T21:20:30','recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'note':'partial apply recorded afterwards','files':rows})
(D/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=1),encoding='utf-8');print('recorded',len(rows))
