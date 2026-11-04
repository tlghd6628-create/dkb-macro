"""Experimental, isolated glyph reader for the energy selection counter.

Not installed in the macro, not an authorization to consume a box. All 0-9
and slash templates must come from independently identified real screenshots
of the same widget/font. If the atlas is incomplete or ambiguous, hold.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import hashlib,json
import cv2,numpy as np

SYMBOLS='0123456789/'

@dataclass(frozen=True)
class Sample:
 symbol:str
 pixels:np.ndarray
 source:str
 region:str='all'

def foreground(image,threshold=150):
 if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3:return None
 return (image.min(axis=2)>=threshold).astype(np.uint8)

def tight(mask):
 if not isinstance(mask,np.ndarray) or mask.ndim!=2:return None
 ys,xs=np.where(mask>0)
 if len(xs)<2:return None
 return mask[ys.min():ys.max()+1,xs.min():xs.max()+1]

def sample(symbol,image,source,region='all'):
 if not isinstance(symbol,str) or len(symbol)!=1 or symbol not in SYMBOLS or not isinstance(source,str) or not source.strip():raise ValueError('표본의 숫자와 원본 출처 필요')
 if region not in ('all','denominator'):raise ValueError('숫자 표본 위치 확인 필요')
 bits=tight(foreground(image))
 if bits is None or not 1<=bits.shape[1]<=12 or not 2<=bits.shape[0]<=14:raise ValueError('숫자 글리프 경계 확인 필요')
 return Sample(symbol,bits.copy(),source,region)

def _distance(a,b):
 """Binary mismatch normalized by union; nearest-neighbor only."""
 if a is None or b is None:return 1.
 h=max(a.shape[0],b.shape[0]);w=max(a.shape[1],b.shape[1])
 aa=cv2.resize(a,(w,h),interpolation=cv2.INTER_NEAREST)>0
 bb=cv2.resize(b,(w,h),interpolation=cv2.INTER_NEAREST)>0
 union=np.logical_or(aa,bb).sum()
 return float(np.logical_xor(aa,bb).sum()/union) if union else 1.

class Atlas:
 def __init__(self,samples):
  self.entries={key:[] for key in SYMBOLS}
  for entry in samples:
   if not isinstance(entry,Sample) or entry.symbol not in self.entries:raise ValueError('숫자 표본 형식 오류')
   self.entries[entry.symbol].append(entry)
 def complete(self):
  # One observed instance per symbol is enough for offline experiments only;
  # production requires independent holdout screenshots as a separate gate.
  return all(self.entries[k] for k in SYMBOLS)
 def classify(self,bits,max_distance=.10,min_margin=.08,*,denominator=False):
  if not self.complete():return None
  q=tight(bits)
  if q is None:return None
  distances=[]
  for symbol in SYMBOLS:
   eligible=[row for row in self.entries[symbol] if row.region=='all' or denominator]
   if not eligible:return None
   d=min(_distance(q,row.pixels) for row in eligible)
   distances.append((d,symbol))
  distances.sort()
  if distances[0][0]>max_distance or distances[1][0]-distances[0][0]<min_margin:return None
  return distances[0][1]

@lru_cache(maxsize=1)
def load_observed_atlas():
 """Load checked-in native-screen crops; unknown/corrupt files fail closed."""
 from PIL import Image
 path=Path(__file__).parent/'assets/energy-choice/glyphs'
 manifest=json.loads((path/'manifest.json').read_text(encoding='utf8'))
 if not isinstance(manifest,dict) or manifest.get('version')!=1 or not isinstance(manifest.get('entries'),list):raise ValueError('숫자 표본 정보 확인 필요')
 samples=[]
 for entry in manifest['entries']:
  name=entry.get('file');symbol=entry.get('symbol');digest=entry.get('sha256');source=entry.get('source')
  if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.png'):raise ValueError('숫자 표본 파일명 확인 필요')
  data=(path/name).read_bytes()
  if not isinstance(digest,str) or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('숫자 표본 무결성 확인 필요')
  from io import BytesIO
  with Image.open(BytesIO(data)) as im:frame=np.asarray(im.convert('RGB'))
  samples.append(sample(symbol,frame,source,entry.get('region','all')))
 atlas=Atlas(samples)
 if not atlas.complete():raise ValueError('숫자 표본 누락')
 return atlas

def read_counter(frame,atlas,box=(436,319,467,334)):
 """Search possible touching-glyph splits; return only one unambiguous n/m.

 The caller must independently prove the correct selection screen and must
 compare m to a separately proved box count. Returned values are provisional.
 """
 if not atlas.complete():return None
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 left,top,right,bottom=box
 if not 0<=left<right<=897 or not 0<=top<bottom<=479:return None
 mask=foreground(frame[top:bottom,left:right]);ink=np.where(mask.any(axis=0))[0]
 if len(ink)==0:return None
 start,end=int(ink[0]),int(ink[-1])+1;answers=[];cache={}
 def visit(pos,text):
  while pos<end and not mask[:,pos].any():pos+=1
  if len(set(answers))>1:return
  if pos==end:
   if text.count('/')==1:
    n,d=text.split('/')
    if n.isdigit() and d.isdigit() and 1<=int(n)<=int(d):answers.append((int(n),int(d)))
   return
  if len(text)>=9:return
  for width in range(1,min(12,end-pos)+1):
   bits=mask[:,pos:pos+width]
   if not bits[:,-1].any():continue
   denominator='/' in text
   key=(pos,width,denominator)
   if key not in cache:
    value=atlas.classify(bits,denominator=denominator)
    # A single antialiased slash-edge pixel may touch the previous glyph;
    # only ignore it when the remaining full glyph independently proves '/'.
    if value is None and width>1 and int(bits[:,0].sum())==1 and atlas.classify(bits[:,1:],denominator=denominator)=='/':value='/'
    cache[key]=value
   symbol=cache[key]
   if symbol is None or (symbol=='/' and ('/' in text or not text)):continue
   visit(pos+width,text+symbol)
 visit(start,'')
 distinct=set(answers)
 return next(iter(distinct)) if len(distinct)==1 else None

def read_pair(first,second,atlas):
 if first is second or not isinstance(first,np.ndarray) or not isinstance(second,np.ndarray) or np.shares_memory(first,second):return None
 a=read_counter(first,atlas);b=read_counter(second,atlas)
 return a if a is not None and a==b else None
