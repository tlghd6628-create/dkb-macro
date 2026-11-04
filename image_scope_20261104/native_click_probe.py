"""Original native detect/click and town flow with the new layer. Saved frames, fake inputs; no game."""
from pathlib import Path
import sys,json,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_image_scope as scope
scope.install()
from project_adapter.sleep_mode import SleepModeActions
import project_adapter.town_services as town
import project_adapter.main_quest as mq
D=Path(__file__).resolve().parent
modal=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261104T014134Z-2877466c/screen.png').convert('RGB'))
mapf=np.asarray(Image.open(D/'map_frame_897x479.png').convert('RGB'))
c=bootstrap.A/'logs/scene-corpus/20261104';plain=np.asarray(Image.open(next(c.glob('20261104T104142-*'))/'screen.png').convert('RGB'))
d=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_축지술_가운데','버튼_지도_축지술','버튼_보스_축지술','버튼_귀환','버튼_전체매뉴'])
for fn,f,names in(('modal',modal,['버튼_축지술_가운데','버튼_지도_축지술','버튼_보스_축지술']),('map',mapf,['버튼_지도_축지술','버튼_보스_축지술','버튼_축지술_가운데']),('plain',plain,['버튼_축지술_가운데','버튼_귀환','버튼_전체매뉴'])):
    print(fn,{n:d.find(n,f) for n in names})
ctx=Context(threading.Event(),threading.Event());clicks=[]
class Inputs:
    def __init__(self,name='inputs'):self.name=name
    def __getattr__(self,n):return Inputs(self.name+'.'+n)
    def __call__(self,*a,**k):
        if not self.name.endswith('require_ready'):clicks.append((self.name,a,k))
        return self
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def __iter__(self):return iter(())
    def __bool__(self):return True
class Cap:
    def __init__(self,get):self.get=get
    def __call__(self):return self.get()
    def require_ready(self,*a,**k):return True
    def __getattr__(self,n):return lambda *a,**k:True
act=SleepModeActions(d,Cap(lambda:modal),ctx,Inputs())
hit=act.detect('버튼_축지술_가운데',timeout=.2);print('detect',hit)
print('click ret',act.click('버튼_축지술_가운데',hit,pre_wait=0));print('inputs',clicks)
clicks.clear();calls=[];script=iter([plain]+[modal]*5+[plain]*40)
current=[plain]
class Replay(town.TownServices):
    def __init__(self,adapter,c,inputs,names):
        super().__init__(adapter,c,inputs,names)
        self.capture=Cap(lambda:current[0]);self.actions.capture=self.capture
        calls.append(('names',list(names)))
    def key(self,code):
        calls.append(('key',code))
        if code==36:current[0]=modal
    def click_hit(self,hit):
        calls.append(('click_hit',hit));current[0]=plain
    def wait_menu(self,*a,**k):calls.append(('wait_menu',));return True
    def wake(self):calls.append(('wake',))
adapter=S(project=S(root=bootstrap.A,code='DKB',app_id='DKB'),values={},mode='sub_quest',window=None,status=None)
try:
    with patch.object(town,'TownServices',Replay):r=town.run_town_return(adapter,ctx,Inputs())
    print('town return',repr(r))
except BaseException as e:print('town exc',type(e).__name__,e)
print('calls',calls);print('inputs',clicks)
slots=mq.StateROIs(bootstrap.A/'profiles/DKB',mode='sub_quest');print('slots',type(slots.entries) if hasattr(slots,'entries') else None,list(getattr(slots,'by_key',{}))[:40])
print('match',slots.match('skip',plain))
print('slot attrs',[k for k in vars(slots)][:20])
k=next(iter(slots.by_key));print(k,slots.by_key[k])
import os;sys.stdout.flush();os._exit(0)
