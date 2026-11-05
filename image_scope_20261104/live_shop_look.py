"""User-authorized look at the remote shop: open it, open one row's quantity popup, cancel, leave.
Never presses the add-to-cart confirm or the purchase button."""
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
key(0x49);time.sleep(1.5);save('look_inventory',grab())
click(688,62);time.sleep(2.5);save('look_shop',grab())
click(110,171);time.sleep(1.2);save('look_popup',grab())
click(408,302);time.sleep(.8);save('look_after_cancel',grab())
click(21,19);time.sleep(2);f=grab();save('look_left',f);print('field',field(f),flush=True)
sys.stdout.flush();os._exit(0)
