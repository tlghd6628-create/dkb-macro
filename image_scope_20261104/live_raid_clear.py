"""User-authorized: close the leftover vote-rejected notice with its X, only if that notice is what is showing."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
was=RoiDetector(profile,['버튼_X_레이드부결','체크_레이드_투표부결'])
f=grab();x=was.find('체크_레이드_투표부결',f,threshold=.9);print('notice',bool(x),flush=True)
if x:
    fg=win32gui.GetForegroundWindow()
    if fg!=H:
        a=kernel.GetCurrentThreadId();b=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
        user.AttachThreadInput(a,b,True);user.AttachThreadInput(a,c,True)
        try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
        finally:user.AttachThreadInput(a,b,False);user.AttachThreadInput(a,c,False)
        time.sleep(.4)
    hit=was.find('버튼_X_레이드부결',f,threshold=.9);print('x',hit,flush=True)
    click(*(hit[:2] if hit else (538,207)));time.sleep(1)
f=grab();print('field',field(f),flush=True);sys.stdout.flush();os._exit(0)
