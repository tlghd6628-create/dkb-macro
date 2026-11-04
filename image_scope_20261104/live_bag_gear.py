"""User-authorized: on the open inventory, press only the gear filter and save the list.
Equips, uses and spends nothing. Proof it is open: the bag's own header matches the saved open page."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
was=np.array(Image.open(OUT/'bag_open.png').convert('RGB'))[40:95,710:890].astype('int16')
now=grab();score=float(np.abs(now[40:95,710:890].astype('int16')-was).mean());print('header diff',round(score,1),flush=True)
if score>12:save('bag_not_open',now);sys.stdout.flush();os._exit(2)
click(878,135);time.sleep(1.2);save('bag_gear',grab())
sys.stdout.flush();os._exit(0)
