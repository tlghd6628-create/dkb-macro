"""Real raid frame through the original RaidFlow with fake inputs: what does it ask the detector, in order?"""
from pathlib import Path
import sys,os,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,numpy as np
from types import SimpleNamespace as S
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_image_scope as scope
import project_adapter.boss_raid as raid,project_adapter.town_services as town
frame=np.array(Image.open(Path(__file__).parent/'live/e16_boss_raid.png').convert('RGB'))
calls=[];inner=RoiDetector.find
def spy(self,name,f,region=None,threshold=.9,*,candidate_filter=None):
    r=inner(self,name,f,region,threshold,candidate_filter=candidate_filter);calls.append((name,region,threshold,r[:2] if r else None));return r
RoiDetector.find=spy
scope.install()
class Any:
    def __init__(self,log=None,n='in'):self.log=log if log is not None else [];self.n=n
    def __getattr__(self,m):return Any(self.log,self.n+'.'+m)
    def __call__(self,*a,**k):
        if self.n.endswith(('click','key')):self.log.append((self.n,a[:2]))
        return self
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def __bool__(self):return True
class Cap:
    def __call__(self):return frame
    def __getattr__(self,n):return lambda *a,**k:True
ctx=Context(threading.Event(),threading.Event());ctx.wait=lambda s:None
inputs=Any()
orig=town.TownServices.__init__
adapter=S(project=S(root=bootstrap.A,code='DKB',app_id='DKB'),values={},window=Any(),mode='sub_quest',exit_sleep_mode=lambda *a:None,status=Any(),input_backend='fake',hwnd=0,notifier=Any(),notifications=Any())
import project_adapter.boss_raid as br
flow=None
try:
    flow=raid.RaidFlow(adapter,ctx,inputs);print('flow attrs',[k for k in vars(flow)][:12])
    for k in ('capture','service'):
        if hasattr(flow,k):print(k,type(getattr(flow,k)))
    flow.service.capture=Cap() if hasattr(flow,'service') else None
    if hasattr(flow,'capture'):flow.capture=Cap()
    print('find 1단계',flow.find('체크_레이드_1단계',frame))
    print(calls[-6:]);calls.clear()
    print('find next',flow.find(raid.NEXT,frame));print(calls[-3:]);calls.clear()
    try:print('detect',flow.detect('체크_레이드_1단계',1))
    except BaseException as e:print('detect exc',type(e).__name__,e)
    print(calls[-6:])
except BaseException as e:
    import traceback;traceback.print_exc(file=sys.stdout)
sys.stdout.flush();os._exit(0)
