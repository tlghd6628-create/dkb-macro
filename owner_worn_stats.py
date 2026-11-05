"""Display-only equipped-tooltip readings; never resource/action authority."""
from pathlib import Path
from functools import lru_cache
import hashlib,logging,re,time,threading
import cv2,numpy as np
from PIL import Image
from owner_chore_transition import ChoreYield,ReadOnlyViewUnavailable,dialogue_pair,unavailable_frame,unavailable_pair

LOG=logging.getLogger('project_gui.DKB')
FIELDS=('enhance','opening','breakthrough','awaken')

def yield_readonly_if_interrupted(service,context,inputs,slot,ui=None):
 if unavailable_pair(service,context):raise ReadOnlyViewUnavailable(slot)
 if dialogue_pair(service,context,inputs):raise ChoreYield(slot)
 # The game's own quest may close the tooltip on a map boundary. Only the
 # existing paired normal-field classifier proves this route; an arbitrary
 # missing popup remains a hard input fence below.
 if ui is not None and callable(getattr(ui,'normal',None)) and ui.normal():
  raise ReadOnlyViewUnavailable(slot)

@lru_cache(maxsize=4)
def label(field):
 return np.asarray(Image.open(Path(__file__).parent/'assets/worn-stats'/(field+'.png')).convert('RGB'))

REAL_ROWS=(565,335,235,250)  # the tooltip's rows, in real pixels. A blessing's sit lower than an item's.
REAL_NUMBER=(690,45,26)      # left edge, width and height of a row's number, between its - and + buttons
REAL_ROW_GAP=28              # rows of the growth preview stand this far apart
REAL_TITLE=(565,155,215,32);REAL_GRADE=(575,205,70,60);REAL_TAB=(570,303,60,24)
WORDS={'강화':'enhance','개방':'opening','돌파':'breakthrough','각성':'awaken'}
# The worn blessing tiles on the info panel, 1 to 5 from the left, always in the same place.
BLESSING_SLOTS={'가호1':(15,294,25,27),'가호2':(51,294,25,27),'가호3':(87,294,25,27),'가호4':(122,294,25,27),'가호5':(158,294,25,27)}
ALL_SLOTS=('무기','반지','팔찌','목걸이','귀걸이','갑옷','다리','신발','장갑','투구','허리띠',*BLESSING_SLOTS)
WORN_TEST_SECONDS=240

def real_table(real):
 """The rows by their words, in real pixels. Label pictures shrunk from 1366 score around .89 either side of the bar,
 and three slots of eleven came back unread (18:23). 강화 and 각성 prove the table; the rows between stand at a fixed
 spacing, so a word read badly (돌파 came back 들파) still has its number read."""
 from owner_text import clean,read_area
 x,y,w,h=REAL_ROWS
 hits={}
 for row in read_area(None,real[y:y+h,x:x+w],left=x,top=y,minimum=.5):
  field=WORDS.get(clean(row['text']))
  if field:hits[field]=row['ry']
 if 'enhance' not in hits or 'awaken' not in hits:return None
 rows=round((hits['awaken']-hits['enhance'])/REAL_ROW_GAP)
 names={2:('enhance','opening','awaken'),3:('enhance','opening','breakthrough','awaken')}.get(rows)
 if names is None or abs(hits['awaken']-hits['enhance']-rows*REAL_ROW_GAP)>4:return None
 return {field:(REAL_NUMBER[0],hits['enhance']+index*REAL_ROW_GAP-REAL_NUMBER[2]//2,REAL_NUMBER[1],REAL_NUMBER[2]) for index,field in enumerate(names)}

def real_popup(real):
 """The details window is open: its 정보 tab, the same on an item and a blessing. It has no E to read."""
 from owner_text import clean,read_area
 x,y,w,h=REAL_TAB
 return any(clean(row['text'])=='정보' for row in read_area(None,real[y:y+h,x:x+w],minimum=.6))

def real_heading(real):
 """(title, grade) of the open details window. The grade is one of the words, or None."""
 from owner_text import clean,read_area
 x,y,w,h=REAL_TITLE
 title=''.join(clean(row['text']) for row in read_area(None,real[y:y+h,x:x+w],minimum=.5))
 x,y,w,h=REAL_GRADE
 words=[clean(row['text']) for row in read_area(None,real[y:y+h,x:x+w],minimum=.6)]
 grades=[grade for grade in ('일반','희귀','영웅','전설') if grade in words]
 return title,grades[0] if len(grades)==1 else None

def blessing_kind(title):
 """도깨비 from 도깨비 가호 장식1 (귀속). The place on the panel gives the slot, so its digit is not needed here."""
 from difflib import SequenceMatcher
 from owner_growth_words import NAMES
 head=re.split(r'[가갓][호혹후]',title)[0]
 for name in NAMES:
  if name in head:return name
 scored=sorted(((SequenceMatcher(None,head,name).ratio(),name) for name in NAMES),reverse=True)
 return scored[0][1] if head and scored[0][0]>=.5 and scored[0][0]>scored[1][0] else None

def real_read(real,hits=None):
 """Each row's number. `hits` are the rows' places from a frame of the same open tooltip: they do not move, and finding
 them again was a whole table read per frame."""
 from owner_text import clean,read_area
 hits=hits or real_table(real)
 if hits is None:return None
 result={}
 for field,(x,y,w,h) in hits.items():
  values=[clean(row['text']) for row in read_area(None,real[y:y+h,x:x+w],language='number',scale=3,minimum=.6)]
  if len(values)==1 and re.fullmatch(r'0|[1-9][0-9]{0,2}',values[0]):result[field]=int(values[0])
 return result

def table(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return None
 if getattr(frame,'hi',None) is not None:return real_table(np.asarray(frame.hi))
 hits={};area=frame[170:385,260:650]
 # Only common Korean field labels are templates. Their numeric values and
 # the equipment/character names are always read from the current frame.
 for field in FIELDS:
  needle=label(field);values=cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED)
  _,score,_,pt=cv2.minMaxLoc(np.nan_to_num(values,nan=-1))
  # A character on three growth tabs has no 돌파 row at all, and every slot's reading failed for it (4.6 s each).
  # 강화 reads .912 there. The rows' fixed spacing below is what proves the table.
  if score>=.90:hits[field]=(260+pt[0],170+pt[1],needle.shape[1],needle.shape[0])
  elif field!='breakthrough':return None
 x,y,_,_=hits['enhance']
 if any(abs(a-x)>2 or abs(b-(y+17*i))>2 for i,(a,b,_,_) in enumerate(hits.values())):return None
 return hits

def read(frame,engine,hits=None):
 if getattr(frame,'hi',None) is not None:return real_read(np.asarray(frame.hi),hits)
 hits=table(frame)
 if hits is None:return None
 result={}
 for field,(x,y,w,h) in hits.items():
  crop=frame[y:y+h,x+60:x+92]
  if crop.shape!=(h,32,3):continue
  values=[]
  for page in engine.predict(cv2.resize(crop,None,fx=6,fy=6,interpolation=cv2.INTER_CUBIC)):
   for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
    value=re.fullmatch(r'\s*(0|[1-9][0-9]{0,2})\s*',str(text))
    # Display only, and two frames must agree. A real "0" reads .94 to .97 (11-04).
    if value and float(score)>=.9:values.append(int(value[1]))
  if len(values)==1:result[field]=values[0]
 return result

def popup(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return False
 if getattr(frame,'hi',None) is not None:return real_popup(np.asarray(frame.hi))
 from owner_progression import inventory_parts
 from owner_energy_box_detail_candidate import close_mark
 from owner_equipment_tooltip_candidate import _badge
 return bool(inventory_parts(frame)==(True,True) and close_mark(frame)
             and _badge(frame,420,116,445,135)>=.96)

READ_TRIES=6

class ReadAgain(Exception):
 """The last look before a press did not hold. Nothing was sent."""

def settled_read(service,context):
 """The numbers once two looks in a row agree. The list slides after the wheel and the 1 can read 7 while it does (23:54)."""
 last=None
 for _ in range(READ_TRIES):
  context.checkpoint();service.check();real=np.asarray(service.capture().hi);hits=real_table(real)
  now=real_read(real,hits) if hits else None
  if now and len(now)==len(hits) and now==last:return now
  last=now;context.wait(.25)
 return None

def inspect_real(service,context,inputs,profile,character,slot,*,decide=None):
 """A worn tile's details at 1366x768: click its fixed place once, read, close with X. No E mark is read, so a spare can
 never answer for it. A second click on the same tile would take the item off, so a tile is never clicked twice.
 decide(values,grade,title) runs with the window still open and always reads afresh; True means it left the window itself."""
 from owner_skill_ui import SkillUI
 from owner_mission_ui import MissionUI
 from owner_equipment_boxes import SLOTS
 adapter=service.adapter;blessing=slot in BLESSING_SLOTS
 x,y,w,h=BLESSING_SLOTS[slot] if blessing else SLOTS[slot]
 context.checkpoint();service.check();f=service.capture()
 if popup(f):raise RuntimeError('장비 상세창이 열린 채 시작 · 추가 입력 차단')
 # The bag can close by itself (a quest, a map change), and these places would then land on the field.
 from owner_progression import inventory_parts
 if inventory_parts(f)[0] is not True:
  LOG.info('착용 %s 현재값 건너뜀 · 인벤토리 화면 미확인',slot);return False
 cache=getattr(adapter,'_owner_worn_stats_cache',None)
 if cache is None:cache={};adapter._owner_worn_stats_cache=cache
 token=(profile,character,slot);old=cache.get(token)
 if decide is None and old and time.monotonic()<old['after']:return False
 cache[token]={'after':time.monotonic()+120}
 service.click_hit((x+w//2,y+h//2,(x,y,x+w,y+h)));opened=False;left=False
 for _ in range(10):
  context.wait(.2);context.checkpoint();service.check()
  if popup(service.capture()):opened=True;break
 if not opened:
  LOG.info('착용 %s 현재값 건너뜀 · 상세창 안 열림',slot);return False
 ui=SkillUI(adapter,context,inputs)
 try:
  title,grade=real_heading(np.asarray(service.capture().hi))
  MissionUI.wheel(ui,-1,10,at=(480,310),scene=popup)
  # Parked outside the window so no row lights up under the pointer. Nothing here presses its - or + buttons.
  with inputs.transaction():
   context.checkpoint();inputs._guard_target();inputs.move(550,110)
  context.wait(.25)
  values=settled_read(service,context)
  if not values:
   LOG.info('착용 %s 현재값 미확인 · 재시도 대기',slot);return False
  if grade is None:
   LOG.info('착용 %s 등급 미확인 · 현재값 저장 보류 · %s',slot,title);return False
  if blessing:
   from owner_growth_current import observe_blessing
   kind=blessing_kind(title)
   if kind is None:
    LOG.info('착용 %s 종류 미확인 · 현재값 저장 보류 · %s',slot,title);return False
   number=slot[-1]
   if not observe_blessing(adapter.project.root,profile,number+'번',kind,grade,values):return False
   LOG.info('착용 %s 현재값 확인 · %s · %s · 강화 %s · 개방 %s · 각성 %s',slot,kind,grade,values['enhance'],values.get('opening','미확인'),values['awaken'])
  else:
   from owner_growth_current import observe
   if grade not in ('일반','희귀','영웅'):
    LOG.info('착용 %s 등급 미확인 · 현재값 저장 보류 · %s',slot,grade);return False
   fields={'enhance':'enhancement','opening':'opening','breakthrough':'breakthrough','awaken':'awakening'}
   row={'character':profile,'item_identity':'worn-slot:'+slot,'slot':slot,'grade':grade,'verified_fields':[fields[k] for k in values],
        'replace_values':True,'source':'paired_equipped_tooltip_display_only'}
   row.update({fields[k]:v for k,v in values.items()})
   if not observe(adapter.project.root,row):return False
   LOG.info('착용 %s 현재값 확인 · 강화 %s · 개방 %s · 돌파 %s · 각성 %s',slot,values['enhance'],values.get('opening','미확인'),values.get('breakthrough','미확인'),values['awaken'])
  cache[token]={'after':time.monotonic()+1200}
  if decide is not None:left=decide(values,grade,title) is True
  return True
 finally:
  context.checkpoint();service.check()
  if left:return
  service.click_hit((510,106,(503,99,518,113)))
  for _ in range(10):
   context.wait(.2);context.checkpoint();service.check()
   if not popup(service.capture()):break
  else:raise RuntimeError('장비 상세창 종료 결과 미확인')

def inspect_slot(service,context,inputs,profile,character,slot='무기'):
 """One short, guarded tooltip inspection during an existing inventory visit.

 Uses the original worn slot and menu-close path. Different item names/icons
 and stat numbers are not templates. This function purchases/enhances nothing.
 """
 from owner_progression import inventory_parts
 from owner_equipment_boxes import SLOTS,agree
 from owner_ui_foreground import inventory_header
 from owner_inventory_filters import choose
 from owner_skill_ui import SkillUI
 from tools.ocr_support import get_paddle_engine
 adapter=service.adapter
 if slot not in SLOTS and slot not in BLESSING_SLOTS:return False
 context.checkpoint();service.check();a=service.capture()
 if getattr(a,'hi',None) is not None:return inspect_real(service,context,inputs,profile,character,slot)
 if slot not in SLOTS:return False
 context.wait(.12);b=service.capture()
 if unavailable_frame(a) and unavailable_frame(b):raise ReadOnlyViewUnavailable(slot)
 # Each skip says why: a silent False here hid ten of the eleven slots (11-04).
 if inventory_parts(a)!=(True,True) or inventory_parts(b)!=(True,True):
  LOG.info('착용 %s 현재값 건너뜀 · 인벤토리 화면 미확인',slot);return False
 if agree(a,b).get(slot) is not True:
  LOG.info('착용 %s 현재값 건너뜀 · 착용 표시 미확인',slot);return False
 if inventory_header(a,character) is None or inventory_header(b,character) is None:
  LOG.info('착용 %s 현재값 건너뜀 · 캐릭터 이름 미확인',slot);return False
 x,y,w,h=SLOTS[slot];icon_a=a[y+5:y+20,x+4:x+19];icon_b=b[y+5:y+20,x+4:x+19]
 if not np.array_equal(icon_a,icon_b):
  LOG.info('착용 %s 현재값 건너뜀 · 아이콘 흔들림',slot);return False
 cache=getattr(adapter,'_owner_worn_stats_cache',None)
 if cache is None:cache={};adapter._owner_worn_stats_cache=cache
 token=(profile,character,slot);signature=hashlib.sha256(icon_b.tobytes()).hexdigest();old=cache.get(token)
 if old and old['icon']==signature and time.monotonic()<old['after']:return False
 cache[token]={'icon':signature,'after':time.monotonic()+120}
 choose(service,context,'equipment')
 engine=get_paddle_engine(adapter.project.root,language='number')
 ui=SkillUI(adapter,context,inputs);opened=False
 try:
  context.checkpoint();service.check();f=service.capture()
  if inventory_parts(f)!=(True,True) or not np.array_equal(f[y+5:y+20,x+4:x+19],icon_b):return False
  service.click_hit((x+w//2,y+h//2,(x,y,x+w,y+h)));context.wait(.2)
  for _ in range(3):
   a=service.capture();context.wait(.12);context.checkpoint();service.check();b=service.capture()
   if popup(a) and popup(b):opened=True;break
   context.wait(.15)
  if not opened:
   if unavailable_frame(a) and unavailable_frame(b):raise ReadOnlyViewUnavailable(slot)
   yield_readonly_if_interrupted(service,context,inputs,slot,ui)
   raise RuntimeError('착용 장비 상세창 미확인 · 추가 입력 차단')
  from owner_mission_ui import MissionUI
  for _ in range(4):
   if table(service.capture()) is not None:break
   MissionUI.wheel(ui,-1,6,at=(480,310),scene=popup)
  # Wheel leaves the pointer over the numeric column. Park it outside the
  # tooltip before both captures; do not drag the game's scrollbar or click.
  if not popup(service.capture()):
   yield_readonly_if_interrupted(service,context,inputs,slot,ui)
   raise RuntimeError('장비 판독 전 상세창 재확인 필요')
  with inputs.transaction():
   context.checkpoint();inputs._guard_target();inputs.move(550,110)
  context.wait(.12)
  a=service.capture().copy();context.wait(.12)
  context.checkpoint();service.check();b=service.capture().copy()
  result=[];done=threading.Event()
  def recognize():
   try:
    places=real_table(np.asarray(a.hi)) if getattr(a,'hi',None) is not None else None
    result.extend((read(a,engine,places),read(b,engine,places)))
   except Exception:pass
   finally:done.set()
  threading.Thread(target=recognize,name='worn-stats-ocr',daemon=True).start()
  deadline=time.monotonic()+8
  while not done.wait(.05):
   context.checkpoint()
   if time.monotonic()>=deadline:LOG.info('장비 현재값 숫자 판독 대기 초과');return False
  context.checkpoint()
  first,second=result if len(result)==2 else (None,None)
  if not popup(a) or not popup(b) or not first or first!=second:
   LOG.info('착용 %s 현재값 미확인 · 재시도 대기 · %s / %s',slot,first,second);return False
  # Grade/type are a separate paired OCR reading, not inferred from rarity
  # colour or from the character's previous weapon.
  try:rows=ui.rows((385,123,136,37),pair_minimum=.94)
  except __import__('owner_skill_goal').Pending as exc:
   # Display-only OCR has no authority to abort the whole macro. Cleanup
   # below still requires this exact tooltip, a paired field/dialogue, or a
   # separately confirmed unavailable capture. No value/input is invented.
   cache.pop(token,None)
   LOG.info('착용 %s 등급 두 화면 판독 보류 · 현재값 미확정 · 같은 작업 재확인',slot)
   raise ReadOnlyViewUnavailable(slot) from exc
  words=[re.sub(r'\s+','',str(r['text'])) for r in rows if r['score']>=.94]
  grades=[g for g in ('일반','희귀','영웅') if g in words]
  if len(grades)!=1:
   LOG.info('착용 %s 등급 미확인 · 현재값 저장 보류',slot);return False
  from owner_growth_current import observe
  fields={'enhance':'enhancement','opening':'opening','breakthrough':'breakthrough','awaken':'awakening'}
  row={'character':profile,'item_identity':'worn-slot:'+slot,'slot':slot,'grade':grades[0],
       'verified_fields':[fields[k] for k in first],'replace_values':True,'source':'paired_equipped_tooltip_display_only'}
  row.update({fields[k]:v for k,v in first.items()})
  if observe(adapter.project.root,row):
   LOG.info('착용 %s 현재값 확인 · 강화 %s · 개방 %s · 돌파 %s · 각성 %s',
            slot,first.get('enhance','미확인'),first.get('opening','미확인'),first.get('breakthrough','미확인'),first.get('awaken','미확인'))
   cache[token]={'icon':signature,'after':time.monotonic()+(1200 if len(first)>=3 else 120)};return True
  return False
 except ChoreYield:
  cache.pop(token,None)
  raise
 finally:
  context.checkpoint();service.check();f=service.capture()
  if opened:
   if not popup(f):
    yield_readonly_if_interrupted(service,context,inputs,slot,ui)
    raise RuntimeError('장비 상세창 종료 위치 미확인 · 추가 입력 차단')
   service.click_hit((510,106,(503,99,518,113)));context.wait(.2)
   if popup(service.capture()) or inventory_parts(service.capture())!=(True,True):
    yield_readonly_if_interrupted(service,context,inputs,slot,ui)
    raise RuntimeError('장비 상세창 종료 결과 미확인')

FULL_SECONDS=100;STALE_SECONDS=12*3600
def stale_slots(root,profile,now=None):
 """Slots with no full reading, or an old one. The grey worn tile counts like any other."""
 from owner_equipment_boxes import SLOTS
 from owner_growth_current import display_snapshot
 now=time.time() if now is None else now
 snapshot=display_snapshot(root,profile)
 rows=[row for row in snapshot['equipment'].values() if isinstance(row,dict)]
 fresh=set()
 for row in rows:
  values=row.get('values',{})
  if row.get('slot') in SLOTS and all(field in values for field in FIELDS if field!='breakthrough') and now-row.get('at_epoch',0)<STALE_SECONDS:fresh.add(row['slot'])
 for slot in BLESSING_SLOTS:
  row=snapshot['values']['blessings'].get(slot[-1]+'번',{})
  values=row.get('values',{})
  if row.get('kind') and 'enhance' in values and 'awaken' in values and now-row.get('field_at',{}).get('awaken',0)<STALE_SECONDS:fresh.add(slot)
 return [slot for slot in (*SLOTS,*BLESSING_SLOTS) if slot not in fresh]

def refresh_when_stale(adapter,context,inputs):
 """Once per start at the hunting spot, so the table shows real values whatever is switched on."""
 from owner_hunt_rules_candidate import configured_identity
 if getattr(adapter,'_owner_worn_refresh_context',None) is context:return False
 adapter._owner_worn_refresh_context=context
 try:
  stale=stale_slots(adapter.project.root,configured_identity(adapter.project.root))
  if not stale:return False
  LOG.info('장비 현재값 갱신 · 오래됐거나 비어 있는 칸 확인 · %s',stale)
  inspect_equipped(adapter,context,inputs,max_seconds=FULL_SECONDS,only=stale);return True
 except (RuntimeError,ValueError,OSError,ChoreYield,ReadOnlyViewUnavailable) as exc:
  LOG.info('장비 현재값 갱신 보류 · %s',str(exc)[:100]);return False

def inspect_weapon(service,context,inputs,profile,character):
 return inspect_slot(service,context,inputs,profile,character,'무기')

SETTLE_SECONDS=2.
def settle_after_popup(service,context):
 """The tooltip fades out after it closes. Read too soon, the next slot looks like no inventory."""
 from owner_progression import inventory_parts
 end=time.monotonic()+SETTLE_SECONDS
 while time.monotonic()<end:
  context.checkpoint();service.check();frame=service.capture()
  if inventory_parts(frame)==(True,True) and not popup(frame):return True
  context.wait(.1)
 return False

def inspect_equipped(adapter,context,inputs,max_seconds=15,only=None):
 """Refresh other slots during the existing growth opportunity, bounded. `only` names the slots wanted; none opens nothing."""
 if only is not None and not only:return
 from owner_progression import state,open_inventory_by_key,inventory_parts
 from owner_equipment_boxes import SLOTS,close_inventory
 from owner_hunt_rules_candidate import configured_identity
 from project_adapter.town_services import TownServices
 from project_adapter import market_inventory
 progress=state(adapter)
 if not progress.character or not 0<=time.monotonic()-progress.observed<=180:return
 profile=configured_identity(adapter.project.root)
 service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES)
 initially_open=inventory_parts(service.capture())==(True,True)
 if open_inventory_by_key(service) is False:return
 end=time.monotonic()+max_seconds
 resume=getattr(adapter,'_owner_worn_resume',None)
 slots=[slot for slot in (*SLOTS,*BLESSING_SLOTS) if only is None or slot in only]
 if resume and resume[:2]==(profile,progress.character) and resume[2] in slots:
  slots=slots[slots.index(resume[2]):]
 read=[]
 try:
  for slot in slots:
   context.checkpoint()
   if time.monotonic()>=end:break
   if state(adapter).character!=progress.character or configured_identity(adapter.project.root)!=profile:
    raise RuntimeError('장비 현재값 확인 중 캐릭터 변경 · 입력 차단')
   adapter._owner_worn_resume=(profile,progress.character,slot)
   settle_after_popup(service,context)
   if inspect_slot(service,context,inputs,profile,progress.character,slot) is True:read.append(slot)
  else:adapter._owner_worn_resume=None
 finally:
  context.checkpoint();service.check();f=service.capture()
  if popup(f):raise RuntimeError('장비 현재값 확인 후 상세창 종료 미확인')
  if not initially_open and inventory_parts(f)==(True,True):close_inventory(service)
 return read
