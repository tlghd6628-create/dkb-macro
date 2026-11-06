"""Observed moving HUD and two-stage B teleport, on the owning worker."""
from functools import lru_cache
from pathlib import Path
import logging,re,time
LOG=logging.getLogger('project_gui.DKB')

@lru_cache(maxsize=16)
def asset(name):
 from PIL import Image
 import numpy as np
 return np.asarray(Image.open(Path(__file__).parent/'assets/movement'/(name+'.png')).convert('RGB'))

def find(frame,name,box,threshold=.95,brightness=.85):
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return None
 x,y,w,h=box;needle=asset(name);part=frame[y:y+h,x:x+w]
 if part.shape[0]<needle.shape[0] or part.shape[1]<needle.shape[1]:return None
 values=cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED)
 _,score,_,point=cv2.minMaxLoc(np.nan_to_num(values,nan=-1))
 hh,ww=needle.shape[:2];l,t=x+point[0],y+point[1];patch=frame[t:t+hh,l:l+ww]
 mask=needle.min(axis=2)>150
 if score>=threshold and mask.sum()>=8 and float((patch.min(axis=2)[mask]>150).mean())>=brightness:
  return l+ww//2,t+hh//2,(l,t,l+ww,t+hh)
 # Text rendering and UI opacity change between updates; shape must still agree.
 from owner_image_scope import unique_peak
 peak=unique_peak(frame,needle,box,min(threshold,.95))
 if not peak:return None
 l,t=peak[1:]
 return l+ww//2,t+hh//2,(l,t,l+ww,t+hh)

def moving_bar(frame):return find(frame,'auto-moving-label',(335,230,220,140),.97)

def moving_b_hit(frame,box):
 # The button's translucent scenery changes while its foreground is exact.
 # Require two exact binary foreground masks, one unique location, same ROI.
 import numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return None
 x,y,w,h=box;n=asset('moving-b-key');hh,ww=n.shape[:2]
 if x<0 or y<0 or x+w>897 or y+h>479:return None
 masks=[n.min(axis=2)>threshold for threshold in (150,190)]
 if any(int(mask.sum())<20 for mask in masks):return None
 hits=[]
 for top in range(y,y+h-hh+1):
  for left in range(x,x+w-ww+1):
   q=frame[top:top+hh,left:left+ww].min(axis=2)
   if all(np.array_equal(q>threshold,mask) for threshold,mask in zip((150,190),masks)):
    hits.append((left+ww//2,top+hh//2,(left,top,left+ww,top+hh)))
 if len(hits)==1:return hits[0]
 # Exact masks fail once rendering or opacity changes; one clear shape match still counts.
 from owner_image_scope import unique_peak
 peak=None if hits else unique_peak(frame,n,box,.92)
 return (peak[1]+ww//2,peak[2]+hh//2,(peak[1],peak[2],peak[1]+ww,peak[2]+hh)) if peak else None

def hud_gain(frame,name,box):
 """Brightness of the icon's foreground against the saved image, or None if absent."""
 from owner_image_scope import peaks,_clip
 x,y,w,h=box;needle=asset(name)
 found=peaks(frame,needle,_clip(x-6,y-6,w+12,h+12),count=1)
 if not found or found[0][0]<.8:return None
 l,t=found[0][1:];patch=frame[t:t+h,l:l+w];white=needle.min(axis=2)>170
 if patch.shape!=needle.shape or int(white.sum())<40:return None
 return float(patch[white].mean())/float(needle[white].mean())

def hud_anchor(frame,name,box):
 import numpy as np
 x,y,w,h=box;needle=asset(name);patch=frame[y:y+h,x:x+w]
 if patch.shape!=needle.shape:return False
 white=needle.min(axis=2)>170
 if white.sum()>=40 and float((patch.min(axis=2)[white]>150).mean())>=.95 and float(np.abs(patch.astype('float32')-needle.astype('float32'))[white].mean())<=15:return True
 # The whole HUD's opacity changes between updates (207 ->162 ink), while an
 # open window dims it further. Compare shape softly, then only the ratio.
 gain=hud_gain(frame,name,box)
 return gain is not None and .7<=gain<=1.1

def hud_dimmed(frame):
 """The HUD icon is present but dimmed: a window is open over the field."""
 gain=hud_gain(frame,'settings-hud',(758,440,26,30))
 return gain is not None and gain<.7

REAL_HUD={'home-real':(992,707),'settings-real':(1144,704)}

@lru_cache(maxsize=2)
def real_hud_ink(name):
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/hud'/(name+'.png')).convert('RGB')).min(axis=2)>170

def real_hud_glyph(real,name):
 """The glyph's white ink at its real place, a few pixels either way, over something darker. On 31 saved screens
 this was whole on the field and at most half anywhere else. The small frame scores .73 over a bright roof."""
 import numpy as np
 ink=real_hud_ink(name);x0,y0=REAL_HUD[name];h,w=ink.shape
 for dy in range(-3,4):
  for dx in range(-3,4):
   part=real[y0+dy:y0+dy+h,x0+dx:x0+dx+w].min(axis=2)
   if part.shape==ink.shape and float((part[ink]>140).mean())>=.95 and float(part[ink].mean())-float(part[~ink].mean())>=40:return True
 return False

def field_hud(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return False
 # Fixed foreground glyphs are unchanged in towns. Their translucent
 # background contains scenery/other players and must not own identity.
 real=getattr(frame,'hi',None)
 if real is not None:
  import numpy as np
  real=np.asarray(real)
  if not all(real_hud_glyph(real,name) for name in REAL_HUD):return False
  # The health bar sits lower here than the old size would put it, at y 680.
  bar=real[668:692,590:780].astype('float32');r,g,b=bar[:,:,0],bar[:,:,1],bar[:,:,2]
  return int(((g>90)&(g>r*1.20)&(g>b*1.15)).sum())>=40
 elif not (hud_anchor(frame,'home-hud',(662,441,25,29)) and hud_anchor(frame,'settings-hud',(758,440,26,30))):return False
 hp=frame[411:423,394:502].astype('float32');r,g,b=hp[:,:,0],hp[:,:,1],hp[:,:,2]
 return int(((g>90)&(g>r*1.20)&(g>b*1.15)).sum())>=40
def moving_field(frame):
 return bool(moving_bar(frame) and field_hud(frame))
# The window by its words at 1366x768, real pixels wide enough for both layouts it has had. Its pictures have no cut,
# and at this size the plain frame scores 축지술 .874 (other PC, 11-05), so a town return never saw the window.
METHOD_TITLE=(530,235,320,50);METHOD_BODY=(520,240,326,290);METHOD_BUTTONS=(520,465,326,50)  # inside the window: scenery would be read again each frame
METHOD_WORDS='자동이동방법선택';TELEPORT_WORD='축지술';CLOSE_MARKS=('×','X','x','✕')
METHOD_DARK=.7  # of the bar dark and grey: .78-.87 with the window open, under .6 on the field and the bag

def method_open(frame):
 """Its title in its title bar. The dark grey bar is looked at first, only to skip a reading: this is asked on every
 scene check, and a reading of moving scenery costs about .15 s."""
 import numpy as np
 from difflib import SequenceMatcher
 from owner_text import read,clean
 x,y,w,h=METHOD_TITLE
 bar=np.asarray(frame.hi)[y:y+h,x:x+w].astype('int16');top=bar.max(axis=2)
 if float(((top<70)&(top-bar.min(axis=2)<=12)).mean())<METHOD_DARK:return False
 return any(SequenceMatcher(None,clean(r['text']),METHOD_WORDS).ratio()>=.7 for r in read(None,frame,METHOD_TITLE))

def method_rows(frame):
 """Every word in the window, or None when it is not open."""
 from owner_text import read
 return read(None,frame,METHOD_BODY) if method_open(frame) else None

def _teleport_row(rows):
 """The one button reading exactly 축지술. 축지부 사용 costs an item and the sentence above also says 축지술, so a
 close spelling is not this button: pressing nothing is the safe answer."""
 from owner_text import clean
 found=[r for r in rows if clean(r['text'])==TELEPORT_WORD]
 return found[0] if len(found)==1 else None

def teleport_word(frame):
 """A hit for the 축지술 button, in the shape a found picture has, or None. Only the button row is read: the native
 click looks again right before it presses."""
 from owner_text import read,logical_bounds
 row=_teleport_row(read(None,frame,METHOD_BUTTONS)) if method_open(frame) else None
 return (row['x'],row['y'],logical_bounds(row,frame)) if row else None

def home_word(frame):
 """The Home icon by the word under it. Over scenery its translucent picture scores .60 on the real field."""
 from owner_text import read,clean
 from owner_hd import logical_of
 found=[r for r in read(None,frame,(960,725,110,36),scale=3) if clean(r['text']).lower()=='home']
 if len(found)!=1:return None
 x,y=logical_of(found[0]['rx'],found[0]['ry']-20,getattr(frame,'layout',None))
 return x,y,(x-6,y-6,x+7,y+7)

def _method_window_words(frame):
 from owner_text import clean
 rows=method_rows(frame)
 button=_teleport_row(rows) if rows else None
 if button is None:return None
 title=next((r for r in rows if '이동' in clean(r['text']) and r['ry']<=METHOD_TITLE[1]+METHOD_TITLE[3]),None)
 if title is None:return None
 l,t=title['x']-49,title['y']-8
 marks=[r for r in rows if clean(r['text']) in CLOSE_MARKS and r['ry']<=METHOD_TITLE[1]+METHOD_TITLE[3]]
 close=(marks[0]['x'],marks[0]['y']) if marks else (l+139,t+7)
 return {'title':(l,t),'close':close,'button':(button['x']-16,button['y']-5),'rows':rows}

def method_window(frame):
 """Title first, then the button inside that window; the layout may change."""
 from owner_image_scope import unique_peak,_clip
 if getattr(frame,'shape',None)!=(479,897,3):return None
 if getattr(frame,'hi',None) is not None:return _method_window_words(frame)
 title=unique_peak(frame,asset('move-method-title'),(340,125,220,50),.92)
 if not title:return None
 l,t=title[1:]
 button=unique_peak(frame,asset('teleport-b-button'),_clip(l-60,t+120,180,50),.95)
 return {'title':(l,t),'close':(l+139,t+7),'button':button[1:]} if button else None
def choice(frame):return method_window(frame) is not None
def story_guide(frame):
 return bool(find(frame,'story-guide-title',(527,54,170,35),.97,.95) and find(frame,'story-guide-arrow',(692,52,40,42),.97,.95))

def tower_combat(frame):
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return False
 for name,box in (('tower-map-title',(23,7,37,14)),('tower-timer-icon',(768,40,14,17)),('tower-exit',(11,82,23,28))):
  x,y,w,h=box;needle=asset(name);part=frame[y:y+h,x:x+w]
  if part.shape!=needle.shape:return False
  mask=needle.max(axis=2)>140
  if float(cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED)[0,0])>=.95 and mask.any() and float(np.abs(part.astype('float32')-needle.astype('float32'))[mask].mean())<=25:continue
  # The opaque map title names the tower. The translucent exit icon and the timer
  # sink with what is behind them (.81-.97 on real floors), so one of them is enough.
  from owner_image_scope import unique_peak,_clip
  title=unique_peak(frame,asset('tower-map-title'),(13,0,57,31),.95)
  if not title:return False
  return bool(unique_peak(frame,asset('tower-timer-icon'),(758,32,34,33),.9) or unique_peak(frame,asset('tower-exit'),(3,74,39,44),.8))
 return True

def distance(rows,*,bare=False):
 values=set()
 for row in rows:
  if row.get('score',0)<.98:continue
  text=row['text'].strip().replace(',','')
  text=re.sub(r'^거리\s*[:：]?\s*','',text)
  found=re.fullmatch(r'([0-9]{1,5}(?:\.[0-9]+)?)\s*(m|km|미터)?',text,re.I)
  if not found:continue
  number=float(found[1]);unit=(found[2] or '').lower()
  if not unit and (not bare or not number.is_integer()):continue
  if unit=='km':number*=1000
  if 0<=number<=100000:values.add(number)
 return next(iter(values)) if len(values)==1 else None

def method_distance(ui,window):
 # Only the distance carries the 거리 prefix or a unit; the cost rows do not.
 if 'rows' in window:return distance(window['rows'])
 l,t=window['title']
 return distance(ui.rows((l-20,t+45,140,75),language='korean'))

def confirm_choice(ui,*,initial_distance=None):
 from owner_skill_goal import Pending
 first=ui.frame()
 window=method_window(first)
 if not window:return False
 ui.context.wait(.08)
 window=method_window(ui.frame())
 if not window:return False
 if initial_distance is None:
  initial_distance=method_distance(ui,window)
 if initial_distance is None or initial_distance<200:
  ui.click(*window['close'],choice)
  LOG.info('축지술 선택창 정상화 · 200m 이상 확인 없음 · 선택창만 닫고 임무 재개')
  return False
 # The second B is authorized only by the exact observed modal, not a timer.
 if not choice(ui.frame()):raise Pending('두 번째 B 입력 전 축지술 선택창 변경')
 ui.key(0x42)
 ui.wait(lambda f:not choice(f),seconds=5)
 LOG.info('축지술 B 두 번째 입력 · 선택창 통과 확인 · 거리=%.0fm',initial_distance)
 return True

REAL_BAR=(560,522,250,42)   # real: 자동 이동 중 74m B above the HP bar (pc1 14:3x)


def real_moving(frame):
 """Metres left on the auto-move bar when it shows 자동 이동 중 and its B key, else None."""
 from owner_text import read,clean
 rows=[clean(r['text']) for r in read(None,frame,REAL_BAR,scale=2,minimum=.6)]
 if not any('자동이동' in w for w in rows) or 'B' not in rows:return None
 found=[int(m.group(1)) for w in rows for m in [re.fullmatch(r'(\d{1,5})m',w)] if m]
 return found[0] if len(found)==1 else None


def travel(ui):
 from owner_skill_goal import Pending
 first=ui.frame()
 if choice(first):return confirm_choice(ui)
 if getattr(first,'hi',None) is not None:
  # At 1366 the bar's pictures rarely match (pc2 11-06: no 축지술 in story mode since 16:16, 895 m walked). Its own
  # words say it: 자동 이동 중, the distance, and B. Two reads must agree within 50 m.
  a=real_moving(first)
  if a is None or a<200:return False
  ui.context.wait(.3);b=real_moving(ui.frame())
  if b is None or b<200 or abs(a-b)>50:return False
  ui.key(0x42)
  try:ui.wait(choice,seconds=2)
  except Pending:
   LOG.info('축지술 B 입력 후 선택창 미확인 · 기본 이동 계속 · 거리=%dm',b);return False
  return confirm_choice(ui,initial_distance=b)
 bar=moving_bar(first)
 if not bar or not moving_field(first):return False
 l,t,r,b=bar[2]
 key_box=(l+88,t-7,37,39)
 if not moving_b_hit(first,key_box):return False
 # Walking distances normally change between frames. Exact-text paired OCR
 # rejects e.g.1210m ->1207m; read two independent, bounded numeric samples.
 started=time.monotonic();read_box=(l+59,t-5,36,22)
 a=distance(ui.rows(read_box,language='number',pair=False),bare=True)
 if a is None or a<200:return False
 meters=distance(ui.rows(read_box,language='number',pair=False),bare=True)
 if meters is None or meters<200 or abs(a-meters)>50 or time.monotonic()-started>4:return False
 fresh=ui.frame()
 if not moving_field(fresh) or not moving_b_hit(fresh,key_box):return False
 ui.key(0x42)
 try:ui.wait(choice,seconds=2)
 except Pending:
  LOG.info('축지술 B 첫 입력 후 선택창 미확인 · 두 번째 입력 생략 · 기본 이동 계속')
  return False
 return confirm_choice(ui,initial_distance=meters)
