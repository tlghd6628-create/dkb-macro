"""Read only: wait for the running daily dungeon to reach its end, then print what the program logged."""
from pathlib import Path
import sys,time,os
LOG=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'vendor/DKB_Auto/logs'/(time.strftime('%Y-%m-%d')+'.log')
offset=LOG.stat().st_size;end=time.time()+float(sys.argv[1])
MARKS=('비경 잔여시간 없음 확인','비경 잔여시간 소진 확인','자동 동작 종료','상태: 정지')
reason='timeout'
while time.time()<end:
    time.sleep(10)
    with LOG.open('rb') as f:f.seek(offset);text=f.read().decode('utf-8','replace')
    hit=next((m for m in MARKS if m in text),None)
    if hit:reason=hit;time.sleep(90);break
with LOG.open('rb') as f:f.seek(offset);text=f.read().decode('utf-8','replace')
rows=[l[11:190] for l in text.splitlines() if (' INFO ' in l or 'WARNING' in l or 'ERROR' in l) and '화면 자료 저장' not in l]
print('reason',reason,time.strftime('%H:%M:%S'))
for row in rows[-45:]:print(row)
sys.stdout.flush();os._exit(0)
