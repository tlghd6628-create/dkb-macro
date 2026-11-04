"""User-authorized: leave the instance a TEST entered, after its entry was proved. Exit icon and its confirm only."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_dungeon_map as dm
ids=RoiDetector(profile,['버튼_던전_나가기','체크_던전진행중','버튼_비경_나가기확인','버튼_넘기기_확인','버튼_넘기기_확인2'])
f=grab();save('leave0',f)
print('inside',bool(dm.inside(ids,f)))
hit=ids.find('버튼_던전_나가기',f,threshold=.8)
if not hit or not ids.find('체크_던전진행중',f,threshold=.8):print('no exit icon');sys.stdout.flush();os._exit(2)
click(hit[0],hit[1]);time.sleep(1.2);f=grab();save('leave1',f)
for name in ('버튼_비경_나가기확인','버튼_넘기기_확인','버튼_넘기기_확인2'):
    h=ids.find(name,f,threshold=.9)
    if h:print('confirm',name);click(h[0],h[1]);break
else:print('no confirm');sys.stdout.flush();os._exit(3)
end=time.monotonic()+60
while time.monotonic()<end:
    time.sleep(1.5);f=grab()
    if f.mean()>12 and field(f) and not dm.inside(ids,f):print('field');break
else:print('still not field')
save('leave2',f);sys.stdout.flush();os._exit(0)
