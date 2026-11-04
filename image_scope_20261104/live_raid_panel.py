"""User-requested in the raid: open the auto-combat panel, read both settings, set them free if they are not, close it."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_boss_range as r
kernel=ctypes.windll.kernel32
def fore():
    fg=win32gui.GetForegroundWindow()
    if fg==H:return
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.3)
def wheel():
    sx,sy=win32gui.ClientToScreen(H,(760,260));user.SetCursorPos(sx,sy);time.sleep(.15)
    for _ in range(12):user.mouse_event(0x800,0,0,-120,0);time.sleep(.05)
    time.sleep(.5)
fore();f=grab();peak=r.cog(f);print('cog',peak,flush=True)
click(*((peak[1]+12,peak[2]+12) if peak else (768,449)));time.sleep(1.2);opened=r.panel_open(grab());print('panel',opened,flush=True)
if not opened:save('raid_no_panel',grab());sys.stdout.flush();os._exit(2)
fore();wheel();f=grab();save('raid_panel',f);state=r.read(f);print('state',state,'high',r.shows(f,'high'),'low',r.shows(f,'low'),flush=True)
if state and state['fixed']:
    left,right,y=r.locate(f)['fixed'];click(left,y);time.sleep(.6);print('fixed off',r.read(grab()),flush=True)
f=grab()
if state and not r.shows(f,'high'):
    y=r.slider_y(f);x=r.handle(f);sx,sy=win32gui.ClientToScreen(H,(x,y));ex,_=win32gui.ClientToScreen(H,(r.SLIDER_RIGHT,y))
    user.SetCursorPos(sx,sy);time.sleep(.12);user.mouse_event(2,0,0,0,0);time.sleep(.08)
    for n in range(1,13):user.SetCursorPos(sx+(ex-sx)*n//12,sy);time.sleep(.025)
    time.sleep(.08);user.mouse_event(4,0,0,0,0);time.sleep(.5);print('high now',r.shows(grab(),'high'),flush=True)
click(760,448);time.sleep(1.0);f=grab();save('raid_panel_closed',f);print('closed',not r.panel_open(f),flush=True)
sys.stdout.flush();os._exit(0)
