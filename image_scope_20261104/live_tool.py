"""User-authorized live collection: capture the game with the program's own capture path,
optionally one navigation key or click first. Refuses unless the exact game window is the target.
Usage: live_tool.py NAME [key VK | click X Y | esc] [wait_seconds]"""
from pathlib import Path
import sys,json,time,ctypes,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,win32gui,win32process,win32con
from PIL import Image
from project_adapter import protected_assets
import runtime_capture
OUT=Path(__file__).parent/'live';OUT.mkdir(exist_ok=True)
GAME='도깨비의세계'
def game():
    found=[]
    def each(h,_):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h).startswith(GAME):found.append(h)
    win32gui.EnumWindows(each,None)
    found=[w for w in found if win32gui.GetClassName(w)=='UnityWndClass']
    if len(found)!=1:raise SystemExit('game window count %d'%len(found))
    return found[0]
user=ctypes.windll.user32
def front(h):
    if win32gui.GetForegroundWindow()!=h:
        user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0)
        win32gui.SetForegroundWindow(h);time.sleep(.25)
    if win32gui.GetForegroundWindow()!=h:raise SystemExit('game not foreground')
def key(h,vk):
    front(h);sc=user.MapVirtualKeyW(vk,0)
    user.keybd_event(vk,sc,0,0);time.sleep(.06);user.keybd_event(vk,sc,2,0)
def click(h,x,y):
    front(h);sx,sy=win32gui.ClientToScreen(h,(x,y));old=win32gui.GetCursorPos()
    user.SetCursorPos(sx,sy);time.sleep(.08)
    user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(.05)
def shot(h,name):
    profile=bootstrap.A/'profiles/DKB'
    target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
    f=runtime_capture.capture(h,target)
    Image.fromarray(f).save(OUT/(name+'.png'));print(name,f.shape,round(float(f.mean()),1));return f
a=sys.argv[1:];h=game()
if win32gui.IsIconic(h):
    win32gui.ShowWindow(h,win32con.SW_RESTORE);time.sleep(1.5)
if a[0]=='__minimize':
    win32gui.ShowWindow(h,win32con.SW_MINIMIZE);print('minimized');sys.stdout.flush();os._exit(0)
rect=win32gui.GetClientRect(h);print('client',rect[2],rect[3],'title',win32gui.GetWindowText(h))
wait=1.2
need=[x[5:] for x in a if x.startswith('need=')];a=[x for x in a if not x.startswith('need=')]
if need:
    from roi_runtime import RoiDetector
    profile=bootstrap.A/'profiles/DKB';det=RoiDetector(profile,need)
    target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
    now=runtime_capture.capture(h,target)
    miss=[n for n in need if det.find(n,now,threshold=.9) is None]
    if miss:
        Image.fromarray(now).save(OUT/(a[0]+'_refused.png'));print('REFUSED before input · missing',miss);sys.stdout.flush();os._exit(3)
if len(a)>1:
    if a[1]=='key':key(h,int(a[2],0));wait=float(a[3]) if len(a)>3 else wait
    elif a[1]=='click':click(h,int(a[2]),int(a[3]));wait=float(a[4]) if len(a)>4 else wait
    elif a[1]=='esc':key(h,0x1b);wait=float(a[2]) if len(a)>2 else wait
    time.sleep(wait)
shot(h,a[0])
import os;sys.stdout.flush();os._exit(0)
