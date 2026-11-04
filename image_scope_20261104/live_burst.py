"""User-authorized: claim the pending mail once and record the screens right after it, with timing."""
from pathlib import Path
import sys,json,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
det2=RoiDetector(profile,['체크_우편함','버튼_우편탭_모두받기','체크_우편없음'])
if not to_field():raise SystemExit('not field')
f=grab();click(805,18);f=settle(f);save('m00_open',f)
if det2.find('체크_우편함',f,threshold=.95) is None:raise SystemExit('mail not open')
tabs=[]
hit=det2.find('버튼_우편탭_모두받기',f,threshold=.9);print('claim button',hit)
if hit is None:raise SystemExit('no claim button')
fresh=grab()
if det2.find('체크_우편함',fresh,threshold=.95) is None or det2.find('버튼_우편탭_모두받기',fresh,threshold=.9) is None:raise SystemExit('screen changed')
t0=time.perf_counter();click(hit[0],hit[1]);rows=[]
for i in range(30):
    g=grab();rows.append(round(time.perf_counter()-t0,2));save('m%02d'%(i+1),g);time.sleep(.12)
print(rows,flush=True);os._exit(0)
