"""Back to preset 1 after a stopped preset run: open skills, open the preset menu, press row 1, close."""
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
def key(vk):user.keybd_event(vk,0,0,0);time.sleep(.06);user.keybd_event(vk,0,2,0)
key(0x4b);time.sleep(1.5);save('preset1_a',grab());click(579,459);time.sleep(1.0);save('preset1_b',grab());click(590,436);time.sleep(1.5);save('preset1_c',grab());key(0x4b);time.sleep(2);f=grab();save('preset1_d',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
