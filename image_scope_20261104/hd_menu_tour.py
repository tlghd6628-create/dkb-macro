"""Open each entry of the full menu, measure that screen with hd_pair.py, and go back. Only opens and leaves screens.
Program closed; game on the field at 1366x768. Places are real pixels on the full menu. Usage: hd_menu_tour.py [NAME...]"""
from pathlib import Path
import subprocess,sys,time,ctypes
import win32gui
D=Path(__file__).parent;PY=sys.executable
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
H=found[0]
MENU={'m_spirit':(1330,150),'m_danger':(1260,150),'m_energy':(1052,220),'m_inner':(983,220),'m_clothes':(1121,220),'m_mount':(1191,220),'m_pet':(1260,220),'m_titlename':(1330,220),
 'm_clan':(983,334),'m_friend':(1052,334),'m_craft':(1330,334),'m_album':(983,403),'m_relic':(1052,403),'m_codex':(1121,403),'m_treasure':(1191,403),'m_achieve':(1260,403),
 'm_quest':(983,517),'m_log':(1052,517),'m_secret':(1121,517),'m_boss':(1191,517),'m_tower':(1260,517),'m_planner':(1330,517),'m_clanwar':(983,586),'m_falling':(1052,586),
 'm_dimension':(1121,586),'m_training':(1191,586),'m_rank':(1260,586),'m_maze':(1330,586),'m_info':(983,150)}
def front():
    fg=win32gui.GetForegroundWindow()
    if fg!=H:
        k=ctypes.windll.kernel32;a=k.GetCurrentThreadId();t=user.GetWindowThreadProcessId(fg,None);c=user.GetWindowThreadProcessId(H,None)
        user.AttachThreadInput(a,t,True);user.AttachThreadInput(a,c,True)
        try:user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.BringWindowToTop(H);user.SetForegroundWindow(H)
        finally:user.AttachThreadInput(a,t,False);user.AttachThreadInput(a,c,False)
        time.sleep(.4)
def click(x,y,wait=1.5):
    front();sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.07);user.mouse_event(4,0,0,0,0);time.sleep(wait)
def pair(name):
    out=subprocess.run([PY,'hd_pair.py',name],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
    lines=(out.stdout or out.stderr).splitlines()
    print(lines[0][:90] if lines else name,flush=True)
only=sys.argv[1:] or list(MENU)
for name in only:
    click(1330,32);click(*MENU[name],2.5)
    pair(name)
    click(35,30,1.5)
    click(35,30,1.5) if name in ('m_clan',) else None
print('done',flush=True)
