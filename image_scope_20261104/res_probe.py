"""User-asked experiment: would a bigger game window help? Resize, capture, compare, restore. Menu navigation only."""
from pathlib import Path
import sys,json,time,os,ctypes
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import cv2
from window_resolution import client_size,physical_coordinates
from tools.ocr_support import get_paddle_engine
from project_adapter import protected_assets
store=json.loads(protected_assets.read_text(profile/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in store.items() if isinstance(e,dict) and e.get('type')=='template']
all_d=RoiDetector(profile,names);plain=RoiDetector.find
BASE=(897,479)
def set_client(w,h):
    with physical_coordinates():
        l,t,r,b=win32gui.GetWindowRect(H);cl,ct,cr,cb=win32gui.GetClientRect(H);dw,dh=(r-l)-(cr-cl),(b-t)-(cb-ct)
        win32gui.SetWindowPos(H,0,max(l,0),max(t,0),w+dw,h+dh,win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
    time.sleep(2.5)
def raw():
    with physical_coordinates():return runtime_capture.printwindow(H)
def exact(f):return {n for n in names if plain(all_d,n,f,None,.9,candidate_filter=None) is not None}
def ocr(img,lang):
    out=[]
    for p in get_paddle_engine(bootstrap.A,language=lang).predict(img):out+=list(zip(p.get('rec_texts',()),[round(s,3) for s in p.get('rec_scores',())]))
    return out
out={}
try:
    if not to_field():raise SystemExit('not field')
    f=raw();print('base size',f.shape,flush=True);Image.fromarray(f).save(OUT/'r_base_field.png')
    click(874,19);time.sleep(1.2);m1=raw();Image.fromarray(m1).save(OUT/'r_base_menu.png');click(874,19);time.sleep(1.2)
    base_field,base_menu=exact(f),exact(m1)
    set_client(1794,958)
    big=raw();print('big size',big.shape,client_size(H),flush=True);Image.fromarray(big).save(OUT/'r_big_field.png')
    if big.shape[:2]==(958,1794):
        sx,sy=win32gui.ClientToScreen(H,(874*2,19*2))
        with physical_coordinates():user.SetCursorPos(sx,sy)
        time.sleep(.1);front();user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(1.5)
        bigm=raw();Image.fromarray(bigm).save(OUT/'r_big_menu.png')
        with physical_coordinates():user.SetCursorPos(sx,sy)
        time.sleep(.1);user.mouse_event(2,0,0,0,0);time.sleep(.06);user.mouse_event(4,0,0,0,0);time.sleep(1.2)
        for label,im,basef,baseset in (('field',big,f,base_field),('menu',bigm,m1,base_menu)):
            for method,flag in (('area',cv2.INTER_AREA),('linear',cv2.INTER_LINEAR)):
                small=cv2.resize(im,BASE,interpolation=flag);got=exact(small)
                print(label,method,'exact now',len(baseset),'after downscale',len(got),'lost',sorted(baseset-got)[:12],'gained',sorted(got-baseset)[:8],flush=True)
        print('text crops: HP/power/top bar',flush=True)
        for name,box in (('top bar',(395,8,125,20)),('power',(0,462,80,16)),('chat',(10,420,190,40))):
            x,y,w,h=box
            a=cv2.resize(f[y:y+h,x:x+w],None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC);b=cv2.resize(big[y*2:(y+h)*2,x*2:(x+w)*2],None,fx=1.5,fy=1.5,interpolation=cv2.INTER_CUBIC)
            print(' ',name,'now',ocr(a,'korean')[:5],'| big',ocr(b,'korean')[:5],flush=True)
finally:
    set_client(*BASE);print('restored',client_size(H),flush=True)
    print('field',to_field(),flush=True);save('r_after',grab())
sys.stdout.flush();os._exit(0)
