"""User-authorized: open the auto-hunt settings cog under the skill bar and save what it shows.
Changes no value. Refuses unless the plain field is showing."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
def raise_game():
    fg=win32gui.GetForegroundWindow();print('foreground',repr(win32gui.GetWindowText(fg)),flush=True)
    if fg==H:return True
    a=kernel.GetCurrentThreadId();b=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,b,True);user.AttachThreadInput(a,c,True)
    try:
        user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);r=user.SetForegroundWindow(H)
    finally:
        user.AttachThreadInput(a,b,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4);print('raised',bool(r),win32gui.GetForegroundWindow()==H,flush=True)
    return win32gui.GetForegroundWindow()==H
f=grab();print('field',field(f),flush=True)
if not field(f):save('cog_notfield',f);sys.stdout.flush();os._exit(2)
if not raise_game():sys.stdout.flush();os._exit(3)
click(768,448);time.sleep(1.5);save('cog_open',grab())
sys.stdout.flush();os._exit(0)
