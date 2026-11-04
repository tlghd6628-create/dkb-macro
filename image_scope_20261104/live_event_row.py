"""User-authorized: close the left-open window, open the event's mission tab and find which spot claims a dotted row.
Only reward clicks inside the event body are sent; each is preceded by a fresh proof that the event window is open."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_reward_visual_guard as vg
OUT=Path(__file__).parent/'f1'
ids=RoiDetector(profile,['체크_이벤트','버튼_이벤트','버튼_이벤트2','체크_보상받기'])
print('field',to_field(),flush=True)
f=grab();save('ev0',f)
hit=ids.find('버튼_이벤트2',f,threshold=.9) or ids.find('버튼_이벤트',f,threshold=.9)
print('event icon',hit,flush=True)
if not hit:sys.stdout.flush();os._exit(2)
click(hit[0],hit[1]);time.sleep(2.5);f=grab();save('ev1',f)
if not ids.find('체크_이벤트',f,threshold=.95):print('no event window');sys.stdout.flush();os._exit(3)
click(230,343);time.sleep(1.5);f=grab();save('ev2',f)
print('dots',vg.notice_dots(f),flush=True)
def row_state(frame):return float(frame[283:312,568:597].astype('int16').mean())
for label,x,y in (('dot',592,287),('icon',582,300),('row',450,300)):
    f=grab()
    if not ids.find('체크_이벤트',f,threshold=.95):print('window gone before',label);break
    dots=vg.notice_dots(f)
    if not any(abs(dx-592)<=8 and abs(dy-286)<=8 for dx,dy in dots):print('dot gone before',label,dots);break
    click(x,y);seen=False
    for step in range(10):
        time.sleep(.3);g=grab()
        if ids.find('체크_보상받기',g,threshold=.9):seen=True;save('ev_banner_'+label,g);break
    time.sleep(1.0);g=grab();save('ev_after_'+label,g)
    print(label,'banner',seen,'dots',vg.notice_dots(g),flush=True)
    if seen:time.sleep(4.5);break
g=grab();save('ev_end',g);print('final dots',vg.notice_dots(g),flush=True)
print('closed',to_field(),flush=True);save('ev_field',grab());sys.stdout.flush();os._exit(0)
