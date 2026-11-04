"""Read-only, no input: when the spirit job ends, photograph the game and score the AUTO images for 40 seconds."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
from project_adapter.secret_exploration import AUTO_NAMES
LOG=Path(r'C:\Users\홍이\Downloads\도깨비의 세계\vendor\DKB_Auto\logs')/(time.strftime('%Y-%m-%d')+'.log')
d=RoiDetector(profile,list(AUTO_NAMES));start=LOG.stat().st_size;end=time.time()+1500
print('watching',list(AUTO_NAMES),flush=True)
while time.time()<end:
    time.sleep(1)
    with LOG.open('rb') as f:f.seek(start);text=f.read().decode('utf-8','replace')
    if '자동 기능 완료 · 영기 수련' in text:break
else:
    print('no spirit job');sys.stdout.flush();os._exit(0)
for i in range(9):
    f=grab();save('spirit_return_%d'%i,f)
    print(time.strftime('%H:%M:%S'),i,'field',field(f),{n:(lambda h:None if h is None else h[:2])(d.find(n,f,threshold=.7)) for n in AUTO_NAMES},flush=True)
    time.sleep(5)
sys.stdout.flush();os._exit(0)
