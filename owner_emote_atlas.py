"""Shared emote name/grid memory; reuses the existing panel, wheel and click.

Only label foreground is retained, never character pixels or send permission.
Coordinates nominate a slot; a fresh label must still match exactly.
"""
from functools import lru_cache
from pathlib import Path
import json,re
import cv2,numpy as np

PACKAGED=Path(__file__).parent/'assets/quest-emote/emote-atlas.json'

@lru_cache(maxsize=1)
def packaged():
 try:d=json.loads(PACKAGED.read_text(encoding='utf8'))
 except (OSError,ValueError):return {}
 return d.get('cards',{}) if d.get('version')==1 else {}

def names():return frozenset(packaged())

def canonical(name):
 # Reviewed fixed-detail OCR observation, not edit-distance guessing. There
 # is no emote named 으쪽. Existing OCR confidence/fresh-pair gates still apply.
 return {'으쪽':'으쓱'}.get(name,name)

def decode(entry):
 try:
  h,w=entry['shape']
  if not (3<=h<=20 and 3<=w<=90):return None
  mask=np.unpackbits(np.frombuffer(bytes.fromhex(entry['bits']),dtype='uint8'))[:h*w].reshape(h,w)
  return mask if mask.sum()>=5 else None
 except (ValueError,KeyError,TypeError):return None

class Atlas:
 def __init__(self,root):
  self.path=Path(root)/'settings/owner-emote-card-atlas.json'
 def entries(self):
  result=dict(packaged())
  try:d=json.loads(self.path.read_text(encoding='utf8'))
  except (OSError,ValueError):return result
  if d.get('version')==1 and isinstance(d.get('cards'),dict):
   for name,entry in d['cards'].items():
    if re.fullmatch('[가-힣]{1,12}',name) and isinstance(entry,dict) and decode(entry) is not None:result[name]=entry
  return result
 def find(self,frame,target):
  if getattr(frame,'shape',None)!=(479,897,3):return None
  entry=self.entries().get(target,{})
  mask=decode(entry)
  if mask is None:return None
  h,w=mask.shape;x=entry.get('left')
  if type(x) is not int or not 250<=x<x+w<=429:return None
  hay=(frame[340:474,x:x+w].min(axis=2)>150).astype('uint8')
  scores=cv2.matchTemplate(hay,mask,cv2.TM_SQDIFF)
  found=[]
  for y in np.where(scores[:,0]<.1)[0]:
   # Exact foreground equality also rejects a same-colour blank rectangle.
   if np.array_equal(hay[y:y+h],mask):found.append(340+int(y))
  if len(found)!=1:return None
  return (entry.get('column_x',x+w//2),found[0]-entry.get('click_dy',16))
 def matches(self,frame,target,point):return point is not None and self.find(frame,target)==point
 def direction(self,frame,target):
  """Choose the existing one-notch wheel direction from visible grid labels."""
  entry=self.entries().get(target,{})
  if type(entry.get('row')) is not int:return None
  offsets=[]
  for name,other in self.entries().items():
   if type(other.get('row')) is not int:continue
   point=self.find(frame,name)
   if point:offsets.append(367+58*other['row']-(point[1]+other.get('click_dy',16)))
  if not offsets:return None
  offset=int(np.median(offsets));label=367+58*entry['row']-offset
  return 1 if label<346 else (-1 if label>465 else None)
 def learn(self,name,frames,bounds):
  """Only an existing paired OCR card label can add a new shared slot."""
  if not re.fullmatch('[가-힣]{1,12}',name) or len(frames)!=2:return False
  l,t,r,b=map(int,bounds)
  if not (250<=l<r<=429 and 340<=t<b<=474):return False
  if any(getattr(f,'shape',None)!=(479,897,3) for f in frames):return False
  a,bits=[f[t:b,l:r].min(axis=2)>150 for f in frames]
  if a.sum()<5 or not np.array_equal(a,bits):return False
  entry={'left':l,'shape':list(a.shape),'bits':np.packbits(a).tobytes().hex(),
         'column_x':(l+r)//2,'click_dy':16,'proof':'paired_card_label'}
  try:d=json.loads(self.path.read_text(encoding='utf8'))
  except (OSError,ValueError):d={'version':1,'cards':{}}
  if d.get('version')!=1 or not isinstance(d.get('cards'),dict):return False
  d['cards'][name]=entry
  from owner_timetable import save
  save(self.path,d);return True
