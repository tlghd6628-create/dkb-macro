"""Required story purchase reuses Adapter.run_potion_purchase unchanged.

No custom shop navigation, cart/quantity reader, purchase button or image.
Only connect the known objective and consume3 if native full proof appears.
"""
from contextlib import contextmanager
import logging,re,time
import numpy as np
from owner_skill_goal import Pending
LOG=logging.getLogger('project_gui.DKB')
NEEDED=3
# Real pixels on the 1366x768 screen.
LIMIT_NAME=(75,108,200,22);LIMIT_ROW=(75,150,180,20)
GOAL_COUNT=(790,262,85,20)  # the first objective's count, in the frame's own terms
# The bag's consumables tab and its windows.
TILE_FIRST=(1095,175);TILE_STEP=(60,59);TILE_ROWS=9;TILE_FULL=10.;KEPT_TIER='1';TIER_LOOKS=30
TIP_KIND=(700,205,110,45);TIP_TITLE=(590,160,178,22);TIP_CLOSE=(782,171);TRASH=(588,543);POTION_KIND='체력물약'
AUTO_USE=(735,498,60,24);AUTO_USE_PRESS=(765,510);SLOTS=5;SLOT_STEP=52;SLOT_DIGITS=(572,725,34,15);SLOT_PRESS=(581,722)
QUANTITY_BOX=(610,232,150,26);QUANTITY_ITEM=(610,275,170,50);QUANTITY_AMOUNT=(640,360,60,24);QUANTITY_OK=(745,457);QUANTITY_CANCEL=(620,457);QUANTITY_TITLE='수량입력'
NOTICE_BOX=(560,360,250,30);DELETE_OK=(751,444);DELETE_NOTICE='복구할수없습니다'

class PotionFull(BaseException):pass

def eligible_root(row):
 return bool(row.get('mode')=='sub_quest' and row.get('group') and not row.get('completed') and '메마른' in str(row.get('title','')))

def counter(rows):
 values={int(m[1]) for r in rows if r.get('score',0)>=.98
         for m in [re.fullmatch(r'\s*([0-3])\s*/\s*3\s*',str(r.get('text','')))] if m}
 return next(iter(values)) if len(values)==1 else None

def observe_stage(ui):
 from owner_skill_ui import quest_screen
 from owner_mission_reading import selected_center
 if not quest_screen(ui.frame()):return None
 # Groups.select already proved this known root and its selected current
 # leaf. Reuse that ownership instead of re-OCRing its small title again.
 center=selected_center(ui.frame())
 if center is None:return None
 def ratio(answer,floor=.98):
  values={(int(m[1]),int(m[2])) for r in answer if r.get('score',0)>=floor
          for m in [re.fullmatch(r'\s*(\d{1,2})\s*/\s*(\d{1,2})\s*',str(r.get('text','')))] if m}
  return next(iter(values)) if len(values)==1 else None
 if getattr(ui.frame(),'hi',None) is not None:
  # The objective's count on the real screen, the same on two looks. The shrunken number never reached .98.
  from owner_text import read,word_box
  values=[]
  for _ in range(2):
   frame=ui.frame();values.append(ratio(read(ui.adapter.project.root,frame,word_box(GOAL_COUNT),scale=3),.85));ui.context.wait(.12)
 else:
  ui.rows((832,264,40,17),language='number',pair_minimum=.98)
  pair=getattr(ui,'_owner_last_rows_pair',None)
  values=[ratio(a) for a in pair[2]] if pair else []
 LOG.info('퀘스트 필수 구매 목표 대조 · 수량=%s',values)
 if len(values)!=2 or values[0] is None or values[0]!=values[1] or selected_center(ui.frame())!=center:return None
 done,total=values[0]
 if not 0<=done<=total:return None
 if total==3:return {'stage':2,'done':done}
 # Observed following stage is the two 10-kill objectives. Other ratios
 # never authorize shopping or assert the whole chapter complete.
 if total==10:return {'stage':3,'done':None}
 return None

def needs_purchase(stage,receipt):
 if not stage or stage['stage']!=2 or stage['done']==3:return False
 if receipt.get('phase') in ('purchase_sent','await_goal','use_sent'):
  raise Pending('퀘스트 물약 이전 입력 결과 확인 필요 · 재구매·추가 사용 없음')
 return True

@contextmanager
def native_purchase_watch(adapter,context,ui,receipt,commit,guard):
 """Observe the SAME existing native calls; never send an alternate click."""
 from project_adapter.town_services import TownServices
 import owner_remote_potion_limit_candidate as limits
 previous_button=TownServices.button;previous_full=limits.observed_full;previous_cached=limits.cached_full
 evidence={'full':False,'buy_sent':False}
 def full(probe,tier):
  value=previous_full(probe,tier)
  if probe.adapter is adapter and probe.context is context and value is not None:
   guard();evidence['full']=True
   if evidence['buy_sent']:raise Pending('물약 구매 후 결과 확인 필요 · 추가 사용 없음')
   receipt['to_use']=3
   raise PotionFull()
  # The town row shows what is held against the limit, and holding over it (320/250) still counts as full.
  counts=over_limit(probe) if probe.adapter is adapter and probe.context is context and not evidence['buy_sent'] else None
  if counts and counts[0]+NEEDED>counts[1]:
   guard();evidence['full']=True
   receipt['to_use']=counts[0]+NEEDED-counts[1]
   LOG.info('퀘스트 필수 구매 · 보유 %d/%d · 구매 전 물약 사용 필요',*counts)
   raise PotionFull()
  return value
 def button(service,name,*a,**k):
  if getattr(service,'context',None) is context:
   guard()
   if name in ('버튼_물약상인_1단물약','버튼_물약상인_MAX'):
    # Non-membership uses the original town merchant and full-screen reader.
    full(ui,'1단물약')
   if name=='버튼_물약상인_구매':
    if evidence['buy_sent']:raise Pending('같은 퀘스트 중복 구매 입력 차단')
    evidence['buy_sent']=True;receipt.update(phase='purchase_sent',sent_at=time.time());commit()
  return previous_button(service,name,*a,**k)
 def cached(other,tier):
  # This required quest needs fresh full proof; ordinary cache is unchanged.
  return False if other is adapter else previous_cached(other,tier)
 TownServices.button=button;limits.observed_full=full;limits.cached_full=cached
 try:yield evidence
 finally:TownServices.button=previous_button;limits.observed_full=previous_full;limits.cached_full=previous_cached

def over_limit(ui):
 """(held, limit) from the shop's first row, 구매 가능 320/250, where two real frames agree. Or None."""
 import owner_text as text
 found=[]
 for _ in range(2):
  frame=ui.frame()
  if getattr(frame,'hi',None) is None or not text.find(text.read(None,frame,LIMIT_NAME),'1단'):return None
  rows=[re.search(r'(\d{1,5})\s*/\s*(\d{1,5})',str(r['text'])) for r in text.read(None,frame,LIMIT_ROW)]
  rows=[(int(m[1]),int(m[2])) for m in rows if m]
  if len(rows)!=1:return None
  found.append(rows[0]);ui.context.wait(.12)
 return found[0] if found[0]==found[1] else None

def _press(ui,point,proof):
 from owner_hd import logical_of
 frame=ui.frame();x,y=logical_of(point[0],point[1],getattr(frame,'layout',None))
 ui.click(x,y,proof)

def _words(frame,box,scale=3):
 from owner_text import clean,read_area
 x,y,w,h=box
 return clean(''.join(r['text'] for r in read_area(None,np.asarray(frame.hi)[y:y+h,x:x+w],scale=scale,minimum=.5)))

def occupied_tiles(frame):
 """Bag tiles with something on them, last first: potions sort to the end. An empty tile measures about 2, a full one 50 or more."""
 real=np.asarray(frame.hi);found=[]
 for row in range(TILE_ROWS):
  for column in range(4):
   x,y=TILE_FIRST[0]+TILE_STEP[0]*column,TILE_FIRST[1]+TILE_STEP[1]*row
   if float(real[y-18:y+18,x-18:x+18].std())>=TILE_FULL:found.append((x,y))
 return found[::-1]

def _is_potion(frame):return POTION_KIND in _words(frame,TIP_KIND)

def _tier(ui):
 """The open potion's tier from its title. The title scrolls, so its start comes round every few seconds."""
 for _ in range(TIER_LOOKS):
  found=re.search(r'([1-9])단',_words(ui.frame(),TIP_TITLE))
  if found:return found[1]
  ui.context.wait(.4)
 return None

def quick_counts(frame):
 """Each quick slot's count, or None where none reads. White when in stock, red at nothing or low."""
 from owner_text import clean,read_area
 real=np.asarray(frame.hi);counts=[]
 for slot in range(SLOTS):
  x,y,w,h=SLOT_DIGITS[0]+SLOT_STEP*slot,*SLOT_DIGITS[1:];part=real[y:y+h,x:x+w].astype(np.int16)
  red=(part[:,:,0]>150)&(part[:,:,0]-part[:,:,1]>70)&(part[:,:,0]-part[:,:,2]>50)&(part[:,:,2]>45)
  lifted=np.stack([255-(red|(part.min(axis=2)>170)).astype(np.uint8)*255]*3,axis=2)
  values=[clean(r['text']) for r in read_area(None,lifted,language='number',scale=4,minimum=.8)]
  counts.append(int(values[0]) if len(values)==1 and values[0].isdigit() else None)
 return counts

def _held(frame):
 found=re.search(r'(\d+)개',_words(frame,TIP_KIND))
 return int(found[1]) if found else None

def _open_first_tier(ui,guard):
 """Leave the 1단 potion's tooltip open, or return False with none open. A tile is pressed once a look: a second press
 uses what is on it, and that could open a box."""
 from owner_equipment_tooltip_candidate import window_open
 for point in occupied_tiles(ui.frame()):
  guard();_press(ui,point,lambda f:guard() and not window_open(f))
  ui.wait(window_open,seconds=4)
  if _is_potion(ui.frame()) and _tier(ui)==KEPT_TIER:return True
  _press(ui,TIP_CLOSE,window_open);ui.wait(lambda f:not window_open(f),seconds=3)
 return False

def _discard_open_potion(ui,guard):
 """The open potion's whole stack: the quantity window opens at its maximum."""
 from owner_equipment_tooltip_candidate import window_open
 def tip(f):return guard() and _is_potion(f)
 def quantity(f):return guard() and QUANTITY_TITLE in _words(f,QUANTITY_BOX)
 def notice(f):return guard() and DELETE_NOTICE in _words(f,NOTICE_BOX,2)
 # A press too soon after the tooltip opens does nothing. Pressing again here is harmless.
 ui.context.wait(2)
 for _ in range(3):
  _press(ui,TRASH,tip)
  try:ui.wait(quantity,seconds=2);break
  except Pending:pass
 else:raise Pending('물약 버리기 수량 창 확인 필요')
 frame=ui.frame()
 if KEPT_TIER+'단' not in _words(frame,QUANTITY_ITEM) or POTION_KIND not in _words(frame,QUANTITY_ITEM):
  _press(ui,QUANTITY_CANCEL,quantity);raise Pending('수량 창 물품이 1단 물약이 아님 · 입력 취소')
 amount=_words(frame,QUANTITY_AMOUNT)
 _press(ui,QUANTITY_OK,quantity);ui.wait(notice,seconds=3)
 _press(ui,DELETE_OK,notice)
 ui.wait(lambda f:guard() and not window_open(f),seconds=5)
 return amount

def discard_first_tier(ui,guard):
 """(how many were thrown away or None, the quick slot they sat on or None). Other tiers stay."""
 from owner_skill_box import _close_bag,_open_bag
 try:
  _open_bag(ui)
  if not _open_first_tier(ui,guard):return None,None
  frame=ui.frame();held=_held(frame);counts=quick_counts(frame)
  slot=counts.index(held) if held is not None and held in counts else None
  return _discard_open_potion(ui,guard),slot
 finally:_close_bag(ui)

def restore_first_tier(ui,guard,slot):
 """Back on its quick slot with automatic use on. Pressing a slot with the tooltip open registers it, and that also turns
 automatic use on. With no slot of its own it takes the first one not holding stock."""
 from owner_equipment_tooltip_candidate import window_open
 from owner_skill_box import _close_bag,_open_bag
 try:
  _open_bag(ui)
  if not _open_first_tier(ui,guard):raise Pending('구매한 1단 물약 칸 확인 필요')
  frame=ui.frame();held=_held(frame);counts=quick_counts(frame)
  if held is None:raise Pending('1단 물약 수량 확인 필요')
  ui.context.wait(2)
  if held not in counts:
   if slot is None:slot=next((i for i,count in enumerate(counts) if not count),None)
   if slot is None:raise Pending('물약 등록할 빈 칸 없음')
   _press(ui,(SLOT_PRESS[0]+SLOT_STEP*slot,SLOT_PRESS[1]),lambda f:guard() and window_open(f) and _is_potion(f))
   ui.wait(lambda f:quick_counts(f)[slot]==held,seconds=4)
  if 'OFF' in _words(ui.frame(),AUTO_USE).upper():
   _press(ui,AUTO_USE_PRESS,lambda f:guard() and window_open(f) and _is_potion(f))
   ui.wait(lambda f:'OFF' not in _words(f,AUTO_USE).upper(),seconds=3)
  _press(ui,TIP_CLOSE,window_open);ui.wait(lambda f:not window_open(f),seconds=3)
  LOG.info('퀘스트 필수 구매 · 1단 물약 %s개 빠른 칸 등록 · 자동 사용 켬',held)
 finally:_close_bag(ui)

def execute(ui,book,key):
 row=book.item['quests'][key]
 if not eligible_root(row):return False
 stage=observe_stage(ui)
 if not stage:return False
 receipt=row.setdefault('quest_purchase',{'phase':'observed','used':0})
 if stage['stage']>2 or stage.get('done')==3:
  if receipt.get('phase') in ('purchase_sent','await_goal'):
   receipt.update(phase='confirmed',confirmed_at=time.time(),proof='same_root_next_stage_or_three_of_three');book.commit()
   LOG.info('퀘스트 구매 조건 완료 확인 · %s · 현재 단계=%s',row['title'],stage['stage'])
  return False
 if not needs_purchase(stage,receipt):return False
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 from project_adapter.town_services import _close_potion_screen
 adapter=ui.adapter;context=ui.context;character=state(adapter).character;scope=configured_identity(adapter.project.root)
 def guard():
  context.checkpoint()
  if not character or state(adapter).character!=character or configured_identity(adapter.project.root)!=scope or book.item.get('active')!=key:
   raise Pending('퀘스트 물약 캐릭터·대상 변경')
  return True
 guard();receipt.update(phase='preflight',goal_before=stage['done'],route='existing_potion_purchase');book.commit()
 ui.close_known()
 # User's rule: throw away the 1단 stack and buy again. Holding over the limit blocks the purchase, and full health blocks
 # drinking, so nothing else clears this reliably. Other tiers stay.
 try:
  discarded,slot=discard_first_tier(ui,guard)
 except Pending as exc:
  LOG.info('퀘스트 필수 구매 보류 · 물약 버리기 미완료 · %s · %s',exc,row['title'])
  book.defer(key,'condition',detail='물약 버리기 미완료 · '+str(exc));return True
 LOG.info('퀘스트 필수 구매 · 1단 물약 버림 · %s개 · 빠른 칸 %s · %s',discarded,slot,row['title'])
 receipt.update(phase='discarded',discarded=discarded,slot=slot);book.commit()
 # The merchant must be seen again: the hour's rest after a full stack is for the ordinary top-up.
 adapter._owner_potion_full_at=-1e30
 guard();full=False
 try:
  with native_purchase_watch(adapter,context,ui,receipt,book.commit,guard) as result:
   LOG.info('퀘스트 필수 구매 · 기존 물약 전체 구매 경로 실행 · %s',row['title'])
   adapter.run_potion_purchase(context,ui.inputs)
 except PotionFull:
  full=True
 if full:
  if not ui.normal():_close_potion_screen(ui.service)
  book.defer(key,'condition',detail='물약을 버린 뒤에도 구매 불가');return True
 if result['buy_sent']:
  receipt.update(phase='await_goal',requested_at=time.time());book.commit()
  LOG.info('기존 물약 구매 요청 종료 · 같은 서사에서 실제 구매 조건 완료 확인')
  adapter._owner_restore_story_once=False
  # Buying is what this step asks. The quest's own result stays in await_goal; a failure here costs only the slot.
  try:restore_first_tier(ui,guard,slot)
  except Pending as exc:LOG.info('1단 물약 빠른 칸 복구 보류 · %s',exc)
  return True
 receipt.update(phase='not_purchased');book.commit()
 raise Pending('기존 물약 구매가 실행되지 않음 · 임무 미완료 유지')
