"""User-authorized live run of the original native reward function through the new flow layer.
Input is a small shim (not the product's backend), so this checks recognition and flow, not the whole product.
Usage: live_native.py mail|event [plain]"""
from pathlib import Path
import sys,json,time,os,threading,logging,contextlib
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
mode=sys.argv[1];plain_run=len(sys.argv)>2
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',stream=sys.stdout)
from biol_base.session import Context
import owner_image_scope as scope,owner_reward_visual_guard as vg,owner_reward_flow as flow
scope.install();vg.install()
import project_adapter.event_rewards as ev,project_adapter.mail_rewards as ml
class Inputs:
    held=()
    def click(self,x,y,bounds=None,before_down=None,**k):
        if before_down:before_down()
        print(' CLICK',x,y,flush=True);click(x,y)
    def key(self,vk,*a,**k):key(vk)
    def transaction(self):return contextlib.nullcontext()
    def move(self,x,y):
        sx,sy=win32gui.ClientToScreen(H,(x,y));user.SetCursorPos(sx,sy)
    def down(self,*a):user.mouse_event(2,0,0,0,0)
    def up(self,*a):user.mouse_event(4,0,0,0,0)
    def __getattr__(self,n):
        class Any:
            def __call__(self,*a,**k):return True
            def __getattr__(self,m):return Any()
        return Any()
class Cap:
    def __call__(self):return grab()
    def __getattr__(self,n):return lambda *a,**k:True
if not to_field():raise SystemExit('not field')
ctx=Context(threading.Event(),threading.Event())
logs=[]
def user_log(t):print(' LOG',t,flush=True)
if mode=='mail':fn,key_,names=ml.run_mail_rewards,'mail',list(ml.NAMES)
else:fn,key_,names=ev.run_event_rewards,'event',list(ev.NAMES)
d=RoiDetector(profile,names)
if mode=='event':d=ev.EventGlowDetector(d)
kw=dict(enabled=True,detector=d,capture=Cap(),inputs=Inputs(),context=ctx,user_log=user_log)
ad=type('A',(),{})()
t0=time.perf_counter()
if plain_run:r=fn(**kw)
else:r=flow.tracked(key_,fn,ad,(),kw)
print('result',r,'outcome',getattr(ad,'_owner_reward_last_outcome',None),'seconds',round(time.perf_counter()-t0,1),flush=True)
print('field',to_field(),flush=True);save('n_after_'+mode,grab())
os._exit(0)
