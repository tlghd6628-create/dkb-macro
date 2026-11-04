"""User-approved trial, part three: how long must the foreground be borrowed for one real press to take? Menus only."""
from pathlib import Path
import sys,time,os,json
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_boss_range as r
kernel=ctypes.windll.kernel32
gui=[];win32gui.EnumWindows(lambda h,_:gui.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None);GUI=gui[0]
def to_front(hwnd):
    fg=win32gui.GetForegroundWindow()
    if fg==hwnd:return
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(hwnd,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(hwnd);user.SetForegroundWindow(hwnd)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
def close_panel():
    if r.panel_open(grab()):to_front(H);time.sleep(.4);click(883,53);time.sleep(1.2)
    return field(grab())
x,y=768,449;results=[]
for settle,hold in ((.1,.1),(.2,.1),(.3,.1),(.5,.15),(.8,.2)):
    close_panel();to_front(GUI);time.sleep(.6);old=win32gui.GetCursorPos();start=time.perf_counter()
    to_front(H);time.sleep(settle);sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.08);user.mouse_event(2,0,0,0,0);time.sleep(.08);user.mouse_event(4,0,0,0,0);time.sleep(hold)
    to_front(GUI);user.SetCursorPos(*old);ms=round((time.perf_counter()-start)*1000);time.sleep(1.5)
    row={'settle':settle,'hold':hold,'ms':ms,'opened':bool(r.panel_open(grab()))};results.append(row);print(row,flush=True)
print('field',close_panel(),flush=True)
(Path(__file__).parent/'background_probe3.json').write_text(json.dumps(results,indent=1),encoding='utf-8')
sys.stdout.flush();os._exit(0)
