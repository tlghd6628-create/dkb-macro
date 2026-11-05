"""User-authorized navigation-only frame collection. Every click is preceded by a fresh proof of the
screen it belongs to, and each step waits for the screen to settle. Never presses commit buttons."""
from pathlib import Path
import sys,json,time,ctypes,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,win32gui,win32con
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
import runtime_capture
import owner_movement as m
import owner_window_scale
owner_window_scale.install()
OUT=Path(__file__).parent/'live';OUT.mkdir(exist_ok=True)
profile=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
det=RoiDetector(profile,['버튼_전체매뉴','버튼_X','버튼_나가기','버튼_AUTO_활성2','버튼_AUTO_비활성2','버튼_AUTO_일시정지','버튼_우편','버튼_인벤토리'])
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' and win32gui.GetWindowText(h).startswith('도깨비의세계') else None,None)
if len(found)!=1:raise SystemExit('window count')
H=found[0];user=ctypes.windll.user32
if win32gui.IsIconic(H):win32gui.ShowWindow(H,win32con.SW_RESTORE);time.sleep(1.5)
def grab():return runtime_capture.capture(H,target)
def front():
    if win32gui.GetForegroundWindow()!=H:
        user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);win32gui.SetForegroundWindow(H);time.sleep(.25)
    if win32gui.GetForegroundWindow()!=H:raise SystemExit('game not foreground')
def click(x,y):
    front();sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy);time.sleep(.08);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0)
def key(vk):
    front();sc=user.MapVirtualKeyW(vk,0);user.keybd_event(vk,sc,0,0);time.sleep(.06);user.keybd_event(vk,sc,2,0)
def has(name,f):return det.find(name,f,threshold=.93) is not None
def field(f):
    # Top icons plus an undimmed HUD: no window of any kind is open.
    return has('버튼_전체매뉴',f) and has('버튼_우편',f) and has('버튼_인벤토리',f) and not m.hud_dimmed(f) and not has('버튼_X',f)
def menu(f):return has('버튼_X',f) and has('버튼_우편',f)
def settle(previous,seconds=9,least=1.2):
    """Wait until the screen changed from `previous` and two samples of the top bar agree."""
    end=time.monotonic()+seconds;start=time.monotonic();last=None
    while time.monotonic()<end:
        f=grab()
        if f.mean()>12 and last is not None and time.monotonic()-start>=least:
            changed=np.abs(f[::4,::4].astype('int16')-previous[::4,::4]).mean()>6
            if changed and np.abs(f[:40,:400].astype('int16')-last[:40,:400]).mean()<4:return f
        last=f;time.sleep(.3)
    return grab()
def to_field():
    for _ in range(5):
        f=grab()
        if field(f):return True
        if menu(f):click(874,19)
        elif has('버튼_나가기',f):click(875,20)
        else:key(0x1b)
        time.sleep(1.6)
        f2=grab()
        if field(f2):return True
    return field(grab())
def save(name,f):Image.fromarray(f).save(OUT/(name+'.png'));print(' saved',name,round(float(f.mean()),1),flush=True)
def visit(name,x,y,subs=()):
    if not to_field():print('STOP not field before',name);return False
    f=grab();click(874,19);time.sleep(1.0);f=grab()
    if not menu(f):print('STOP menu not open',name);save('stop_'+name,f);return False
    click(x,y);f=settle(f);save(name,f)
    for sub,sx,sy in subs:
        before=grab()
        if field(before) or menu(before):print('STOP window gone',sub);break
        click(sx,sy);time.sleep(1.4);save(sub,grab())
    return to_field()
def top(name,x,y):
    if not to_field():print('STOP not field before',name);return False
    f=grab();click(x,y);f=settle(f);save(name,f);return to_field()
ok=True
plan=json.loads(sys.argv[1])
for row in plan:
    if row[0]=='top':ok=top(row[1],row[2],row[3])
    else:ok=visit(row[1],row[2],row[3],[tuple(s) for s in row[4:]])
    if not ok:print('ABORT at',row[1]);break
print('field at end',field(grab()),flush=True)
os._exit(0 if ok else 2)
