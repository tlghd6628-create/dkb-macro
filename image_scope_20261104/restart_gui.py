"""Normal close of the program (never the game), wait for its shutdown line, then optional relaunch and settings open."""
from pathlib import Path
import sys,time,ctypes,subprocess,os
import win32gui,win32con
R=Path(r'C:\Users\홍이\Downloads\도깨비의 세계');LOG=R/'vendor/DKB_Auto/logs'/(time.strftime('%Y-%m-%d')+'.log')
user=ctypes.windll.user32;user.SetProcessDPIAware()
def tk(part):
    found=[]
    def each(h,_):
        if win32gui.IsWindowVisible(h) and part in win32gui.GetWindowText(h) and win32gui.GetClassName(h)=='TkTopLevel':found.append(h)
    win32gui.EnumWindows(each,None);return found
if sys.argv[1]=='close':
    size=LOG.stat().st_size
    for part in ('세부설정','DKB · 도깨비'):
        for h in tk(part):win32gui.PostMessage(h,win32con.WM_CLOSE,0,0);time.sleep(1.2)
    end=time.time()+40
    while time.time()<end:
        with LOG.open('rb') as f:f.seek(size);t=f.read().decode('utf-8','replace')
        if 'shutdown complete' in t:print('shutdown complete');break
        time.sleep(.5)
    else:print('NO shutdown line');print(t[-400:])
    print('windows left',len(tk('DKB · 도깨비')))
else:
    size=LOG.stat().st_size
    subprocess.Popen([str(R/'DKB_개발용.exe')],cwd=str(R))
    end=time.time()+40
    while time.time()<end and not tk('DKB · 도깨비'):time.sleep(.5)
    time.sleep(6);h=tk('DKB · 도깨비')[0]
    user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(h);time.sleep(.3)
    l,t,_,_=win32gui.GetWindowRect(h);user.SetCursorPos(l+445,t+384);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(1.5)
    end=time.time()+130
    while time.time()<end:
        with LOG.open('rb') as f:f.seek(size);t=f.read().decode('utf-8','replace')
        if 'OCR 초기화' in t:print('ocr ready');break
        time.sleep(1)
    print('settings',bool(tk('세부설정')));print([x[11:110] for x in t.splitlines() if 'OCR' in x or '오류' in x or 'Traceback' in x or 'Error' in x][:8])
sys.stdout.flush();os._exit(0)
