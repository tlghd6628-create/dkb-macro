"""Compatibility install name; guarded original album workflow, no new worker."""
from functools import wraps
from pathlib import Path
import hashlib,logging,sys,threading,time
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
FLAGS=('auto_rewards.album.enabled','custom.auto_rewards.album.enabled')
COMPLETE='버튼_전체매뉴_화첩_완성';CHECK='체크_전체매뉴_화첩'
class AlbumBoundary(BaseException):pass
class AlbumNothingLeft(BaseException):pass
LOOKS_AGAIN='다른 빨점 재확인';MOST_LOOKS=2;WHOLE_SCREEN=(0,0,897,479)

class NoDots(logging.Handler):
 """The original looks again for a dot it cannot place, and at 1366x768 did so for five minutes (17:27). A press or
 any other step logs something else in between, so looks in a row mean nothing is left to claim. When the real pixels
 can say so, the first look is enough; the count stays for screens they cannot speak for."""
 looks=0
 def __init__(self,screen_clear=None):
  super().__init__();self.screen_clear=screen_clear
 def emit(self,record):
  text=record.getMessage()
  if '화첩' not in text:return
  self.looks=self.looks+1 if LOOKS_AGAIN in text else 0
  if self.looks>=MOST_LOOKS or (self.looks and self.screen_clear is not None and self.screen_clear()):raise AlbumNothingLeft()

def screen_clear(service):
 """True only on the album screen, seen on real pixels, with no red dot anywhere on it. Anything else leaves it to the count."""
 from owner_reward_visual_guard import notice_dots
 try:
  frame=service.capture()
  if getattr(frame,'hi',None) is None or not service.detector.find(CHECK,frame,threshold=.95):return False
  return not notice_dots(frame,WHOLE_SCREEN)
 except Exception as exc:
  LOG.debug('album dot read: %s',exc);return False

def completion_hit(service,frame):
 if not service.detector.find(CHECK,frame,threshold=.95):return None
 return service.detector.find(COMPLETE,frame,threshold=.95)

def guarded_click(original,service,hit):
 scope=getattr(LOCAL,'scope',None)
 if not scope or service.adapter is not scope['adapter']:return original(service,hit)
 scope['service']=service
 service.check();a=service.capture();first=completion_hit(service,a)
 if not first or not (abs(hit[0]-first[0])<55 and abs(hit[1]-first[1])<20):return original(service,hit)
 service.context.wait(.12);service.check();b=service.capture();second=completion_hit(service,b)
 if first!=second:raise AlbumBoundary('완성 버튼 재확인 필요')
 if scope['mode']=='조각 등록만':raise AlbumBoundary('조각 등록만 · 완성 버튼에서 종료')
 import numpy as np
 if not np.array_equal(a[66:85,224:412],b[66:85,224:412]):raise AlbumBoundary('화첩 제목 재확인 필요')
 token=hashlib.sha256(b[66:85,224:412].tobytes()).hexdigest()
 from owner_timetable import read_required_if_present,save
 path=Path(service.adapter.project.root)/'settings/owner-album-inputs.json'
 data=read_required_if_present(path,{'version':1,'characters':{}})
 rows=data['characters'].setdefault(scope['identity'],{})
 if token in rows:raise AlbumBoundary('이 화첩의 이전 완성 입력 결과 확인 필요')
 service.context.checkpoint();service.check();fresh=service.capture()
 if completion_hit(service,fresh)!=second or not np.array_equal(b[66:85,224:412],fresh[66:85,224:412]):raise AlbumBoundary('완성 입력 직전 화면 변경')
 # Durable before input. Do not clear on disappearance alone; an uncertain
 # completion may not charge the same character/title a second time.
 rows[token]={'state':'sent_unconfirmed','at':time.time()};save(path,data)
 scope['sent']=True
 return original(service,second)

def guarded_button(original,service,name,*args,**kwargs):
 scope=getattr(LOCAL,'scope',None)
 if scope and service.adapter is scope['adapter'] and name==COMPLETE:
  scope['service']=service
  # Do not let the native convenience method bypass the same completion
  # boundary that applies to hit-based clicks.
  if scope['mode']=='조각 등록만':raise AlbumBoundary('조각 등록만 · 완성 버튼에서 종료')
  service.check();hit=completion_hit(service,service.capture())
  if not hit:raise AlbumBoundary('완성 버튼 재확인 필요')
  return service.click_hit(hit)
 return original(service,name,*args,**kwargs)

def install(gui):
 if getattr(gui,'_owner_album_disabled',False):return
 from project_adapter._entry import Adapter
 from project_adapter import achievement_rewards
 from project_adapter.town_services import TownServices
 original=achievement_rewards.run_album_rewards
 @wraps(original)
 def run(adapter,context,inputs):
  if adapter.values.get(FLAGS[0]) is not True:return True
  from owner_hunt_rules_candidate import configured_identity
  from owner_gear_settings_candidate import Store
  from owner_character_binding import mismatch
  from owner_progression import state
  from owner_outcome import report,Outcome,WAITING,SENT_UNCONFIRMED
  # First in the day's timetable, nobody has read the character yet, and the album waited 20 minutes for that (19:42).
  if not state(adapter).character:
   from owner_quest_preflight import read_power
   read_power(adapter,context,inputs)
  if mismatch(adapter) or not state(adapter).character:
   report(adapter,'album',Outcome(WAITING,'캐릭터 확인 필요'));return True
  identity=configured_identity(adapter.project.root)
  mode=Store(adapter.project.root,identity).read()['album']['mode']
  previous=getattr(LOCAL,'scope',None)
  scope={'adapter':adapter,'identity':identity,'mode':mode,'sent':False};LOCAL.scope=scope
  watch=NoDots(lambda:screen_clear(TownServices(adapter,context,inputs,[CHECK])));LOG.addHandler(watch)
  try:
   try:
    result=original(adapter,context,inputs)
    if scope['sent']:report(adapter,'album',Outcome(SENT_UNCONFIRMED,'완성 입력 후 결과 별도 확인',unverified=True))
    return result
   except AlbumNothingLeft:
    LOG.removeHandler(watch)
    LOG.info('화첩 보상 완료 · 빨점 없음 · 추가 탐색 종료')
    # The album is finished, so its completion guard has no say over leaving. This service does not know the album's images.
    LOCAL.scope=previous
    TownServices(adapter,context,inputs,['버튼_나가기']).button('버튼_나가기',wait_before_click=.12,required=False)
    return True
   except AlbumBoundary as exc:
    LOG.info('화첩 · %s',exc)
    report(adapter,'album',Outcome(SENT_UNCONFIRMED if scope['sent'] else WAITING,str(exc),unverified=True))
    service=scope.get('service')
    if service is not None:
     context.checkpoint();service.check()
     if service.detector.find(CHECK,service.capture(),threshold=.95):
      service.button('버튼_나가기',wait_before_click=.12,required=False)
    return True
  finally:
   LOG.removeHandler(watch);LOCAL.scope=previous
 ordinary_click=TownServices.click_hit
 @wraps(ordinary_click)
 def click(service,hit):return guarded_click(ordinary_click,service,hit)
 TownServices.click_hit=click
 ordinary_button=TownServices.button
 @wraps(ordinary_button)
 def button(service,name,*args,**kwargs):return guarded_button(ordinary_button,service,name,*args,**kwargs)
 TownServices.button=button
 for name,module in tuple(sys.modules.items()):
  if name.startswith('project_adapter') and module is not None:
   for attr,value in tuple(vars(module).items()):
    if value is original:setattr(module,attr,run)
 achievement_rewards.run_album_rewards=run;Adapter.run_album_rewards=run
 gui._owner_album_disabled=True
