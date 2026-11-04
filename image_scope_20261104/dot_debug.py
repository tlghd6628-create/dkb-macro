"""Read-only: why does native not take the real dot on the saved attendance and mission frames?"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import numpy as np,cv2
from PIL import Image
from roi_runtime import RoiDetector
import owner_reward_visual_guard as vg
import project_adapter.event_rewards as ev
base=RoiDetector(bootstrap.A/'profiles/DKB',list(ev.NAMES))
original=ev.EventGlowDetector(base)
D=Path(__file__).parent/'live'
print('DOT entry',base.entries[ev.DOT]);print('range',base.entries[ev.REWARD_RANGE])
for n in('p03','p05','p06'):
    f=np.asarray(Image.open(D/(n+'.png')).convert('RGB'))
    print('==',n,'dots',vg.notice_dots(f))
    print(' base find',RoiDetector.find(base,ev.DOT,f,ev.REWARD_RANGE,.9))
    print(' glow find before guard',original.find(ev.DOT,f,ev.REWARD_RANGE))
    for t in(.9,.8,.7,.5):print(' base find t',t,RoiDetector.find(base,ev.DOT,f,ev.REWARD_RANGE,t))
    for c in vg.notice_dots(f):print(' pixels',c,f[c[1],c[0]].tolist(),'rgb entry',base.entries[ev.DOT].get('rgb'),base.entries[ev.DOT].get('tolerance'))
vg.install()
guarded=ev.EventGlowDetector(base)
for n in('p03','p05','p06'):
    f=np.asarray(Image.open(D/(n+'.png')).convert('RGB'))
    h=guarded.find(ev.DOT,f,ev.REWARD_RANGE);print(n,'guarded',h)
    print(' available?',guarded.available(ev.DOT,ev.REWARD_RANGE,f,h) if h else None)
    print(' opened title',RoiDetector(bootstrap.A/'profiles/DKB',['체크_이벤트']).find('체크_이벤트',f,threshold=.95))
import os;sys.stdout.flush();os._exit(0)
