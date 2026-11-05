"""User-suggested trial: does a bigger game window read better? Program stopped, shop open, nothing pressed in the game.
Saves the shop at the normal size and at twice the size, then puts the window back. Prints only what it measured."""
from pathlib import Path
import sys,time,ctypes,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2,win32gui,win32con,win32api
from PIL import ImageGrab,Image
from tools.ocr_support import get_paddle_engine
from roi_runtime import RoiDetector
user=ctypes.windll.user32;user.SetProcessDPIAware()
found=[]
win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
H=found[0];OUT=Path(__file__).parent/'live'
def grab():
    l,t,r,b=win32gui.GetClientRect(H);x,y=win32gui.ClientToScreen(H,(0,0))
    return np.asarray(ImageGrab.grab((x,y,x+r,y+b),all_screens=True).convert('RGB'))
def resize(w,h):
    L,T,R,B=win32gui.GetWindowRect(H);_,_,cw,ch=win32gui.GetClientRect(H)
    win32gui.SetWindowPos(H,0,L,T,w+(R-L-cw),h+(B-T-ch),win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
    time.sleep(2.5)
    return win32gui.GetClientRect(H)[2:]
eng=get_paddle_engine(bootstrap.A,language='korean');num=get_paddle_engine(bootstrap.A,language='number')
def read(frame,box,scale,e=eng,up=4):
    x,y,w,h=[v*scale for v in box]
    crop=frame[y:y+h,x:x+w]
    crop=cv2.resize(crop,None,fx=up/scale,fy=up/scale,interpolation=cv2.INTER_CUBIC) if up!=scale else crop
    crop=cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT)
    return [(t,round(float(s),2)) for page in e.predict(crop) for t,s in zip(page['rec_texts'],page['rec_scores'])]
BOXES={'잔액':((402,6,44,18),num),'목록':((44,61,153,370),eng),'합계':((428,388,80,20),num),'제목':((36,4,110,30),eng)}
original=win32gui.GetClientRect(H)[2:];print('client',original)
try:
    small=grab();Image.fromarray(small).save(OUT/'size_1x.png')
    for name,(box,e) in BOXES.items():print('1x',name,read(small,box,1,e))
    got=resize(897*2,479*2);print('resized to',got)
    big=grab();Image.fromarray(big).save(OUT/'size_2x.png')
    scale=2 if tuple(got)==(897*2,479*2) else None
    if scale:
        for name,(box,e) in BOXES.items():print('2x',name,read(big,box,2,e))
        down=cv2.resize(big,(897,479),interpolation=cv2.INTER_AREA)
        det=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_나가기','버튼_전체메뉴','버튼_우편','버튼_인벤토리'])
        for n in ('버튼_나가기','버튼_전체메뉴','버튼_우편','버튼_인벤토리'):
            print(n,'1x',bool(det.find(n,small,threshold=.96)),'2x내림',bool(det.find(n,down,threshold=.96)),bool(det.find(n,down,threshold=.9)))
finally:
    print('restored',resize(*original))
