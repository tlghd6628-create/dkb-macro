"""User-approved trial, last part. Control: the same press without handing the foreground back.
Then: did the panel open and close again when the game lost focus, or never open?"""
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
def press():
    sx,sy=win32gui.ClientToScreen(H,(768,449));user.SetCursorPos(sx,sy);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.08);user.mouse_event(4,0,0,0,0)
out={}
close_panel();to_front(GUI);time.sleep(.6);to_front(H);time.sleep(.4);press();time.sleep(1.5);out['control_stays_in_front']=bool(r.panel_open(grab()));print(out,flush=True)
close_panel();to_front(GUI);time.sleep(.6);to_front(H);time.sleep(.4);press()
seen=[]
for n in range(10):
    time.sleep(.2);seen.append(bool(r.panel_open(grab())))
out['opens_with_game_in_front']=seen;print(out,flush=True)
to_front(GUI);later=[]
for n in range(6):
    time.sleep(.3);later.append(bool(r.panel_open(grab())))
out['after_giving_focus_away']=later;print(out,flush=True)
if later and later[-1]:
    # Can a second press land while it is behind, once a panel is up? Only reads whether the panel survives.
    out['panel_stays_behind']=True
print('field',close_panel(),flush=True)
(Path(__file__).parent/'background_probe4.json').write_text(json.dumps(out,indent=1),encoding='utf-8')
sys.stdout.flush();os._exit(0)
