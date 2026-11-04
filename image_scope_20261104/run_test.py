"""User-authorized: press one TEST button in the program's own settings window and watch the program log.
Usage: run_test.py NAME TAB_Y BTN_X BTN_Y TIMEOUT [stop_on=TEXT]
Stops the wait at the TEST result line, or presses the program's F3 on stop_on text / timeout."""
from pathlib import Path
import sys,time,ctypes,json,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import win32gui,win32con
from PIL import ImageGrab
LOG=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs')/(time.strftime('%Y-%m-%d')+'.log')
OUT=Path(__file__).parent/'gui';OUT.mkdir(exist_ok=True)
user=ctypes.windll.user32;user.SetProcessDPIAware()
def window(part):
    found=[]
    def each(h,_):
        if win32gui.IsWindowVisible(h) and part in win32gui.GetWindowText(h) and win32gui.GetClassName(h)=='TkTopLevel':found.append(h)
    win32gui.EnumWindows(each,None)
    if len(found)!=1:raise SystemExit('window count '+part)
    return found[0]
def front(h):
    if win32gui.IsIconic(h):win32gui.ShowWindow(h,win32con.SW_RESTORE);time.sleep(.3)
    user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(h);time.sleep(.3)
def click(h,x,y):
    l,t,_,_=win32gui.GetWindowRect(h);user.SetCursorPos(l+x,t+y);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0)
name,tab,bx,by,limit=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),float(sys.argv[5])
stop_on=next((a[8:] for a in sys.argv[6:] if a.startswith('stop_on=')),None)
scroll=next((int(a[7:]) for a in sys.argv[6:] if a.startswith('scroll=')),0)
h=window('세부설정');front(h);click(h,78,tab);time.sleep(.7)
if scroll:
    l,t,_,_=win32gui.GetWindowRect(h);user.SetCursorPos(l+600,t+400);time.sleep(.1);user.mouse_event(0x800,0,0,scroll*120,0);time.sleep(.5)
start=LOG.stat().st_size;click(h,bx,by);t0=time.time();sent=False;reason='timeout'
seen=b''
while time.time()-t0<limit:
    time.sleep(1.0)
    with LOG.open('rb') as f:f.seek(start);seen=f.read()
    text=seen.decode('utf-8','replace')
    if '실전 TEST 결과' in text or '실전 TEST 준비 실패' in text:reason='result';break
    if stop_on and stop_on in text:reason='stop_on';break
if reason!='result':
    # The program's own F3 hotkey: same as the user's stop.
    user.keybd_event(0x72,0,0,0);time.sleep(.06);user.keybd_event(0x72,0,2,0);print('F3 sent · '+reason);time.sleep(4)
    with LOG.open('rb') as f:f.seek(start);seen=f.read()
print('==',name,reason,round(time.time()-t0,1),'s')
keep=[l for l in seen.decode('utf-8','replace').splitlines() if (' INFO ' in l or 'WARNING' in l or 'ERROR' in l or 'Error' in l) and '화면 자료 저장' not in l]
for l in keep[:90]:print(l[11:170])
print('lines',len(keep))
sys.stdout.flush();os._exit(0)
