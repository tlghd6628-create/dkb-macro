"""User-authorized: finish the tower run my stop interrupted. Presses only next-floor and the exit shown on failure or end."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
import owner_movement as mv
import owner_image_scope as sc
tower=RoiDetector(profile,['버튼_승천_다음단계','버튼_나가기_승천실패'])
end=time.monotonic()+900;presses=[];last=0
while time.monotonic()<end:
    f=grab()
    def inside(frame):return sc.unique_peak(frame,mv.asset('tower-map-title'),(13,0,57,31),.9) is not None
    if field(f) and not inside(f):
        time.sleep(2);f=grab()
        if field(f) and not inside(f):print('back in field',flush=True);break
    for name in ('버튼_승천_다음단계','버튼_나가기_승천실패'):
        hit=tower.find(name,f,threshold=.93)
        if hit and time.monotonic()-last>2.5:
            time.sleep(.4);again=tower.find(name,grab(),threshold=.93)
            if again:
                click(again[0],again[1]);last=time.monotonic();presses.append(name);print(time.strftime('%H:%M:%S'),'pressed',name,flush=True)
    time.sleep(.8)
else:print('time limit',flush=True)
print('presses',len(presses));save('tower_end',grab());sys.stdout.flush();os._exit(0)
