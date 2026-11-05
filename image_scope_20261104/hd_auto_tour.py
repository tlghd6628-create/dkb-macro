"""Measure the AUTO button in each of its states on the field. Program closed. The only input is that button."""
from pathlib import Path
import subprocess,sys,time,ctypes
import win32gui
D=Path(__file__).parent;PY=sys.executable
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
H=found[0]
def front():
    fg=win32gui.GetForegroundWindow()
    if fg!=H:
        k=ctypes.windll.kernel32;a=k.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
        user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
        try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
        finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
        time.sleep(.4)
def click(x,y,wait=1.5):
    front();sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.07);user.mouse_event(4,0,0,0,0);time.sleep(wait)
def pair(name):
    out=subprocess.run([PY,'hd_pair.py',name],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
    print('\n'.join(l[:90] for l in (out.stdout or out.stderr).splitlines()[:8]),flush=True)
for name in sys.argv[1:]:
    pair(name)
    click(1210,720,2)
