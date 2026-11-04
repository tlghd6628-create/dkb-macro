"""User-authorized: on the open energy page, press only its four tabs and save what each state looks like.
Every press is preceded by a fresh proof that the energy page is open. Sends no spending input."""
from pathlib import Path
import sys,time,os
src=(Path(__file__).parent/'live_collect.py').read_text(encoding='utf-8').split('\nok=True\n')[0]
sys.argv=[__file__];exec(compile(src,str(Path(__file__).parent/'live_collect.py'),'exec'))
OUT=Path(__file__).parent/'f1'
ids=RoiDetector(profile,['체크_전체매뉴_기운발현','버튼_기운발현_기운발현','버튼_기운발현_기운돌파'])
def page(f):return ids.find('체크_전체매뉴_기운발현',f,threshold=.95)
f=grab();print('page',bool(page(f)),flush=True)
if not page(f):sys.stdout.flush();os._exit(2)
for name,y in (('e_life',54),('e_dawn',92),('e_dream',130),('e_flame',168),('e_life2',54)):
    f=grab()
    if not page(f):print('page gone',name);break
    click(57,y);time.sleep(1.6);g=grab();save(name,g)
    print(name,'action',bool(ids.find('버튼_기운발현_기운발현',g,threshold=.9)),'break',bool(ids.find('버튼_기운발현_기운돌파',g,threshold=.9)),flush=True)
print('closed',to_field(),flush=True);save('e_after',grab());sys.stdout.flush();os._exit(0)
