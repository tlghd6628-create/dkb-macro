"""User-authorized: press only the exit button on the blessing summon result screen, then report where the game is."""
from pathlib import Path
import sys,time,ctypes,os
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
save('summon_before',grab());click(561,452);time.sleep(2.5);f=grab();save('summon_after',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
