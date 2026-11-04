"""User-approved trial, done again properly after the earlier runs misjudged an open inventory as the field.
Every click needs a proved plain field first, so nothing lands inside the bag. Menus only; a control comes first.
Keys: the game's own I. Mouse: the auto-combat cog."""
from pathlib import Path
import sys,time,os,json
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_boss_range as r,cv2
kernel=ctypes.windll.kernel32
WM_KEYDOWN,WM_KEYUP,WM_MOUSEMOVE,WM_LDOWN,WM_LUP,WM_ACTIVATE,WM_SETFOCUS=0x100,0x101,0x200,0x201,0x202,0x6,0x7
gui=[];win32gui.EnumWindows(lambda h,_:gui.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None);GUI=gui[0]
saved=np.array(Image.open(OUT/'bag_open.png').convert('RGB'))
TABS=saved[44:66,726:880]
def bag(f):return float(cv2.matchTemplate(f[38:72,716:890],TABS,cv2.TM_CCOEFF_NORMED).max())>=.85
def plain(f):return field(f) and not bag(f) and not r.panel_open(f) and r.cog(f) is not None
def front(hwnd):
    fg=win32gui.GetForegroundWindow()
    if fg==hwnd:return
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(hwnd,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(hwnd);user.SetForegroundWindow(hwnd)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
def real_click(x,y):
    sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.08);user.mouse_event(4,0,0,0,0)
def real_key(vk):
    sc=user.MapVirtualKeyW(vk,0);user.keybd_event(vk,sc,0,0);time.sleep(.06);user.keybd_event(vk,sc,2,0)
def tidy():
    """Back to a proved plain field with real input, closing only what is shown to be open."""
    for _ in range(5):
        f=grab()
        if plain(f):return True
        front(H)
        if r.panel_open(f):real_click(883,53)
        elif bag(f):
            real_click(510,107);time.sleep(.5);real_key(0x49)
        else:real_click(876,19)
        time.sleep(1.5)
    return plain(grab())
def lp(x,y):return (y<<16)|(x&0xffff)
def keylp(vk,up=False):
    sc=user.MapVirtualKeyW(vk,0);return 1|(sc<<16)|(0xC0000000 if up else 0)
def msg_key(send,vk):
    send(H,WM_KEYDOWN,vk,keylp(vk));time.sleep(.08);send(H,WM_KEYUP,vk,keylp(vk,True))
def msg_mouse(send,x,y):
    send(H,WM_MOUSEMOVE,0,lp(x,y));time.sleep(.05);send(H,WM_LDOWN,1,lp(x,y));time.sleep(.08);send(H,WM_LUP,0,lp(x,y))
post,sendm=win32gui.PostMessage,win32gui.SendMessage
def activate(send):send(H,WM_ACTIVATE,1,0);send(H,WM_SETFOCUS,0,0);time.sleep(.1)
results={}
def attempt(name,where,action,opened):
    if not tidy():results[name]='plain field not proved, skipped';print(name,results[name],flush=True);return
    front(H if where=='front' else GUI)
    if where=='behind' and win32gui.GetForegroundWindow()==H:results[name]='game would not go behind';print(name,results[name],flush=True);return
    action();time.sleep(1.8);f=grab();results[name]=bool(opened(f));save('bg5_'+name,f);print(name,results[name],flush=True)
if not tidy():print('could not start from a plain field');sys.stdout.flush();os._exit(2)

print('plain',plain(grab()),flush=True)
front(H);f=grab();save('zoom_0',f);sx,sy=win32gui.ClientToScreen(H,(456,180));user.SetCursorPos(sx,sy);time.sleep(.2)
hud_before=f[0:36,600:897].copy()
for step in range(1,6):
    for _ in range(5):user.mouse_event(0x800,0,0,-120,0);time.sleep(.06)
    time.sleep(1.0);g=grab();save('zoom_%d'%(step*5),g);print(step*5,'plain',plain(g),flush=True)
sys.stdout.flush();os._exit(0)
