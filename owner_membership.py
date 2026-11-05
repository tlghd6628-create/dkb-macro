"""Explicit membership choice; ordinary guarded remote-store UI."""
from pathlib import Path
from functools import wraps,lru_cache
import json,logging,threading,time
from owner_timetable import read,save
from owner_skill_goal import Pending
from biol_base.session import Cancelled
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()

class RemoteShopDeferred(Pending):
 """No shop consumption, known menus closed and field return verified."""

def _pair(ui,proof):
 a=ui.frame();ui.context.wait(.12);ui.context.checkpoint();b=ui.frame()
 return bool(proof(a) and proof(b))

def _inventory_popup(frame):
 from owner_energy_box_detail_candidate import generic_box_detail
 from owner_energy_choice_reader_candidate import layout_screen
 if layout_screen(frame):return 'energy_selection'
 if generic_box_detail(frame):return 'box_detail'
 return None

def _defer_known_inventory_popup(ui):
 """Only the old known X-close path; never select, confirm or consume."""
 a=ui.frame();kind=_inventory_popup(a)
 if kind is None:return False
 ui.context.wait(.12);ui.context.checkpoint()
 if _inventory_popup(ui.frame())!=kind:raise Pending('원격 물약 전 이전 인벤토리 창 전환 중 · 입력 없음')
 from owner_progression import state,inventory_parts
 from owner_hunt_rules_candidate import configured_identity
 from owner_energy_box_port_candidate import Port
 adapter=ui.adapter;root=adapter.project.root
 character=state(adapter).character;scope=configured_identity(root)
 def guard():
  ui.context.checkpoint()
  if not character or state(adapter).character!=character or configured_identity(root)!=scope:
   raise Pending('원격 물약 전 메뉴 정리 캐릭터·설정 변경')
 guard();port=Port(adapter,ui.context,ui.inputs)
 # The original Port closes only its exact known selector/detail X and the
 # inventory. Fence each native key/click with the same character/profile.
 for name in ('key','click_hit'):
  original=getattr(port.service,name)
  def fenced(*args,_original=original,**kwargs):guard();return _original(*args,**kwargs)
  setattr(port.service,name,fenced)
 port.opened=True;port.view='selection' if kind=='energy_selection' else 'detail'
 try:port.close_known()
 except Cancelled:raise
 except Exception as exc:raise Pending('원격 물약 전 이전 상자 창 종료 미확인 · 다음 작업 차단') from exc
 guard()
 if not _pair(ui,lambda f:inventory_parts(f)==(False,False) and ui.normal_frame(f)):
  raise Pending('원격 물약 전 메뉴 정리 후 일반 필드 미확인 · 다음 작업 차단')
 adapter._owner_remote_potion_navigation_hold=kind
 LOG.warning('원격 물약 보류 · 이전 %s 창만 기존 X 경로로 종료 · 일반 필드 확인 · 상점 구매 입력 0회',kind)
 return True

class QuotaMessage(logging.Filter):
 def filter(self,record):
  import re
  text=record.getMessage()
  found=re.fullmatch(r'(일일|주간) 임무 5/5 확인 · 수락·자동진행 건너뜀',text)
  if found:
   record.msg=found[1]+' 임무 남은 완료 가능 횟수 0/5 확인 · 수락·자동진행 건너뜀';record.args=()
  return True

def settings(root):return read(Path(root)/'settings/owner-membership.json',{'version':1,'paid':False})
def paid(root):return settings(root).get('paid') is True
def set_paid(root,value):save(Path(root)/'settings/owner-membership.json',{'version':1,'paid':bool(value)})

@lru_cache(maxsize=4)
def asset(name):
 from PIL import Image
 import numpy as np
 return np.asarray(Image.open(Path(__file__).parent/'assets/mission-catalog'/(name+'.png')).convert('RGB'))

def hit(frame,name,box,threshold=.94):
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return None
 x,y,w,h=box;needle=asset(name);patch=frame[y:y+h,x:x+w]
 if patch.shape[0]<needle.shape[0] or patch.shape[1]<needle.shape[1]:return None
 _,score,_,p=cv2.minMaxLoc(np.nan_to_num(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED),nan=-1))
 if score<threshold:return None
 hh,ww=needle.shape[:2];l,t=x+p[0],y+p[1]
 return l+ww//2,t+hh//2,(l,t,l+ww,t+hh)

def remote_shop_screen(frame):
 """Independent foreground title and the existing exact potion-list label."""
 import numpy as np
 from owner_remote_potion_limit_candidate import _asset
 from owner_visual_state import same_label
 found=hit(frame,'remote-shop-title',(35,4,110,30))
 foreground=False
 if not found and getattr(frame,'shape',None)==(479,897,3):
  # Exact core-glyph/negative-space proof; antialias pixels are neutral.
  # Every core pixel and every dark-space pixel must agree, at one unique
  # location. This does not lower an RGB/template threshold for scenery.
  reference=asset('remote-shop-title');ink=reference.min(axis=2)>190;dark=reference.max(axis=2)<100
  area=frame[4:34,35:145].min(axis=2);h,w=ink.shape;points=[]
  if ink.sum()>=80 and dark.sum()>=100:
   for y in range(area.shape[0]-h+1):
    for x in range(area.shape[1]-w+1):
     sample=area[y:y+h,x:x+w]
     if np.all(sample[ink]>170) and np.all(sample[dark]<150):points.append((x,y))
  if len(points)==1:
   x,y=points[0];found=(35+x+w//2,4+y+h//2,(35+x,4+y,35+x+w,4+y+h));foreground=True
 if not found:return False
 l,t,r,b=found[2];mask=asset('remote-shop-title').min(axis=2)>(190 if foreground else 170)
 if mask.sum()<20 or float((frame[t:b,l:r].min(axis=2)[mask]>150).mean())<.95:return False
 # This is shop identity only. Tier1 is grey after its quota is exhausted
 # and white while purchasable. Availability/quantity are checked later.
 return same_label(frame,_asset('tier1'),(49,69,84,11))

def open_remote(adapter,context,inputs):
 from owner_skill_ui import SkillUI,Pending
 from owner_progression import open_inventory_by_key,inventory_parts
 ui=SkillUI(adapter,context,inputs);adapter.exit_sleep_mode(context,inputs)
 adapter._owner_remote_potion_navigation_hold=None
 if _defer_known_inventory_popup(ui):raise RemoteShopDeferred('이전 상자 창 정리 · 이번 물약 작업 보류')
 frame=ui.frame()
 if _pair(ui,remote_shop_screen):return ui
 if hit(frame,'remote-shop-title',(35,4,110,30)):
  raise Pending('원격 잡화상점 제목은 보이나 전경 목록·후속 창 확인 필요 · 입력 없음')
 open_inventory_by_key(ui.service)
 if _defer_known_inventory_popup(ui):raise RemoteShopDeferred('인벤토리 상자 창 정리 · 이번 물약 작업 보류')
 first=hit(ui.frame(),'remote-merchant',(670,43,36,39));context.wait(.15)
 second=hit(ui.frame(),'remote-merchant',(670,43,36,39))
 if not first or not second:raise Pending('인벤토리 원격 잡화상점 표시 확인 필요')
 ui.click(second[0],second[1],lambda f:inventory_parts(f)==(True,True) and _inventory_popup(f) is None and hit(f,'remote-merchant',(670,43,36,39)) is not None)
 try:ui.wait(remote_shop_screen)
 except Pending as exc:
  if _defer_known_inventory_popup(ui):raise RemoteShopDeferred('상점 전환 대신 이전 상자 창 확인 · 이번 물약 작업 보류') from exc
  if _pair(ui,lambda f:inventory_parts(f)==(False,False) and ui.normal_frame(f)):
   adapter._owner_remote_potion_navigation_hold='unchanged_field'
   raise RemoteShopDeferred('원격 잡화상점 진입 미확인 · 일반 필드 유지 · 구매 없음') from exc
  raise Pending('원격 잡화상점 진입 시간 초과 · 상점 또는 후속 창 미확인 · 구매 입력 없음') from exc
 LOG.info('멤버십 물약 구매 · 인벤토리 원격 잡화상점 확인 · 기존 단계·수량 설정 유지')
 return ui

def remote_purchase(adapter,context,inputs):
 from project_adapter.town_services import TownServices,_close_potion_screen,POTION_NAMES
 from owner_skill_goal import Pending
 from owner_remote_potion_limit_candidate import cached_full,observed_full,remember_full
 tier=str(adapter.values.get('common.potion_and_favorite.potion_tier','1단물약'))
 if tier not in ('1단물약','2단물약','3단물약'):raise Pending('물약 단계 설정 확인 필요')
 context.checkpoint()
 if cached_full(adapter,tier):
  LOG.info('원격 물약 구매 생략 · %s 직전 확인 한도 대기 · 구매 없음',tier);return True
 try:ui=open_remote(adapter,context,inputs)
 except RemoteShopDeferred as exc:
  LOG.warning('원격 물약 작업만 보류 · %s',exc);return False
 names=list(POTION_NAMES)+['버튼_물약상인_2단물약','버튼_물약상인_3단물약']
 service=TownServices(adapter,context,inputs,list(dict.fromkeys(names)))
 try:
  if not remote_shop_screen(service.capture()):raise Pending('원격 잡화상점 전경 목록 화면 변경')
  limit=observed_full(ui,tier)
  if limit is not None:
   context.checkpoint();remember_full(adapter,tier)
   LOG.info('원격 물약 한도 확인 · %s %d/%d · 구매 없음',tier,limit,limit);return True
  if service.button('버튼_물약상인_'+tier,wait_before_click=.3,required=False) is False:
   LOG.info('원격 물약 구매 보류 · %s 구매 가능 표시 없음',tier);return False
  if service.button('버튼_물약상인_MAX',wait_before_click=.3,required=False) is False:
   LOG.info('원격 물약 구매 보류 · 구매 가능 수량 확인 필요');return False
  service.button('버튼_물약상인_확인',wait_before_click=.3)
  context.wait(.4);service.button('버튼_물약상인_구매',wait_before_click=.3)
  context.wait(.5)
  LOG.info('원격 물약 구매 요청 처리 · %s · 완료 수량은 게임 표시 기준',tier)
  return True
 finally:_close_potion_screen(service)

def route_potion_purchase(ordinary,adapter,context,inputs):
 """Existing replenishment only; an instance never authorizes town travel."""
 if not paid(adapter.project.root):
  from owner_schedule_priority import LOCAL as priority
  if getattr(priority,'combat',None):
   LOG.info('특수 콘텐츠 물약 보충 보류 · 원격 상점 미사용 · 마을 이동 없음')
   return False
  # A full stack shows 구매 불가 (525/500 on 11-05). The trip cost 30 s on every start, so rest for an hour.
  import time
  if time.monotonic()-getattr(adapter,'_owner_potion_full_at',-1e30)<3600:
   LOG.info('물약 한도 확인 후 1시간 대기 · 상인 이동 없음');return True
  from project_adapter.town_services import TownServices
  from owner_remote_potion_limit_candidate import sold_out
  tier=str(adapter.values.get('common.potion_and_favorite.potion_tier','1단물약'))
  look=TownServices(adapter,context,inputs,[])
  class Full(logging.Handler):
   said=False;sold=False
   def emit(self,record):
    if '물약구매 불가' not in record.getMessage():return
    self.said=True
    # The shop is still open when the first of these lines is written.
    if not self.sold:
     try:self.sold=sold_out(look.capture(),tier)
     except (OSError,ValueError,RuntimeError):pass
  watch=Full();LOG.addHandler(watch)
  try:result=ordinary(adapter,context,inputs)
  finally:LOG.removeHandler(watch)
  if watch.said:adapter._owner_potion_full_at=time.monotonic()
  # 구매 불가 means the amount is used up. Reporting a failure made the falling-battle return skip its re-entry.
  if watch.sold:
   LOG.info('물약 구매 끝 · %s 구매 가능 수량 없음',tier);return True
  return result
 previous=getattr(LOCAL,'potion',None);LOCAL.potion=(adapter,context,inputs)
 try:return remote_purchase(adapter,context,inputs)
 finally:LOCAL.potion=previous

TOWN_WORDS=('market','shop','treasure')

def without_potion_town(native,adapter,context,inputs,*args,**kwargs):
 """The merchant is why the native start goes to town twice. A member buys from the
 inventory, so both trips only cost time (36s on the 23:21 real run). A job that may
 still expect the town gets the held first trip right before it runs."""
 if not paid(adapter.project.root):return native(adapter,context,inputs,*args,**kwargs)
 original=context.run_action;had='run_action' in vars(context);owner=threading.get_ident();first=True;held=None
 def action(key,operation,*a,**k):
  nonlocal first,held
  if threading.get_ident()!=owner:return original(key,operation,*a,**k)
  if first and key=='common.run_town_return':
   first=False;context.checkpoint();held=(operation,a,k)
   LOG.info('멤버십 · 물약 때문에 가던 마을귀환 생략');return True
  first=False
  if held and any(word in key for word in TOWN_WORDS):
   operation_,a_,k_=held;held=None;original('common.run_town_return',operation_,*a_,**k_)
  if key=='common.potion.purchase':
   return original(key,lambda:adapter.run_potion_purchase(context,inputs),*a,**k)
  return original(key,operation,*a,**k)
 context.run_action=action
 try:return native(adapter,context,inputs,*args,**kwargs)
 finally:
  if had:context.run_action=original
  else:del context.run_action

def install(gui):
 if getattr(gui,'_owner_membership',False):return
 from project_adapter._entry import Adapter
 from project_adapter import town_services,mission_quests
 ordinary=Adapter.run_potion_purchase
 @wraps(ordinary)
 def potion(adapter,context,inputs):
  return route_potion_purchase(ordinary,adapter,context,inputs)
 Adapter.run_potion_purchase=potion
 ordinary_features=Adapter._run_auto_features
 @wraps(ordinary_features)
 def features(adapter,context,inputs,*args,**kwargs):
  return without_potion_town(ordinary_features,adapter,context,inputs,*args,**kwargs)
 Adapter._run_auto_features=features
 ordinary_run=mission_quests.run_mission_quests
 @wraps(ordinary_run)
 def missions(adapter,context,inputs):
  previous=getattr(LOCAL,'missions',None);LOCAL.missions=(adapter,context,inputs)
  try:
   result=ordinary_run(adapter,context,inputs)
   from owner_mission_ui import MissionUI,fit_rows_left
   ui=MissionUI(adapter,context,inputs);complete=True;running=False
   try:
    for setting,weekly,label in (('auto_schedule.daily_quest.enabled',False,'일일'),('auto_schedule.weekly_quest.enabled',True,'주간')):
     if not adapter.values.get(setting):continue
     remaining=ui.remaining_quota(weekly)
     # 수락 5/5 only says no more can be accepted. Those are finished only if
     # the instant-complete allowance was what filled it; otherwise they are running.
     from owner_mission_ui import instant_left
     finished=remaining==0 and not weekly and instant_left(ui)==0
     if finished:
      LOG.info('%s 임무 수락 5/5 · 즉시 완료 0/5 · 전체 완료 확인',label)
      # Proved here, so the timetable must not treat it as unverified and reopen
      # the mission window on every start for the rest of the day.
      from owner_timetable import LOCAL as timetable
      if getattr(timetable,'job',None)=='daily_missions':
       from owner_outcome import DONE,Outcome,report
       report(adapter,'daily_missions',Outcome(DONE,'수락 5/5 · 즉시 완료 0/5 확인'))
     elif remaining==0:
      running=True;LOG.info('%s 임무 수락 5/5 · 진행 중 · 완료로 저장하지 않음',label)
     elif remaining is not None and fit_rows_left(ui.frame())==0:
      # Every row this character is strong enough for is taken; the rest stay locked until it grows.
      text='수락 %d/5 · 수락 가능 행 없음'%(5-remaining);LOG.info('%s 임무 %s',label,text)
      from owner_timetable import LOCAL as timetable
      key='weekly_missions' if weekly else 'daily_missions'
      if getattr(timetable,'job',None)==key:
       from owner_outcome import DONE,Outcome,report
       report(adapter,key,Outcome(DONE,text))
     else:
      complete=False;LOG.info('%s 임무 미완료 · 남은 수락 가능 횟수=%s/5 · 완료로 저장하지 않음',label,remaining if remaining is not None else '판독 대기')
   finally:ui.close_known()
   return result if complete else False
  finally:LOCAL.missions=previous
 import sys
 for name,module in tuple(sys.modules.items()):
  if name.startswith('project_adapter') and module:
   for key,value in tuple(vars(module).items()):
    if value is ordinary_run:setattr(module,key,missions)
 instant=mission_quests.MissionQuests.instant_daily
 @wraps(instant)
 def daily(self):
  owner=getattr(LOCAL,'missions',None)
  if owner is None or not paid(owner[0].project.root):
   LOG.info('일일 임무 · 멤버십 미선택 · 즉시 완료 사용 안 함');return False
  return instant(self)
 mission_quests.MissionQuests.instant_daily=daily
 find=mission_quests.MissionQuests.find
 @wraps(find)
 def remaining_only(self,name,frame,region=None):
  if name!=mission_quests.FULL:return find(self,name,frame,region=region)
  owner=getattr(LOCAL,'missions',None)
  if owner is None:return None
  from owner_mission_ui import MissionUI,remaining_on_screen
  from owner_skill_goal import Pending
  try:
   ui=MissionUI(*owner)
   if remaining_on_screen(ui)==0:return (344,451,(332,441,356,462))
   return None
  except Pending:return None
 mission_quests.MissionQuests.find=remaining_only
 LOG.addFilter(QuotaMessage())
 gui._owner_membership=True
