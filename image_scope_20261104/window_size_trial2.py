"""Second trial: do the existing pictures still match a double-size frame scaled back down? Field screen, nothing pressed."""
from pathlib import Path
import sys,time,ctypes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2,win32gui,win32con
from PIL import ImageGrab,Image
from roi_runtime import RoiDetector
from project_adapter import secret_exploration,boss_raid,falling_battle,auto_mode
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
H=found[0];OUT=Path(__file__).parent/'live'
def grab():
    l,t,r,b=win32gui.GetClientRect(H);x,y=win32gui.ClientToScreen(H,(0,0))
    return np.asarray(ImageGrab.grab((x,y,x+r,y+b),all_screens=True).convert('RGB'))
def resize(w,h):
    L,T,R,B=win32gui.GetWindowRect(H);_,_,cw,ch=win32gui.GetClientRect(H)
    win32gui.SetWindowPos(H,0,L,T,w+(R-L-cw),h+(B-T-ch),win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE);time.sleep(2.5)
    return win32gui.GetClientRect(H)[2:]
names=sorted(set(secret_exploration.NAMES)|set(boss_raid.NAMES)|set(falling_battle.NAMES)|set(auto_mode.NAMES))
det=RoiDetector(bootstrap.A/'profiles/DKB',names)
small=grab();Image.fromarray(small).save(OUT/'field_1x.png')
try:
    print(resize(1794,958))
    big=grab();Image.fromarray(big).save(OUT/'field_2x.png')
    downs={'INTER_AREA':cv2.resize(big,(897,479),interpolation=cv2.INTER_AREA),'INTER_LINEAR':cv2.resize(big,(897,479),interpolation=cv2.INTER_LINEAR)}
    hits=[n for n in names if det.find(n,small,threshold=.95)]
    print('1x hits',len(hits),hits)
    for label,d in downs.items():
        got=[n for n in hits if det.find(n,d,threshold=.95)]
        loose=[n for n in hits if det.find(n,d,threshold=.90)]
        extra=[n for n in names if n not in hits and det.find(n,d,threshold=.95)]
        print(label,'kept .95',len(got),'kept .90',len(loose),'lost',[n for n in hits if n not in got],'new',extra)
finally:
    print('restored',resize(897,479))
