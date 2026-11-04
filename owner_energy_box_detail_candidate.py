"""Read observed 49/50 essence-box details, without granting action rights."""
from functools import lru_cache
from pathlib import Path
import cv2,numpy as np
import os,re
from PIL import Image
from owner_progression import inventory_parts
ASSETS=Path(__file__).parent/'assets/energy-box-runtime'
@lru_cache(maxsize=8)
def asset(name):return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))
def score(a,b):
 if a.shape!=b.shape:return -1
 n=float(cv2.matchTemplate(a,b,cv2.TM_CCOEFF_NORMED)[0,0]);return n if np.isfinite(n) else -1

def close_mark(frame):
 """Exact X foreground survives the observed translucent backdrop change."""
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3):return False
 actual=frame[99:112,502:518];expected=asset('detail-close')
 if actual.shape!=expected.shape:return False
 ink=expected.min(axis=2)>190
 return bool(ink.sum()>=8 and np.array_equal(actual.min(axis=2)>190,ink))

def detail_screen(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or inventory_parts(frame)!=(True,True):return None
 if score(frame[236:263,383:513],asset('choices-detail'))<.97:return None
 if score(frame[352:374,404:493],asset('open'))<.97:return None
 return True

def generic_box_detail(frame):
 """Only identify an ordinary box detail for safe X-close, not its item."""
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or inventory_parts(frame)!=(True,True):return False
 return (close_mark(frame) and
         score(frame[352:374,404:493],asset('open'))>=.97)

def detail(frame):
 if not detail_screen(frame):return None
 return count(frame)

def count(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 # Exact observed fast cases remain cheap. Include the full left margin so
 # the suffix of 147 cannot be mistaken for the known 47 raster.
 values=[(score(frame[143:156,484:510],asset('count'+str(n))),n) for n in (47,48,49,50)]
 values.sort(reverse=True)
 if (values[0][0]>=.985 and values[0][0]-values[1][0]>=.015
     and not (frame[143:156,477:484].min(axis=2)>150).any()
     and np.array_equal(frame[143:156,484:510].min(axis=2)>150,asset('count'+str(values[0][1])).min(axis=2)>150)):
  return values[0][1]
 # The game's count includes the unit. This exact same-widget Korean crop
 # is readable where the isolated touching numeral is not. It grants no
 # input authority; callers still require two frames and independent 1/N.
 try:
  from tools.ocr_support import get_paddle_engine
  root=os.environ.get('MDT_SHARED_APP_ROOT')
  if not root:return None
  engine=get_paddle_engine(Path(root),language='korean')
  return read_count_text(frame,engine)
 except (OSError,ValueError,TypeError):return None

def read_count_text(frame,engine):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 crop=frame[138:162,477:518]
 values=[]
 for page in engine.predict(cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)):
  for text,confidence in zip(page.get('rec_texts',()),page.get('rec_scores',())):
   value=re.fullmatch(r'(0|[1-9][0-9]{0,5})개',re.sub(r'\s+','',str(text)))
   if value and float(confidence)>=.98:values.append(int(value[1]))
 return values[0] if len(values)==1 else None

def warm_count_reader(root):
 from tools.ocr_support import get_paddle_engine
 return get_paddle_engine(Path(root),language='korean')

def evidence_detail(frame):
 """Read detail when a transient click overlay covers its open button."""
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or inventory_parts(frame)!=(True,True):return None
 if not close_mark(frame):return None
 if score(frame[236:263,383:513],asset('choices-detail'))<.97:return None
 return count(frame)

def box_candidates(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or inventory_parts(frame)!=(True,True):return None
 # The stable icon is searched only inside the inventory grid. Repeated icons
 # mean an ambiguous match: never choose one by coordinate alone.
 grid=frame[90:479,710:861];hits=[]
 for name in ('box-icon','box-icon-alt','box-icon-native'):
  needle=asset(name);result=cv2.matchTemplate(grid,needle,cv2.TM_CCOEFF_NORMED)
  if not np.isfinite(result).all():return None
  work=result.copy()
  while True:
   _,val,_,point=cv2.minMaxLoc(work)
   if val<.97:break
   x,y=point;point=(x+710+needle.shape[1]//2,y+90+needle.shape[0]//2)
   if not any(abs(point[0]-p[0])<12 and abs(point[1]-p[1])<12 for p in hits):hits.append(point)
   cv2.rectangle(work,(max(0,x-12),max(0,y-12)),(min(work.shape[1]-1,x+12),min(work.shape[0]-1,y+12)),-1,-1)
   if len(hits)>5:return None
 if not hits:
  # This is a NON-CONSUMING candidate search, not item authentication.
  # Existing native artwork differs slightly through the translucent bag.
  # Allow opening at most five plausible details, then require the unchanged
  # exact four contents / title / count / selected quantity before any claim.
  needle=asset('box-icon-native');work=cv2.matchTemplate(grid,needle,cv2.TM_CCOEFF_NORMED)
  if not np.isfinite(work).all():return None
  while True:
   _,val,_,point=cv2.minMaxLoc(work)
   if val<.90:break
   x,y=point;hits.append((x+710+needle.shape[1]//2,y+90+needle.shape[0]//2))
   cv2.rectangle(work,(max(0,x-12),max(0,y-12)),(min(work.shape[1]-1,x+12),min(work.shape[0]-1,y+12)),-1,-1)
   if len(hits)>5:return None
 return sorted(hits,key=lambda p:(p[1],p[0]))

def box_location(frame):
 """Backward-compatible single candidate; never treats icon as item proof."""
 hits=box_candidates(frame)
 return hits[0] if hits and len(hits)==1 else None

def stable_box_candidates(first,second):
 """Only shared exact candidate cells; unrelated animated cells may vary.

 A candidate only permits opening a detail. The exact four contents, stack
 count and final selected quantity must still be proved before consumption.
 """
 from owner_energy_choice_reader_candidate import layout_screen
 if any(generic_box_detail(f) or layout_screen(f) for f in (first,second)):
  return None
 a,b=box_candidates(first),box_candidates(second)
 if not a or not b:return None
 shared=[point for point in b if point in a]
 return shared or None
