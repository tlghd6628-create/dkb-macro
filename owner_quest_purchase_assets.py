"""Observed generic HP item glyph, independent of character name/equipment."""
from pathlib import Path
from functools import lru_cache
import numpy as np,cv2
from PIL import Image
@lru_cache(maxsize=1)
def icon():return np.asarray(Image.open(Path(__file__).parent/'assets/quest-purchase/hp-quickslot.png').convert('RGB'))
def hp_slot(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return None
 reference=icon();found=[]
 for x in (379,412):
  patch=frame[431:445,x:x+12]
  if patch.shape!=reference.shape:continue
  score=float(cv2.matchTemplate(patch,reference,cv2.TM_CCOEFF_NORMED)[0,0])
  if np.isfinite(score) and score>=.97:found.append(x)
 # User canonical layout: tier1 Ctrl1, tier2 Ctrl2, tier3 Ctrl3.
 # A tier1 glyph in a different slot is diagnostic, never use permission.
 return 379 if found==[379] else None

@lru_cache(maxsize=2)
def goal_asset(name):return np.asarray(Image.open(Path(__file__).parent/'assets/quest-purchase'/(name+'.png')).convert('RGB'))
def _label(frame,name,box):
 x,y,w,h=box;sample=frame[y:y+h,x:x+w];reference=goal_asset(name)
 if sample.shape!=reference.shape:return False
 score=float(cv2.matchTemplate(sample,reference,cv2.TM_CCOEFF_NORMED)[0,0]);ink=reference.min(axis=2)>180
 return bool(np.isfinite(score) and score>=.97 and ink.sum()>=20 and (sample.min(axis=2)[ink]>160).mean()>=.95)
def purchase_step(frame):
 return bool(getattr(frame,'shape',None)==(479,897,3)
   and _label(frame,'marsh-step2-title',(685,78,151,22))
   and _label(frame,'marsh-buy-goal',(682,264,155,16)))

def empty_cart(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return False
 sample=frame[315:351,330:572];ref=goal_asset('cart-empty')
 return bool(sample.shape==ref.shape and float(cv2.matchTemplate(sample,ref,cv2.TM_CCOEFF_NORMED)[0,0])>=.97)
