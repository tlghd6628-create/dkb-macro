"""User-authorized look: open the growth menu and press only the breakthrough and awakening subtabs, saving each.
Navigation only. No item or action button is pressed. Returns to the plain field."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
kernel=ctypes.windll.kernel32
d=RoiDetector(profile,['체크_성장','버튼_전체매뉴_성장','버튼_전체매뉴'])
fg=win32gui.GetForegroundWindow()
if fg!=H:
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
f=grab();print('field',field(f),flush=True)
if not field(f):save('tabs_notfield',f);sys.stdout.flush();os._exit(2)
click(875,19);time.sleep(1.2);f=grab();hit=d.find('버튼_전체매뉴_성장',f,threshold=.85);print('menu entry',hit,flush=True)
click(*(hit[:2] if hit else (703,97)));time.sleep(1.8);f=grab();save('tab_enhance',f);print('growth',bool(d.find('체크_성장',f,threshold=.9)),flush=True)
if d.find('체크_성장',f,threshold=.9):
    for name,y in (('tab_break',115),('tab_awaken',146)):
        click(43,y);time.sleep(1.3);save(name,grab())
    click(875,19);time.sleep(1.8)
print('field',field(grab()),flush=True);sys.stdout.flush();os._exit(0)
