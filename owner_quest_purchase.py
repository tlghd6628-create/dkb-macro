"""Required story purchase reuses Adapter.run_potion_purchase unchanged.

No custom shop navigation, cart/quantity reader, purchase button or image.
Only connect the known objective and consume3 if native full proof appears.
"""
from contextlib import contextmanager
import logging,re,time
from owner_skill_goal import Pending
LOG=logging.getLogger('project_gui.DKB')

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

def consume_three(ui,receipt,commit,guard):
 """User layout: tier1 Ctrl1, tier2 Ctrl2, tier3 Ctrl3. No slot guessing."""
 from owner_shop_runtime_candidate import _number
 if receipt.get('used',0)>=3:raise Pending('물약 3개 사용 후에도 구매 불가 · 추가 사용 없음')
 if not ui.normal():raise Pending('물약 사용 전 일반 필드 확인 필요')
 while receipt.get('used',0)<3:
  guard();before=_number(ui,(381,445,25,13),minimum=.97)
  if before<3-receipt.get('used',0):raise Pending('첫 칸 1단 물약 수량 부족')
  receipt.update(phase='use_sent',use_before=before,use_sent_at=time.time());commit()
  ui.click(385,443,lambda f:ui.normal_frame(f) and guard())
  end=time.monotonic()+4
  while True:
   guard();after=_number(ui,(381,445,25,13),minimum=.97)
   if after==before-1:break
   if after!=before or time.monotonic()>=end:raise Pending('물약 사용 후 1개 감소 확인 필요 · 추가 사용 없음')
   ui.context.wait(.4)
  receipt.update(phase='full',used=receipt.get('used',0)+1,use_after=after);commit();ui.context.wait(.6)

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
   receipt.update(phase='full');book.commit();consume_three(ui,receipt,book.commit,guard)
   continue
  if result['buy_sent']:
   receipt.update(phase='await_goal',requested_at=time.time());book.commit()
   LOG.info('기존 물약 구매 요청 종료 · 같은 서사에서 실제 구매 조건 완료 확인')
   adapter._owner_restore_story_once=False
   return True
  receipt.update(phase='not_purchased');book.commit()
  # The town merchant shows 구매 불가 while the bag holds over the limit (821/250, 11-05), and a story that asks
  # for a purchase then repeated until the run ended. It waits; every other story goes on. The quest stays open.
  LOG.info('퀘스트 필수 구매 불가 · 물약 한도 초과 · 이 서사 보류 후 다음 서사 진행 · %s',row['title'])
  book.defer(key,'condition',detail='물약 구매 한도 초과 · 구매 조건 대기')
  return True
 raise Pending('물약 사용 후에도 구매 불가 · 추가 사용 없음')
