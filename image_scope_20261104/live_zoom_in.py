"""User-requested check of the start zoom: zoom the camera in first, so the start's zoom-out can be seen working."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
sx,sy=win32gui.ClientToScreen(H,(456,180));user.SetCursorPos(sx,sy);time.sleep(.2)
for _ in range(20):user.mouse_event(0x800,0,0,120,0);time.sleep(.05)
time.sleep(.8);save('zoom_before_start',grab());sys.stdout.flush();os._exit(0)
