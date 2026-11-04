"""Read-only: how does native code call the detector and what threshold does it pass? Fake service only."""
from pathlib import Path
import sys,json,inspect,dis,types
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from unittest.mock import Mock
from types import SimpleNamespace as S
import numpy as np
from roi_runtime import RoiDetector
import project_adapter.town_services as town
out={}
print('town attrs',[k for k in vars(town) if not k.startswith('__')][:80])
service=town.TownServices(S(project=S(root=bootstrap.A,code='DKB',app_id='DKB'),values={},window=None),Mock(),Mock(),['버튼_축지술_가운데','버튼_귀환','버튼_전체매뉴'])
print('service attrs',{k:type(v).__name__ for k,v in vars(service).items()})
for n in ('button','detect','find','click_hit','point','key','capture','check'):
    fn=getattr(type(service),n,None)
    if fn is not None:
        try:print(n,inspect.signature(fn),getattr(fn,'__module__',None),type(fn).__name__)
        except Exception as e:print(n,'sig?',e)
a=service.actions
cls=type(a);print('actions',cls,cls.__module__,getattr(sys.modules.get(cls.__module__),'__file__',None))
for n,v in vars(cls).items():
    if callable(v):
        try:print(' ',n,inspect.signature(v))
        except Exception:print(' ',n)
print('actions attrs',{k:type(v).__name__ for k,v in vars(a).items()})
# trace find calls from native detect on a saved frame
frame=np.asarray(__import__('PIL.Image',fromlist=['Image']).open(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png').convert('RGB'))
calls=[]
orig=RoiDetector.find
def spy(self,name,f,region=None,threshold=.9,*,candidate_filter=None):
    r=orig(self,name,f,region,threshold,candidate_filter=candidate_filter);calls.append((name,region,threshold,bool(candidate_filter),r));return r
RoiDetector.find=spy
try:
    a.capture=lambda:frame
except Exception as e:print('cap set',e)
try:
    print('detect ->',a.detect('버튼_축지술_가운데',timeout=0.01))
except Exception as e:print('detect exc',type(e).__name__,e)
print('calls',calls)
sys.stdout.flush()
import os;os._exit(0)
