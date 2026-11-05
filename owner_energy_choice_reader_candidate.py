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
ROWS_V2=(153,191,230,268)
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
 found=layouts(frame)
 return found[0][0] if len(found)==1 else None

def layouts(frame):
 matched=[]
 for offset,suffix,rows in ((0,'',ROWS),(3,'-alt',ROWS),(0,'-v2',ROWS_V2)):
  if _score(frame[108+offset:120+offset,417:481],asset('selection-title'+suffix))<.97:continue
  ok=True
  for i,y in enumerate(rows):
   sample=frame[y+7+offset:y+27+offset,365:385]
   values=[_score(sample,asset(name+suffix)) for name in FILES]
   # The bigger art scores alike across colours, so the colour distance tells them apart. A selected row brightens: 14.4 against 18.8.
   gaps=[float(np.abs(sample.astype('int16')-asset(name+suffix).astype('int16')).mean()) for name in FILES]
   apart=values[i]-max(values[:i]+values[i+1:])>=.10 or (suffix=='-v2' and min(gaps[:i]+gaps[i+1:])-gaps[i]>=2.5)
   if values[i]<.96 or not apart:ok=False;break
  if ok:matched.append((offset,rows))
 return matched

def rows_of(frame):
 """Tops of the four rows on this screen. The game now spaces them 38 apart (seen 11-05)."""
 found=layouts(frame) if isinstance(frame,np.ndarray) and frame.shape==(479,897,3) and inventory_parts(frame)==(True,True) else []
 return found[0][1] if len(found)==1 else ROWS

def layout_screen(frame):return layout_variant(frame) is not None

def ocr_counter(frame,offset):
 """n/m by the number engine, for touching glyphs like 1/160. The caller needs two equal frames."""
 import os,re
 from tools.ocr_support import get_paddle_engine
 from owner_progression import resized
 root=os.environ.get('MDT_SHARED_APP_ROOT')
 if not root:return None
 found=set()
 for language in ('number','korean'):
  for page in get_paddle_engine(Path(root),language=language).predict(resized(frame,(405,317+offset,86,20))):
   for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
    hit=re.fullmatch(r'(\d{1,4})/(\d{1,4})',str(text).replace(' ',''))
    if hit and float(score)>=.85 and 1<=int(hit[1])<=int(hit[2]):found.add((int(hit[1]),int(hit[2])))
 # Either engine may name it at the same .85, but they must not name different values.
 return found.pop() if len(found)==1 else None
def read_screen(frame):
 offset=layout_variant(frame)
 if offset is None:return None
 # Only a unique bright outline, with clear separation from the other rows,
 # counts as a selected row. Unknown highlights never imply a default.
 borders=[float(frame[y+offset:y+offset+3,363:535].min(axis=2).mean()) for y in rows_of(frame)]
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
 if counter is None:counter=ocr_counter(frame,offset)
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
