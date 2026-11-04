"""User-authorized: leave an open menu with the game's own exit, until the plain field shows."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
for _ in range(4):
    f=grab()
    if field(f):print('field',True);break
    fg=win32gui.GetForegroundWindow()
    if fg!=H:
        a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
        user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
        try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
        finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
        time.sleep(.3)
    click(876,19);time.sleep(1.6)
else:print('field',field(grab()))
sys.stdout.flush();os._exit(0)
