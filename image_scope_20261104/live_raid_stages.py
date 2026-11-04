"""User-authorized: walk raid stages with the arrow only. Never presses match or entry."""
from pathlib import Path
import sys,json,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_image_scope as scope
title=RoiDetector(profile,['체크_보스토벌','버튼_레이드_매칭'])
if not to_field():raise SystemExit('not field')
f=grab();click(874,19);time.sleep(1.0)
if not menu(grab()):raise SystemExit('menu')
f=grab();click(787,320);f=settle(f)
if title.find('체크_보스토벌',f,threshold=.95) is None:raise SystemExit('no boss window')
click(152,53);time.sleep(1.6);f=grab();save('s1',f)
for stage in range(2,6):
    now=grab()
    if title.find('체크_보스토벌',now,threshold=.95) is None or title.find('버튼_레이드_매칭',now,threshold=.9) is None:raise SystemExit('left raid')
    alt=scope._redrawn_image('raid-next');peak=scope.unique_peak(now,alt,(850,70,47,50),.92);print('arrow',peak)
    if not peak:break
    click(peak[1]+6,peak[2]+9);time.sleep(1.5);save('s%d'%stage,grab())
print('field',to_field());sys.stdout.flush();os._exit(0)
