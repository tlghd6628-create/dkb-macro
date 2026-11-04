"""User-approved trial, part two. Does the game take window messages when it is in front? And can input work
by borrowing the foreground for one press and handing it straight back? Menus only; no spending button."""
from pathlib import Path
import sys,time,os,json
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_boss_range as r
kernel=ctypes.windll.kernel32
WM_MOUSEMOVE,WM_LDOWN,WM_LUP=0x200,0x201,0x202
gui=[];win32gui.EnumWindows(lambda h,_:gui.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None);GUI=gui[0]
def to_front(hwnd):
    fg=win32gui.GetForegroundWindow()
    if fg==hwnd:return
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(hwnd,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(hwnd);user.SetForegroundWindow(hwnd)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
def lp(x,y):return (y<<16)|(x&0xffff)
def close_panel():
    f=grab()
    if r.panel_open(f):to_front(H);time.sleep(.3);click(883,53);time.sleep(1.2)
    return field(grab())
results={}
p=r.cog(grab());x,y=(p[1]+12,p[2]+12) if p else (768,449);print('cog',(x,y),flush=True)
# 1. Messages with the game in front: separates "needs focus" from "ignores messages".
close_panel();to_front(H);time.sleep(.5)
send=win32gui.PostMessage;send(H,WM_MOUSEMOVE,0,lp(x,y));time.sleep(.05);send(H,WM_LDOWN,1,lp(x,y));time.sleep(.08);send(H,WM_LUP,0,lp(x,y));time.sleep(1.5)
results['message_with_game_in_front']=bool(r.panel_open(grab()));print(results,flush=True)
# 2. Borrow the foreground for one real press, then hand it back, and put the cursor back.
close_panel();to_front(GUI);time.sleep(.5)
old=win32gui.GetCursorPos();start=time.perf_counter()
to_front(H);sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.05);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(.05)
to_front(GUI);user.SetCursorPos(*old);held=time.perf_counter()-start
time.sleep(1.5);f=grab();save('bg_borrow',f)
results['borrow_opened']=bool(r.panel_open(f));results['borrow_ms']=round(held*1000);results['gui_back_in_front']=win32gui.GetForegroundWindow()==GUI;results['cursor_back']=win32gui.GetCursorPos()==old
print(results,flush=True)
# 3. Does the game keep drawing and fighting behind another window?
a=grab();time.sleep(1.2);b=grab();results['still_animating_behind']=float(np.abs(a[::4,::4].astype(int)-b[::4,::4]).mean())>.5
print(results,flush=True);print('field',close_panel(),flush=True)
(Path(__file__).parent/'background_probe2.json').write_text(json.dumps(results,ensure_ascii=False,indent=1),encoding='utf-8')
sys.stdout.flush();os._exit(0)
