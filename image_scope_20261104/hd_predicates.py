"""On saved pairs only, never a game test: call every owner function that takes just a frame, on both sizes of each
screen, and list the ones that answer differently. This is how pixel-level checks tied to the old size are found.
Usage: hd_predicates.py [SCREEN...]"""
from pathlib import Path
import sys,os,inspect,importlib,time,logging
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
sys.stdout.reconfigure(encoding='utf-8')
import bootstrap
import numpy as np
from PIL import Image
import owner_hd as hd
hd.install_reading()
import owner_text
owner_text.set_root(bootstrap.A)
logging.disable(logging.CRITICAL)
SKIP_MODULES=('owner_main','owner_hd','owner_settings','owner_challenge_test','owner_diagnostic','owner_update')
SKIP_WORDS=('save','write','log','install','frame_','capture','grab')
FRAME_NAMES=('frame','f','image','rgb','img','screen','current')
def functions():
    out=[]
    for path in sorted(C.glob('owner_*.py')):
        name=path.stem
        if name.startswith(SKIP_MODULES):continue
        try:module=importlib.import_module(name)
        except Exception as exc:print('skip',name,type(exc).__name__,flush=True);continue
        for fname,fn in vars(module).items():
            if not inspect.isfunction(fn) or fn.__module__!=name or any(w in fname for w in SKIP_WORDS):continue
            try:params=list(inspect.signature(fn).parameters.values())
            except (TypeError,ValueError):continue
            need=[p for p in params if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY,p.POSITIONAL_OR_KEYWORD,p.KEYWORD_ONLY)]
            if len(need)==1 and need[0].name in FRAME_NAMES and need[0].kind!=need[0].KEYWORD_ONLY:out.append((name+'.'+fname,fn))
    return out
def same(a,b):
    if isinstance(a,np.ndarray) or isinstance(b,np.ndarray):return True  # pictures are not verdicts
    if isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)):
        return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):
        return set(a)==set(b) and all(same(a[k],b[k]) for k in a)
    if isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool):return abs(a-b)<=6
    return a==b
def call(fn,frame):
    try:return fn(frame)
    except Exception as exc:return 'raises '+type(exc).__name__
D=C/'image_scope_20261104/hd_frames'
only=set(sys.argv[1:])
funcs=functions();print('functions',len(funcs),flush=True)
wrong={};total=bad=0
for path in sorted(D.glob('*_1x.png')):
    screen=path.stem[:-3]
    if only and screen not in only:continue
    small=np.asarray(Image.open(path).convert('RGB'));real=np.asarray(Image.open(D/(screen+'_hd.png')).convert('RGB'))
    frame=hd.make_frame(real)
    start=time.time();here=[]
    for name,fn in funcs:
        a=call(fn,small);b=call(fn,frame);total+=1
        if not same(a,b):
            bad+=1;here.append(name);wrong.setdefault(name,[]).append((screen,repr(a)[:40],repr(b)[:40]))
    print(screen,'differ',len(here),'%.0fs'%(time.time()-start),flush=True)
print('agree %d/%d'%(total-bad,total))
for name,rows in sorted(wrong.items(),key=lambda kv:-len(kv[1])):
    print(len(rows),name,rows[0])
sys.stdout.flush();os._exit(0)
