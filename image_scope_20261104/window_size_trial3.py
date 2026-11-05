"""Third trial: how much of the gain does 1.5x keep? 1.5x leaves room for the program window beside the game on 1920 wide."""
from pathlib import Path
import sys,time,ctypes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2,win32gui,win32con
from PIL import ImageGrab,Image
from tools.ocr_support import get_paddle_engine
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
    return tuple(win32gui.GetClientRect(H)[2:])
eng=get_paddle_engine(bootstrap.A,language='korean')
def read(frame,box,scale,up=4):
    x,y,w,h=[round(v*scale) for v in box]
    crop=cv2.resize(frame[y:y+h,x:x+w],None,fx=up/scale,fy=up/scale,interpolation=cv2.INTER_CUBIC)
    crop=cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT)
    return [(t,round(float(s),2)) for page in eng.predict(crop) for t,s in zip(page['rec_texts'],page['rec_scores'])]
names=sorted(set(secret_exploration.NAMES)|set(boss_raid.NAMES)|set(falling_battle.NAMES)|set(auto_mode.NAMES))
det=RoiDetector(bootstrap.A/'profiles/DKB',names);names=[n for n in names if n in det.templates]
small=grab();hits=[n for n in names if det.find(n,small,threshold=.95)]
print('1x list',read(small,(44,61,153,370),1)[:24])
try:
    print(resize(1346,719))
    big=grab();Image.fromarray(big).save(OUT/'size_15x.png')
    print('1.5x list',read(big,(44,61,153,370),1.5)[:24])
    d=cv2.resize(big,(897,479),interpolation=cv2.INTER_AREA)
    print('hits',hits,'kept',[n for n in hits if det.find(n,d,threshold=.95)])
finally:
    print('restored',resize(897,479))
