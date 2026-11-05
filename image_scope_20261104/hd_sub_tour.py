"""Open a full menu entry, press its tabs by their words, and measure each with hd_pair.py. Only tabs: words that would
enter, buy or use anything are not in the list. Program closed; game on the field at 1366x768."""
from pathlib import Path
import subprocess,sys,time,ctypes,os
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
sys.stdout.reconfigure(encoding='utf-8')
import bootstrap
import numpy as np,win32gui
from PIL import ImageGrab
import owner_text as text
from owner_start_menu import TITLE_MENUS
import re
text.set_root(bootstrap.A)
D=Path(__file__).parent;PY=sys.executable
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
H=found[0]
TOUR={'quest':((983,517),('일일','주간','서사','메인','일일')),
 'secret':((1121,517),('전래동화','상시비경','일일비경')),
 'boss':((1191,517),('필드보스','레이드','월드보스')),
 'treasure':((1191,403),('타바로 지방','수아리 지방','가모리 지방')),
 'clan':((983,334),('전투','문파 정보','결계지 방어','요신 토벌령','미혹의 정원','신기 쟁탈전')),
 'tower':((1260,517),()),'falling':((1052,586),('입장 구역 선택',))}
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
def shot():
    l,t,r,b=win32gui.GetClientRect(H);x,y=win32gui.ClientToScreen(H,(0,0));return np.asarray(ImageGrab.grab((x,y,x+r,y+b),all_screens=True).convert('RGB'))
def pair(name):
    out=subprocess.run([PY,'hd_pair.py',name],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
    lines=(out.stdout or out.stderr).splitlines()
    print(lines[0][:90] if lines else name,flush=True)
def title_word(image):
    for row in text.read_area(None,image[0:50,20:350]):
        name=re.sub(r'[^가-힣]','',row['text'])
        if name in TITLE_MENUS:return name
    return None
only=sys.argv[1:] or list(TOUR)
for name in only:
    place,tabs=TOUR[name]
    click(1330,32);click(*place,2.5)
    image=shot();rows=text.read_area(None,image,scale=2,bright=True)
    print(name,'words',[r['text'] for r in rows][:40],flush=True)
    pair('s_'+name)
    for tab in tabs:
        hit=text.find(text.read_area(None,shot(),scale=2,bright=True),tab)
        if not hit:print(' no tab',tab,flush=True);continue
        click(hit[0]['rx'],hit[0]['ry'],1.8)
        pair('s_%s_%s'%(name,text.clean(tab)))
    for _ in range(3):
        if not title_word(shot()):break
        click(35,30,1.6)
print('done',flush=True)
sys.stdout.flush();os._exit(0)
