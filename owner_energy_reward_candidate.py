"""Observed dawn-one reward pixels; no arbitrary rewards inferred."""
from pathlib import Path
import os,re,cv2
from owner_energy_box_detail_candidate import asset,score
import numpy as np

def dawn_one(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return False
 return (score(frame[94:110,421:478],asset('reward-title'))>=.98
         and score(frame[128:160,433:465],asset('reward-dawn-icon1'))>=.98
         and score(frame[164:178,429:469],asset('reward-dawn-name'))>=.98)

def dream_one(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return False
 return (score(frame[94:110,421:478],asset('reward-title'))>=.98
         and score(frame[128:160,433:465],asset('reward-dream-icon1'))>=.98
         and score(frame[164:178,429:469],asset('reward-dream-name'))>=.98)

def life_one(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return False
 count=frame[151:160,455:465].min(axis=2)>180
 expected=asset('reward-life-icon1')[23:32,22:32].min(axis=2)>180
 return (score(frame[94:110,421:478],asset('reward-title'))>=.98
         and score(frame[128:160,433:465],asset('reward-life-icon1'))>=.98
         and score(frame[164:178,429:469],asset('reward-life-name'))>=.98
         and expected.sum()>=2 and np.array_equal(count,expected))

READERS={'생명':life_one,'여명':dawn_one,'몽환':dream_one}

def quantity(frame,name):
 """Read an observed named reward quantity; never infer N from the request."""
 if name not in READERS:return None
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 suffix={'생명':'life','여명':'dawn','몽환':'dream'}[name]
 reference=asset('reward-'+suffix+'-icon1')
 if READERS[name](frame) and np.array_equal(frame[148:160,433:465].min(axis=2)>180,reference[20:32].min(axis=2)>180):return 1
 if (score(frame[94:110,421:478],asset('reward-title'))<.98
     or score(frame[128:150,433:465],asset('reward-'+suffix+'-icon1')[:22])<.98
     or score(frame[164:178,429:469],asset('reward-'+suffix+'-name'))<.98):return None
 from tools.ocr_support import get_paddle_engine
 root=os.environ.get('MDT_SHARED_APP_ROOT')
 if not root:return None
 engine=get_paddle_engine(Path(root),language='korean');found=[]
 image=cv2.resize(frame[148:162,433:467],None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
 for page in engine.predict(image):
  for text,confidence in zip(page.get('rec_texts',()),page.get('rec_scores',())):
   value=re.fullmatch(r'[1-9][0-9]{0,5}',str(text).strip())
   if value and float(confidence)>=.98:found.append(int(value[0]))
 return found[0] if len(found)==1 else None

def matches(frame,name,expected):
 return type(expected) is int and expected>0 and quantity(frame,name)==expected
