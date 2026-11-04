"""Read the observed four-choice energy box screen; never send an input.

Frames and icon assets were captured from the actual hero selection box.
Neither this reader nor icon recognition proves quantity or receipt.
"""
from functools import lru_cache
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from owner_progression import inventory_parts

NAMES=('생명','여명','몽환','홍염')
FILES=('life','dawn','dream','crimson')
ROWS=(152,188,224,260)
ASSETS=Path(__file__).parent/'assets/energy-choice'

@lru_cache(maxsize=20)
def asset(name):
 return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

def _score(part,needle):
 if part.shape!=needle.shape or part.ndim!=3:return -1.
 value=float(cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED)[0,0])
 return value if np.isfinite(value) else -1.

def layout_variant(frame):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 if inventory_parts(frame)!=(True,True):return None
 matched=[]
 for offset,suffix in ((0,''),(3,'-alt')):
  if _score(frame[108+offset:120+offset,417:481],asset('selection-title'+suffix))<.97:continue
  ok=True
  for i,y in enumerate(ROWS):
   sample=frame[y+7+offset:y+27+offset,365:385]
   values=[_score(sample,asset(name+suffix)) for name in FILES]
   if values[i]<.96 or values[i]-max(values[:i]+values[i+1:])<.10:ok=False;break
  if ok:matched.append(offset)
 return matched[0] if len(matched)==1 else None

def layout_screen(frame):return layout_variant(frame) is not None

def read_screen(frame):
 offset=layout_variant(frame)
 if offset is None:return None
 # Only a unique bright outline, with clear separation from the other rows,
 # counts as a selected row. Unknown highlights never imply a default.
 borders=[float(frame[y+offset:y+offset+3,363:535].min(axis=2).mean()) for y in ROWS]
 order=sorted(range(4),key=lambda i:borders[i],reverse=True)
 if borders[order[0]]>=110 and borders[order[0]]-borders[order[1]]>=30:selected=NAMES[order[0]]
 elif max(borders)<90:selected=None
 else:return None
 # Glyph result is provisional; a fresh independent detail count must match.
 from owner_energy_counter_glyph_candidate import load_observed_atlas,read_counter
 try:
  # Multi-digit grouped quantities extend left of the old 1/N crop. Stay
  # between the independently known minus/plus controls, never clip a digit.
  counter=read_counter(frame,load_observed_atlas(),box=(405,319+offset,491,334+offset))
  if counter is None and offset==3 and _score(frame[322:337,436:468],asset('counter-one49-alt'))>=.995:counter=(1,49)
 except (OSError,ValueError,TypeError):return None
 if counter is None:return None
 quantity,available=counter
 return {'selected':selected,'rows':list(NAMES),'quantity':quantity,
         'available_count':available,
         'receipt':False,'evidence':'selection-screen-only'}

def read_open_pair(first,second):
 if first is second or not isinstance(first,np.ndarray) or not isinstance(second,np.ndarray) or np.shares_memory(first,second):return None
 a,b=read_screen(first),read_screen(second)
 return a if a is not None and a==b else None

def read_pair(first,second):
 a=read_open_pair(first,second)
 return a if a is not None and a.get('selected') in NAMES else None
