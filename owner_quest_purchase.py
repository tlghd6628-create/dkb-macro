"""Required story purchase reuses Adapter.run_potion_purchase unchanged.

No custom shop navigation, cart/quantity reader, purchase button or image.
Only connect the known objective and consume3 if native full proof appears.
"""
from contextlib import contextmanager
import logging,re,time
from owner_skill_goal import Pending
LOG=logging.getLogger('project_gui.DKB')
NEEDED=3
# Real pixels on the 1366x768 screen.
LIMIT_NAME=(75,108,200,22);LIMIT_ROW=(75,150,180,20);SLOT_COUNT=(562,722,44,24);SLOT_PRESS=(581,722)

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
 ui.rows((832,264,40,17),language='number',pair_minimum=.98)
 pair=getattr(ui,'_owner_last_rows_pair',None)
 def ratio(answer):
  values={(int(m[1]),int(m[2])) for r in answer if r.get('score',0)>=.98
          for m in [re.fullmatch(r'\s*(\d{1,2})\s*/\s*(\d{1,2})\s*',str(r.get('text','')))] if m}
  return next(iter(values)) if len(values)==1 else None
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

def slot_count(ui):
 """Potions left in the first quick slot, on the real screen. Or None."""
 from owner_text import read_area
 import numpy as np
 x,y,w,h=SLOT_COUNT;real=np.asarray(ui.frame().hi)
 values=[r['text'] for r in read_area(None,real[y:y+h,x:x+w],language='number',scale=3,minimum=.6) if re.fullmatch(r'\d{1,4}',str(r['text']).strip())]
 return int(values[0]) if len(values)==1 else None

def use_potions(ui,receipt,commit,guard):
 """User layout: the potion on Ctrl1. Each use is proved by the slot's count falling; a press with no effect is pressed again."""
 import owner_hd as hd
 from owner_movement import field_hud
 need=receipt.get('to_use',3);start=slot_count(ui)
 if start is None:raise Pending('첫 칸 물약 수량 판독 필요')
 if start<need:raise Pending('첫 칸 물약 수량 부족 · %d/%d'%(start,need))
 LOG.info('퀘스트 필수 구매 · 한도 아래로 물약 %d개 사용 · 첫 칸 %d개',need,start)
 frame=ui.frame();x,y=hd.logical_of(SLOT_PRESS[0],SLOT_PRESS[1],getattr(frame,'layout',None))
 receipt.update(phase='using',use_before=start);commit()
 used=0;last=time.monotonic();end=last+need*6+30
 while used<need:
  guard()
  if time.monotonic()>=end or time.monotonic()-last>=20:raise Pending('물약 사용 후 수량 감소 확인 필요 · %d/%d'%(used,need))
  ui.click(x,y,lambda f:field_hud(f) and guard());ui.context.wait(.5)
  now=slot_count(ui)
  if now is not None and now<start-used:
   used=start-now;last=time.monotonic()
   receipt.update(used=used,use_after=now)
 receipt.update(phase='full');commit()
 LOG.info('퀘스트 필수 구매 · 물약 %d개 사용 완료',used)

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
 # The merchant must be seen again: the hour's rest after a full stack is for the ordinary top-up.
 adapter._owner_potion_full_at=-1e30
 for attempt in range(2):
  guard();full=False
  try:
   with native_purchase_watch(adapter,context,ui,receipt,book.commit,guard) as result:
    LOG.info('퀘스트 필수 구매 · 기존 물약 전체 구매 경로 실행 · %s',row['title'])
    adapter.run_potion_purchase(context,ui.inputs)
  except PotionFull:
   full=True
  if full:
   if not ui.normal():_close_potion_screen(ui.service)
   if not ui.normal():raise Pending('물약 사용 전 기존 상점 종료 확인 필요')
   receipt.update(phase='full');book.commit()
   try:use_potions(ui,receipt,book.commit,guard)
   except Pending as exc:
    # Not enough in the slot, or the count would not fall. The quest stays open and the other stories go on.
    LOG.info('퀘스트 필수 구매 보류 · %s · %s',exc,row['title'])
    book.defer(key,'condition',detail='물약 사용 미완료 · '+str(exc));return True
   adapter._owner_potion_full_at=-1e30
   continue
  if result['buy_sent']:
   receipt.update(phase='await_goal',requested_at=time.time());book.commit()
   LOG.info('기존 물약 구매 요청 종료 · 같은 서사에서 실제 구매 조건 완료 확인')
   adapter._owner_restore_story_once=False
   return True
  receipt.update(phase='not_purchased');book.commit()
  raise Pending('기존 물약 구매가 실행되지 않음 · 임무 미완료 유지')
 raise Pending('물약 사용 후에도 구매 불가 · 추가 사용 없음')
