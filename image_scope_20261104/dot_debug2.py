"""Read-only: trace which detector calls native detect_reward makes on the real attendance tab."""
from pathlib import Path
import sys,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_reward_visual_guard as vg
vg.install()
import project_adapter.event_rewards as ev
D=Path(__file__).parent/'live'
base=RoiDetector(bootstrap.A/'profiles/DKB',list(ev.NAMES))
g=ev.EventGlowDetector(base)
calls=[]
cls=ev.EventGlowDetector;orig=cls.find
def spy(self,name,frame,region=None,threshold=.9,*,candidate_filter=None):
    r=orig(self,name,frame,region,threshold,candidate_filter=candidate_filter);calls.append((name,region,threshold,bool(candidate_filter),r));return r
cls.find=spy
oa=cls.available
def spya(self,name,region,frame,hit):
    r=oa(self,name,region,frame,hit);calls.append(('available',name,region,hit[:2],r));return r
cls.available=spya
ob=cls.boxes
def spyb(self,frame,reward_name=None):
    r=ob(self,frame,reward_name);calls.append(('boxes',reward_name,r));return r
cls.boxes=spyb
class Any:
    def __call__(self,*a,**k):return True
    def __getattr__(self,n):return Any()
    def __enter__(self):return self
    def __exit__(self,*a):return False
for n in('p03','p05'):
    calls.clear();f=np.asarray(Image.open(D/(n+'.png')).convert('RGB'))
    class Cap:
        def __call__(self):return f
        def __getattr__(self,m):return lambda *a,**k:True
    ctx=Context(threading.Event(),threading.Event());ctx.wait=lambda s:None
    actions=ev.reward_actions(detector=g,capture=Cap(),inputs=Any(),context=ctx,user_log=print)
    try:print(n,'detect_reward ->',g.detect_reward(Cap(),actions,ctx))
    except BaseException as e:print(n,'exc',type(e).__name__,e)
    for c in calls[:14]:print('  ',c)
    print('  total',len(calls))
import os;sys.stdout.flush();os._exit(0)
