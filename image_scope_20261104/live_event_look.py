"""User-authorized: open the event window, visit tabs with a red dot, capture and list what native reads there. No reward clicks."""
from pathlib import Path
import sys,json,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_reward_visual_guard as vg
vg.install()
import project_adapter.event_rewards as ev
g=ev.EventGlowDetector(RoiDetector(profile,list(ev.NAMES)))
title=RoiDetector(profile,['체크_이벤트'])
if not to_field():raise SystemExit('not field')
f=grab();click(705,18);f=settle(f);save('p00',f)
if title.find('체크_이벤트',f,threshold=.95) is None:raise SystemExit('no event window')
def read(f):return {'dots':g.find(ev.DOT,f,ev.DOT_RANGE),'boxes':[(n,tuple(int(v) for v in b)) for n,b in g.boxes(f)]}
print('p00',read(f))
for i,y in enumerate((130,170,207,250,290,330,370),1):
    now=grab()
    if title.find('체크_이벤트',now,threshold=.95) is None:raise SystemExit('window gone')
    click(230,y);time.sleep(1.3);f=grab();save('p%02d'%i,f);print('p%02d'%i,y,read(f),flush=True)
print('field',to_field());os._exit(0)
