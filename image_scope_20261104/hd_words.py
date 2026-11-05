"""Read the words on every old picture, so a picture with no new cut can be found by them on the real screen.
Writes assets/hd/words.jsonl. Sends nothing to the game. Anything that spends is left out and stays with its picture,
as are words too short or too common to name one thing."""
from pathlib import Path
import sys,json,os,re
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
sys.stdout.reconfigure(encoding='utf-8')
import bootstrap
import numpy as np,cv2
from PIL import Image
from project_adapter import protected_assets
from roi_runtime import RoiDetector
from tools.ocr_support import get_paddle_engine
import owner_hd as hd
import owner_text as text
P=bootstrap.A/'profiles/DKB'
target=json.loads(protected_assets.read_text(P/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
roi=json.loads(protected_assets.read_text(P/target['roi'],encoding='utf-8-sig'))
names=[n for n,e in roi.items() if e.get('type')=='template' and e.get('target')=='game']
det=RoiDetector(P,names)
engine=get_paddle_engine(bootstrap.A,language='korean')
def words_of(image):
    big=cv2.resize(image,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
    big=cv2.copyMakeBorder(big,24,24,24,24,cv2.BORDER_REPLICATE)
    found=[]
    for page in engine.predict(big):
        found+=[(str(t),float(s)) for t,s in zip(page.get('rec_texts',()),page.get('rec_scores',()))]
    return found
SPENDS=re.compile('구매|거래소|분해|상자열기|결정|봉인해제|성장|가호|일괄|쿠폰|계정|모두등록|완성|강화|돌파|각성|소환|등록')
# Too common to name one thing anywhere near it. A button's own word in its own small place is exact enough.
NEVER={'보상','후부','모두','대기','전체','사용','사용안함','받기'}
COMMON={'입장','확인','닫기','전투','나가기','수락','입장하기','자동진행'}
rows=[]
for n in names:
    if SPENDS.search(n):continue
    image=det.templates[n][:,:,::-1]  # the detector keeps them the other way round
    if image.shape[1]<14:continue
    got=[t for t,s in words_of(image) if s>=.9]
    word=text.clean(''.join(got))
    hangul=sum('가'<=c<='힣' for c in word)
    if hangul>=2 and len(word)<=14 and word not in NEVER and (word not in COMMON or n.startswith('버튼_')):
        e=roi[n];rows.append(dict(key=hd.key_of(det.templates[n]),name=n,words=word,exact=word in COMMON,x=e['x'],y=e['y'],w=e['w'],h=e['h']))
keep=rows
# AUTO's state is its colour. owner_hd reads that off the real screen.
STATES={'버튼_AUTO_활성':'gold','버튼_AUTO_활성2':'gold','버튼_AUTO_비활성':'white','버튼_AUTO_비활성2':'white','버튼_AUTO_일시정지':'paused'}
keep=[r for r in keep if r['name'] not in STATES]+[dict(key=hd.key_of(det.templates[n]),name=n,state=s) for n,s in STATES.items()]
out=hd.STORE/'words.jsonl'
out.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in sorted(keep,key=lambda r:r['key'])),encoding='utf-8')
print('kept',len(keep),'of',len(rows),'with words, of',len(names))
for r in keep:print(' ',r['name'],'=',r['words'])
sys.stdout.flush();os._exit(0)
