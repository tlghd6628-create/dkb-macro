"""User-requested in the raid: press the AUTO button once, and score what the native flow looks for on this frame."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import cv2
from project_adapter import boss_raid as b
kernel=ctypes.windll.kernel32
d=RoiDetector(profile,[b.ENTERED,*b.AUTO_NAMES,'버튼_나가기'])
f=grab();save('raid_before_auto',f);hay=f[:,:,::-1]
for n in [b.ENTERED,*b.AUTO_NAMES,'버튼_나가기']:
    e=d.entries[n];x,y,w,h=e['x'],e['y'],e['w'],e['h'];r=cv2.matchTemplate(hay,d.templates[n],cv2.TM_CCOEFF_NORMED);_,s,_,at=cv2.minMaxLoc(r)
    here=float(cv2.matchTemplate(hay[max(0,y-4):y+h+4,max(0,x-4):x+w+4],d.templates[n],cv2.TM_CCOEFF_NORMED).max())
    print(n,(x,y,w,h),'at roi',round(here,3),'best',round(float(s),3),at,flush=True)
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.3)
click(800,449);time.sleep(1.2);save('raid_after_auto',grab());print('pressed',flush=True)
sys.stdout.flush();os._exit(0)
