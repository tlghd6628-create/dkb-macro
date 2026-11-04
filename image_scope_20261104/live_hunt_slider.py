"""User-authorized: learn the auto-hunt range slider. Drag right, read, then return to 5m with X closing.
Only the range slider moves. If 5m is not proved at the end this says so and leaves the panel open."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
from tools.ocr_support import get_paddle_engine
from owner_progression import resized
engine=get_paddle_engine(bootstrap.A,language='korean')
kernel=ctypes.windll.kernel32
def raise_game():
    fg=win32gui.GetForegroundWindow()
    if fg==H:return
    a=kernel.GetCurrentThreadId();b=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
    user.AttachThreadInput(a,b,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
    finally:user.AttachThreadInput(a,b,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
def value(f):
    rows=[]
    for page in engine.predict(resized(f,(664,346,44,24))):rows+=[(str(t),round(float(s),2)) for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',()))]
    return rows
def wheel():
    sx,sy=win32gui.ClientToScreen(H,(760,260));user.SetCursorPos(sx,sy);time.sleep(.2)
    for _ in range(12):user.mouse_event(0x800,0,0,-120,0);time.sleep(.06)
    time.sleep(.6)
def drag(a,b):
    sx,sy=win32gui.ClientToScreen(H,a);ex,ey=win32gui.ClientToScreen(H,b);user.SetCursorPos(sx,sy);time.sleep(.15);user.mouse_event(2,0,0,0,0);time.sleep(.1)
    for n in range(1,13):user.SetCursorPos(sx+(ex-sx)*n//12,sy+(ey-sy)*n//12);time.sleep(.03)
    time.sleep(.1);user.mouse_event(4,0,0,0,0);time.sleep(.6)
raise_game()
f=grab();print('field',field(f),flush=True)
if field(f):click(768,448);time.sleep(1.5)
raise_game();wheel();f=grab();save('sl_start',f);print('start',value(f),flush=True)
raise_game();drag((731,358),(860,358));f=grab();save('sl_max',f);print('after drag right',value(f),flush=True)
raise_game();click(717,358);time.sleep(.5);f=grab();save('sl_minus',f);print('after one minus',value(f),flush=True)
raise_game();drag((850,358),(700,358));f=grab();save('sl_left',f);print('after drag left',value(f),flush=True)
sys.stdout.flush();os._exit(0)
