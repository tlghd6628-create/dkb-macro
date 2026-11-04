"""User-approved trial: can the game take input while it is not the foreground window?
Only opens the inventory and the auto-combat panel, and closes them again. No spending button is ever sent."""
from pathlib import Path
import sys,time,os,json
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_boss_range as r
kernel=ctypes.windll.kernel32
WM_KEYDOWN,WM_KEYUP,WM_MOUSEMOVE,WM_LDOWN,WM_LUP,WM_ACTIVATE,WM_SETFOCUS=0x100,0x101,0x200,0x201,0x202,0x6,0x7
def main_gui():
    found=[]
    win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='TkTopLevel' else None,None)
    return found[0] if found else None
def to_front(hwnd):
    fg=win32gui.GetForegroundWindow()
    if fg==hwnd:return
    a=kernel.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(hwnd,None)
    user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
    try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(hwnd);user.SetForegroundWindow(hwnd)
    finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
    time.sleep(.4)
GUI=main_gui()
def behind():
    to_front(GUI);return win32gui.GetForegroundWindow()!=H
def keylp(vk,up=False):
    sc=user.MapVirtualKeyW(vk,0);return 1|(sc<<16)|((0xC0000000) if up else 0)
def lp(x,y):return (y<<16)|(x&0xffff)
def key(send,vk):
    send(H,WM_KEYDOWN,vk,keylp(vk));time.sleep(.08);send(H,WM_KEYUP,vk,keylp(vk,True))
def mouse(send,x,y):
    send(H,WM_MOUSEMOVE,0,lp(x,y));time.sleep(.05);send(H,WM_LDOWN,1,lp(x,y));time.sleep(.08);send(H,WM_LUP,0,lp(x,y))
post=win32gui.PostMessage;sendm=win32gui.SendMessage
def activate(send):
    send(H,WM_ACTIVATE,1,0);send(H,WM_SETFOCUS,0,0);time.sleep(.1)
def cog_spot(f):
    p=r.cog(f);return (p[1]+12,p[2]+12) if p else (768,449)
def settle_field():
    f=grab()
    if field(f):return True
    to_front(H)
    if r.panel_open(f):click(883,53)
    else:click(876,19)
    time.sleep(1.5)
    if not field(grab()):
        vk=0x49;sc=user.MapVirtualKeyW(vk,0);user.keybd_event(vk,sc,0,0);time.sleep(.06);user.keybd_event(vk,sc,2,0);time.sleep(1.5)
    return field(grab())
results={}
def attempt(name,action,opened):
    if not settle_field():results[name]='field not restored, skipped';print(name,results[name],flush=True);return
    if not behind():results[name]='could not put the game behind';print(name,results[name],flush=True);return
    before=win32gui.GetCursorPos();action();time.sleep(1.6);f=grab();fg=win32gui.GetForegroundWindow()==H
    moved=win32gui.GetCursorPos()!=before;ok=opened(f)
    results[name]={'took':bool(ok),'game_came_forward':fg,'cursor_moved':moved}
    save('bg_'+name,f);print(name,results[name],flush=True)
inventory=lambda f:not field(f)
panel=lambda f:r.panel_open(f)
spot=cog_spot(grab())
print('cog',spot,'gui',GUI,flush=True)
attempt('key_post',lambda:key(post,0x49),inventory)
attempt('key_send',lambda:key(sendm,0x49),inventory)
attempt('key_activate_post',lambda:(activate(post),key(post,0x49)),inventory)
attempt('mouse_post',lambda:mouse(post,*spot),panel)
attempt('mouse_send',lambda:mouse(sendm,*spot),panel)
attempt('mouse_activate_post',lambda:(activate(post),mouse(post,*spot)),panel)
def with_cursor(send):
    # The method MaaFramework lists as "briefly moves, then restores".
    old=win32gui.GetCursorPos();sx,sy=win32gui.ClientToScreen(H,spot);user.SetCursorPos(sx,sy);time.sleep(.06)
    mouse(send,*spot);time.sleep(.1);user.SetCursorPos(*old)
attempt('mouse_cursor_post',lambda:with_cursor(post),panel)
attempt('mouse_activate_cursor_send',lambda:(activate(sendm),with_cursor(sendm)),panel)
print('final field',settle_field(),flush=True)
(Path(__file__).parent/'background_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=1),encoding='utf-8')
sys.stdout.flush();os._exit(0)
