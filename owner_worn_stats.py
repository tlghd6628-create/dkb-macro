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

def table(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return None
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

def read(frame,engine):
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
 from owner_progression import inventory_parts
 from owner_energy_box_detail_candidate import close_mark
 from owner_equipment_tooltip_candidate import _score,badge
 return bool(inventory_parts(frame)==(True,True) and close_mark(frame)
             and _score(frame[116:135,420:445],badge())>=.96)

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
 if slot not in SLOTS:return False
 context.checkpoint();service.check();a=service.capture();context.wait(.12);b=service.capture()
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
   try:result.extend((read(a,engine),read(b,engine)))
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
   LOG.info('착용 %s 현재값 미확인 · 재시도 대기',slot);return False
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
 rows=[row for row in display_snapshot(root,profile)['equipment'].values() if isinstance(row,dict)]
 fresh=set()
 for row in rows:
  values=row.get('values',{})
  if row.get('slot') in SLOTS and all(field in values for field in FIELDS if field!='breakthrough') and now-row.get('at_epoch',0)<STALE_SECONDS:fresh.add(row['slot'])
 return [slot for slot in SLOTS if slot not in fresh]

def refresh_when_stale(adapter,context,inputs):
 """Once per start at the hunting spot, so the table shows real values whatever is switched on."""
 from owner_hunt_rules_candidate import configured_identity
 if getattr(adapter,'_owner_worn_refresh_context',None) is context:return False
 adapter._owner_worn_refresh_context=context
 try:
  if not stale_slots(adapter.project.root,configured_identity(adapter.project.root)):return False
  LOG.info('장비 현재값 갱신 · 오래됐거나 비어 있는 칸 확인')
  inspect_equipped(adapter,context,inputs,max_seconds=FULL_SECONDS);return True
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

def inspect_equipped(adapter,context,inputs,max_seconds=15):
 """Refresh other slots during the existing growth opportunity, bounded."""
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
 slots=list(SLOTS)
 if resume and resume[:2]==(profile,progress.character) and resume[2] in slots:
  slots=slots[slots.index(resume[2]):]
 try:
  for slot in slots:
   context.checkpoint()
   if time.monotonic()>=end:break
   if state(adapter).character!=progress.character or configured_identity(adapter.project.root)!=profile:
    raise RuntimeError('장비 현재값 확인 중 캐릭터 변경 · 입력 차단')
   adapter._owner_worn_resume=(profile,progress.character,slot)
   settle_after_popup(service,context)
   inspect_slot(service,context,inputs,profile,progress.character,slot)
  else:adapter._owner_worn_resume=None
 finally:
  context.checkpoint();service.check();f=service.capture()
  if popup(f):raise RuntimeError('장비 현재값 확인 후 상세창 종료 미확인')
  if not initially_open and inventory_parts(f)==(True,True):close_inventory(service)
