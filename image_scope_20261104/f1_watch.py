"""User-authorized real F1 run. `start` sends the program's own F1 once; both modes then only read the log.
Usage: f1_watch.py start|watch SECONDS. Never sends F3: the run keeps going unless it ends by itself."""
from pathlib import Path
import sys,time,ctypes,os
import win32gui,win32con
LOG=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')/'vendor/DKB_Auto/logs'/(time.strftime('%Y-%m-%d')+'.log')
STATE=Path(__file__).parent/'f1'/'watch_offset.txt';STATE.parent.mkdir(exist_ok=True)
user=ctypes.windll.user32
mode,seconds=sys.argv[1],float(sys.argv[2])
if mode=='start':
    found=[]
    win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and '세부설정' in win32gui.GetWindowText(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None)
    for h in found:win32gui.PostMessage(h,win32con.WM_CLOSE,0,0);time.sleep(1.5)
    offset=LOG.stat().st_size
    user.keybd_event(0x70,0,0,0);time.sleep(.06);user.keybd_event(0x70,0,2,0);print('F1 sent',time.strftime('%H:%M:%S'))
else:offset=int(STATE.read_text())
ENDS=('자동 동작 종료','사용자 정지','상태: 정지')
end=time.time()+seconds;ended=False
while time.time()<end and not ended:
    time.sleep(2)
    with LOG.open('rb') as f:f.seek(offset);text=f.read().decode('utf-8','replace')
    ended=any(word in text for word in ENDS)
with LOG.open('rb') as f:f.seek(offset);raw=f.read()
STATE.write_text(str(offset+len(raw)))
rows=[l[11:190] for l in raw.decode('utf-8','replace').splitlines() if (' INFO ' in l or 'WARNING' in l or 'ERROR' in l or 'Error' in l) and '화면 자료 저장' not in l]
for row in rows[:130]:print(row)
print('lines',len(rows),'ended' if ended else 'still running',time.strftime('%H:%M:%S'))
sys.stdout.flush();os._exit(0)
