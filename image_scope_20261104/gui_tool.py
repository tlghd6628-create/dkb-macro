"""User-authorized: look at and click the program's own windows.
Usage: gui_tool.py list | shot TITLE_PART NAME | click TITLE_PART X Y NAME [wait]
Coordinates are relative to the window's top-left corner. Refuses the game window."""
from pathlib import Path
import sys,time,ctypes
import win32gui,win32con,win32process
from PIL import ImageGrab
OUT=Path(__file__).parent/'gui';OUT.mkdir(exist_ok=True)
user=ctypes.windll.user32;user.SetProcessDPIAware()
def rows():
    found=[]
    def each(h,_):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):found.append((h,win32gui.GetWindowText(h),win32gui.GetClassName(h),win32gui.GetWindowRect(h)))
    win32gui.EnumWindows(each,None);return found
def pick(part):
    hits=[r for r in rows() if part in r[1] and r[2]!='UnityWndClass' and r[2]!='Chrome_WidgetWin_1' and not r[2].startswith('HwndWrapper')]
    if not hits:raise SystemExit('no window: '+part)
    return hits[0]
def front(h):
    if win32gui.IsIconic(h):win32gui.ShowWindow(h,win32con.SW_RESTORE);time.sleep(.3)
    if win32gui.GetForegroundWindow()!=h:
        user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(h);time.sleep(.3)
def shot(h,name):
    front(h);rect=win32gui.GetWindowRect(h);im=ImageGrab.grab(rect,all_screens=True);im.save(OUT/(name+'.png'));print(name,im.size,rect)
a=sys.argv[1:]
if a[0]=='list':
    for r in rows():print(r)
elif a[0]=='shot':shot(pick(a[1])[0],a[2])
elif a[0]=='click':
    h=pick(a[1])[0];front(h);l,t,_,_=win32gui.GetWindowRect(h)
    user.SetCursorPos(l+int(a[2]),t+int(a[3]));time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0)
    time.sleep(float(a[5]) if len(a)>5 else 1.0);shot(h,a[4])
