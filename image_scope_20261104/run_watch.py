"""Read-only: wait on the program log until a run ends or stalls, then print a compact summary.
Usage: run_watch.py MAX_MINUTES [STALL_MINUTES]. Sends no input."""
from pathlib import Path
import os,re,sys,time
ROOT=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')
LOG_DIR=ROOT/'vendor/DKB_Auto/logs'
STATE=Path(__file__).parent/'f1'/'run_watch_offset.txt';STATE.parent.mkdir(exist_ok=True)
ENDS=('자동 동작 종료','사용자 정지','상태: 정지')
# Lines a stuck quest keeps printing. They must not count as progress.
NOISE=('퀘스트 상태판정','Paddle 준비 완료','화면 자료 저장','메인퀘 정체','감정 요구 판독 대조','퀘스트 이동·자동사냥 확인','자동 기능 처리 종료 · 다음 퀘스트','메인퀘 시작','퀘스트 행 판독 보류','진행 진단 저장')
max_minutes=float(sys.argv[1]);stall_minutes=float(sys.argv[2]) if len(sys.argv)>2 else 12
def log_path():return LOG_DIR/(time.strftime('%Y-%m-%d')+'.log')
def gui_hung():
    import ctypes,win32gui
    found=[]
    win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and 'DKB · 도깨비' in win32gui.GetWindowText(h) else None,None)
    return bool(found) and bool(ctypes.windll.user32.IsHungAppWindow(found[0]))
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
    if gui_hung():reason='program window not responding';break
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
