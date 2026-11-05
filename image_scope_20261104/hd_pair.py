"""Measure the real 1366x768 screen, on the proof of the old pictures. Sends no click or key to the game.

Takes the screen at 897x479 and at 1366x768. Every old picture (native and owner) that matches the small frame at
its own threshold is found again on the large one, near where each anchor says, and that crop becomes its new
picture. The two frames also give this screen's layout map. Leave the game on a still screen first. The program must
be stopped, since this resizes the window.

Usage: hd_pair.py SCREEN_NAME        takes one screen (prints what was cut and what was already there)
       hd_pair.py --again SCREEN...  cuts again from a screen's saved frames, keeping everything else
       hd_pair.py --rebuild          makes everything again from the frames saved in hd_frames
"""
from pathlib import Path
import sys,json,time,ctypes,os,zlib
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
import bootstrap
import numpy as np,cv2,win32gui,win32con
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector,_match_ccoeff_normed_masked
import runtime_capture
import owner_hd as hd
user=ctypes.windll.user32;user.SetProcessDPIAware()
P=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(P/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
store=hd.STORE;store.mkdir(parents=True,exist_ok=True)
FRAMES=C/'image_scope_20261104/hd_frames'
def game():
    found=[]
    win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)=='UnityWndClass' else None,None)
    if len(found)!=1:raise SystemExit('window count')
    return found[0]
def resize(H,size):
    L,T,R,B=win32gui.GetWindowRect(H);_,_,cw,ch=win32gui.GetClientRect(H)
    win32gui.SetWindowPos(H,0,0,0,size[0]+(R-L-cw),size[1]+(B-T-ch),win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
    time.sleep(2.2)
    got=tuple(win32gui.GetClientRect(H)[2:])
    if got!=tuple(size):raise SystemExit('size %s'%(got,))
def owner_assets():
    """Every picture the owner modules load, with no fixed place known: searched on the whole small frame."""
    out=[]
    for root in (C/'assets',C/'skill_assets_candidate'):
        if not root.exists():continue
        for path in root.rglob('*.png'):
            if 'hd' in path.parts:continue
            try:image=np.asarray(Image.open(path).convert('RGB'))
            except OSError:continue
            if min(image.shape[:2])>=6 and max(image.shape[:2])<=420 and float(image.std())>=4:out.append((str(path.relative_to(C)),image))
    return out
def best(hay,needle,mask=None):
    if hay.shape[0]<needle.shape[0] or hay.shape[1]<needle.shape[1]:return -1,(0,0)
    s=cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED) if mask is None else _match_ccoeff_normed_masked(hay,needle,mask)
    _,v,_,loc=cv2.minMaxLoc(np.nan_to_num(s,nan=-1));return float(v),loc
def locate(real,needle,x,y,mask=None):
    """Find the old picture on the real frame near its place under each anchor. Returns (score,rx,ry,rule)."""
    big=cv2.resize(needle,None,fx=hd.F,fy=hd.F,interpolation=cv2.INTER_CUBIC)
    bigmask=None if mask is None else cv2.resize(mask,(big.shape[1],big.shape[0]),interpolation=cv2.INTER_NEAREST)
    h,w=big.shape[:2];top=None
    for rule in hd.RULES:
        rx=round(hd.to_real_x(x,rule));ry=round(hd.to_real_y(y))
        l,t=max(0,rx-10),max(0,ry-10)
        v,loc=best(real[t:ry+h+10,l:rx+w+10],big,bigmask)
        if top is None or v>top[0]:top=(v,l+loc[0],t+loc[1],rule)
    return top,(w,h)
def load_rows(name):
    rows=[]
    if (store/name).exists():
        rows=[json.loads(line) for line in (store/name).read_text(encoding='utf-8').splitlines() if line.strip()]
    return rows
def save_rows(name,rows):
    (store/name).write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in rows),encoding='utf-8')
store_roi=json.loads(protected_assets.read_text(P/target['roi'],encoding='utf-8-sig'))
NAMES=[n for n,e in store_roi.items() if e.get('type')=='template' and e.get('target')=='game']
det=RoiDetector(P,NAMES)
ASSETS=owner_assets()
def process(screen,small,small2,real,idx):
    made=[];known=0;weak=[]
    def add(needle,x,y,label,score,bgr,mask=None):
        nonlocal known
        key=hd.key_of(needle)
        if key in idx:known+=1;return
        top,(w,h)=locate(real,needle if not bgr else needle[:,:,::-1],x,y,mask)
        if top[0]<.62:weak.append((label,round(top[0],2)));return
        v,rx,ry,rule=top
        crop=real[ry:ry+h,rx:rx+w].copy()
        if crop.shape[:2]!=(h,w) or float(crop.std())<1:return
        # The file name carries its content, so two PCs cutting one picture at once never collide.
        name='%s_%08x.png'%(key,zlib.crc32(crop.tobytes()));Image.fromarray(crop).save(store/name)
        idx[key]=dict(key=key,file=name,x=rx,y=ry,w=w,h=h,rule=rule,label=label,screen=screen,bgr=bool(bgr),old_score=round(score,3),scaled_score=round(v,3))
        made.append((label,rule,round(v,2)))
    for n in NAMES:
        e=store_roi[n];mask=det.masks.get(n)
        # Both small frames, at the original's default floor, in its own fixed place: a flicker is not proof.
        if det.find(n,small,threshold=.90) and det.find(n,small2,threshold=.90):
            needle=det.templates[n]
            add(needle,e['x'],e['y'],'native:'+n,best(small[e['y']:e['y']+e['h'],e['x']:e['x']+e['w']][:,:,::-1],needle,mask)[0],True,mask)
    for label,image in ASSETS:
        a=best(small,image);b=best(small2,image)
        # These are searched over the whole frame with no fixed place, so a chance look-alike must be ruled out.
        # Worn marks are tiny and sit on the bag's own slots, which is only where they are looked for.
        if a[0]>=.965 and b[0]>=.965 and a[1]==b[1] and (image.shape[0]*image.shape[1]>=200 or 'equipped_badge' in label):
            add(image,a[1][0],a[1][1],'owner:'+label,a[0],False)
    return made,known,weak
def rebuild():
    idx={};maps=[]
    for old in store.glob('*.png'):old.unlink()
    for path in sorted(FRAMES.glob('*_1x.png'),key=lambda p:p.stat().st_mtime):
        screen=path.stem[:-3]
        small=np.asarray(Image.open(path).convert('RGB'));real=np.asarray(Image.open(FRAMES/(screen+'_hd.png')).convert('RGB'))
        made,known,weak=process(screen,small,small,real,idx)
        maps.append(hd.dump_layout(hd.build_layout(small,real,screen)))
        print(screen,'new',len(made),'known',known,'weak',len(weak),flush=True)
    save_rows('index.jsonl',sorted(idx.values(),key=lambda r:r['key']));save_rows('layouts.jsonl',sorted(maps,key=lambda r:r['screen']))
    print('total',len(idx),'screens',len(maps))
def main():
    if sys.argv[1:]==['--rebuild']:return rebuild()
    if sys.argv[1:2]==['--again']:
        rows=load_rows('index.jsonl');idx={r['key']:r for r in rows}
        for screen in sys.argv[2:]:
            small=np.asarray(Image.open(FRAMES/(screen+'_1x.png')).convert('RGB'));real=np.asarray(Image.open(FRAMES/(screen+'_hd.png')).convert('RGB'))
            made,known,weak=process(screen,small,small,real,idx);print(screen,'new',len(made),'known',known,'weak',len(weak))
        save_rows('index.jsonl',sorted(idx.values(),key=lambda r:r['key']));return
    screen=sys.argv[1] if len(sys.argv)>1 else 'screen'
    H=game()
    def grab(size):return runtime_capture.capture(H,dict(target,client_size=list(size)))
    original=tuple(win32gui.GetClientRect(H)[2:])
    resize(H,hd.LOGICAL);small=grab(hd.LOGICAL);small2=grab(hd.LOGICAL)
    resize(H,hd.REAL);real=grab(hd.REAL)
    if original!=hd.REAL:resize(H,original)
    FRAMES.mkdir(exist_ok=True)
    Image.fromarray(small).save(FRAMES/(screen+'_1x.png'));Image.fromarray(real).save(FRAMES/(screen+'_hd.png'))
    rows=load_rows('index.jsonl');idx={r['key']:r for r in rows}
    made,known,weak=process(screen,small,small2,real,idx)
    save_rows('index.jsonl',sorted(idx.values(),key=lambda r:r['key']))
    maps={r['screen']:r for r in load_rows('layouts.jsonl')}
    maps[screen]=hd.dump_layout(hd.build_layout(small,real,screen))
    save_rows('layouts.jsonl',sorted(maps.values(),key=lambda r:r['screen']))
    print(screen,'new',len(made),'known',known,'weak',len(weak),'total',len(idx))
    for row in made:print(' ',row)
    if weak:print(' weak',weak[:20])
main();sys.stdout.flush();os._exit(0)
