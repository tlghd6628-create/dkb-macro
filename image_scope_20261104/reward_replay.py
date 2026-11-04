"""Original native reward flows on real frames with recording inputs and a virtual clock. No game input."""
from pathlib import Path
import sys,json,threading,collections,time as T
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_reward_visual_guard as guard
guard.install()
import project_adapter.event_rewards as ev,project_adapter.mail_rewards as ml
D=Path(__file__).parent/'live';profile=bootstrap.A/'profiles/DKB'
def load(n):return np.asarray(Image.open(D/(n+'.png')).convert('RGB'))
class Rec:
    def __init__(self,log,name='inputs'):self.log=log;self.name=name
    def __getattr__(self,n):return Rec(self.log,self.name+'.'+n)
    def __call__(self,*a,**k):
        if not self.name.endswith('require_ready'):self.log.append((self.name,a,{x:y for x,y in k.items() if x in('bounds',)}))
        return self
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def __bool__(self):return True
class Cap:
    def __init__(self,f):self.f=f;self.n=0
    def __call__(self):self.n+=1;return self.f
    def __getattr__(self,n):return lambda *a,**k:True
def run(label,fn,frame,names,wrap=None):
    log=[];waits=[];clock=[0.];context=Context(threading.Event(),threading.Event())
    real=T.monotonic
    def wait(s):waits.append(round(float(s),3));clock[0]+=float(s);context.checkpoint()
    context.wait=wait;msgs=[]
    det=RoiDetector(profile,names)
    if wrap:det=wrap(det)
    cap=Cap(frame)
    import project_adapter.guide_rewards as gr
    T.monotonic=lambda:clock[0]
    try:
        try:r=fn(enabled=True,detector=det,capture=cap,inputs=Rec(log),context=context,user_log=msgs.append)
        except BaseException as e:r=type(e).__name__+':'+str(e)[:120]
    finally:T.monotonic=real
    print('==',label,'result',r,'virtual',round(clock[0],2),'waits',len(waits),'sum',round(sum(waits),2),'captures',cap.n)
    print(' waits',collections.Counter(waits).most_common(12));print(' inputs',[(a,b) for a,b,_ in log][:40]);print(' msgs',msgs[:40])
run('event static',ev.run_event_rewards,load('d11_event'),list(ev.NAMES),wrap=lambda d:ev.EventGlowDetector(d) if True else d)
run('mail system',ml.run_mail_rewards,load('d10_mail'),list(ml.NAMES))
import os;sys.stdout.flush();os._exit(0)
