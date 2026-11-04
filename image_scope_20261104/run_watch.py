"""Read-only: wait on the program log until a run ends or stalls, then print a compact summary.
Usage: run_watch.py MAX_MINUTES [STALL_MINUTES]. Sends no input."""
from pathlib import Path
import os,re,sys,time
ROOT=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')
LOG_DIR=ROOT/'vendor/DKB_Auto/logs'
STATE=Path(__file__).parent/'f1'/'run_watch_offset.txt';STATE.parent.mkdir(exist_ok=True)
ENDS=('자동 동작 종료','사용자 정지','상태: 정지')
NOISE=('퀘스트 상태판정','Paddle 준비 완료','화면 자료 저장')
max_minutes=float(sys.argv[1]);stall_minutes=float(sys.argv[2]) if len(sys.argv)>2 else 12
def log_path():return LOG_DIR/(time.strftime('%Y-%m-%d')+'.log')
path=log_path()
offset=int(STATE.read_text()) if STATE.exists() else path.stat().st_size
if offset>path.stat().st_size:offset=0
rows=[];end=time.time()+max_minutes*60;last_change=time.time();reason='time limit'
while time.time()<end:
    time.sleep(5)
    if log_path()!=path:
        path=log_path();offset=0
        if not path.exists():continue
    with path.open('rb') as f:f.seek(offset);raw=f.read()
    if raw:
        offset+=len(raw)
        for line in raw.decode('utf-8','replace').splitlines():
            if not any(word in line for word in NOISE):
                rows.append(line);last_change=time.time()
            if any(word in line for word in ENDS):reason='ended'
    if reason=='ended':break
    if time.time()-last_change>stall_minutes*60:reason='no new log lines for %g min'%stall_minutes;break
STATE.write_text(str(offset))
levels=[m for m in (re.search(r'레벨=(\d+) · 전투력=(\S+)',r) for r in rows) if m]
print('reason',reason,time.strftime('%H:%M:%S'),'lines',len(rows))
if levels:print('level',levels[-1][1],'power',levels[-1][2])
problems=[r for r in rows if ' WARNING ' in r or ' ERROR ' in r]
print('problems',len(problems))
for r in problems[-14:]:print(r[11:185])
print('--- last lines ---')
for r in [r for r in rows if ' INFO ' in r or ' ERROR ' in r][-22:]:print(r[11:165])
sys.stdout.flush();os._exit(0)
