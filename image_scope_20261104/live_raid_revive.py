"""User-requested in the raid: press the revive button, watch what the screen does, and report."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import cv2
kernel=ctypes.windll.kernel32
print('foreground before',repr(win32gui.GetWindowText(win32gui.GetForegroundWindow())),flush=True)
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
print('foreground now',win32gui.GetForegroundWindow()==H,flush=True)
d=RoiDetector(profile,['버튼_보스_거점이동부활','체크_사망상태'])
def state(f):
    hay=f[:,:,::-1];out={}
    for n in d.templates:
        _,s,_,at=cv2.minMaxLoc(cv2.matchTemplate(hay,d.templates[n],cv2.TM_CCOEFF_NORMED));out[n]=(round(float(s),3),at)
    return out
f=grab();print('before',state(f),flush=True)
sx,sy=win32gui.ClientToScreen(H,(448,453));print('screen point',(sx,sy),flush=True)
click(448,453)
for n in range(1,5):
    time.sleep(1.5);f=grab();print(n,state(f),flush=True)
save('revive_after',f)
sys.stdout.flush();os._exit(0)
