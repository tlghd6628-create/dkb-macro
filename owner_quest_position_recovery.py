"""Bounded same-quest re-entry after the native confirmed stationary event."""
import logging,time
from owner_skill_goal import Pending
from owner_quest_emote_candidate import paired,target_zone
LOG=logging.getLogger('project_gui.DKB')
WINDOW=900

def is_position_stall(reason):
 return (all(s in reason for s in ('중앙 노란 장판','제자리 유효 관측','30초'))
         or reason in ('서브퀘 움직임 정체 3분 · 진행중2로 전환','서사 진행 정체 180초','서사 감정표현 진행 정체 30초'))

def recover(ui,book,key,reason):
 from owner_schedule_priority import LOCAL as priority
 prior=getattr(priority,'feature',None);priority.feature='임무 자리 복구'
 try:return _recover(ui,book,key,reason)
 finally:priority.feature=prior

def _recover(ui,book,key,reason):
 """Reuse native home return and existing current-root selection; no scan.

 A durable intent bounds repeated failures and survives program restarts.
 This never marks a quest complete, never counts a death and never clears
 an unverified equipment or consumption receipt.
 """
 if not is_position_stall(reason):return False
 row=book.item.get('quests',{}).get(key)
 if not row or row.get('completed') or row.get('identity_alias_of') or row.get('mode')!='sub_quest' or not row.get('group'):return False
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 character=state(ui.adapter).character;scope=configured_identity(ui.adapter.project.root)
 def guard():
  ui.context.checkpoint()
  if not character or state(ui.adapter).character!=character or configured_identity(ui.adapter.project.root)!=scope:
   raise Pending('자리 복구 중 캐릭터·설정 변경')
  if book.item.get('active')!=key or book.item['quests'].get(key) is not row:
   raise Pending('자리 복구 중 진행 임무 변경')
  if ui.context.input_depth or getattr(ui.inputs,'held',()):raise Pending('자리 복구 전 입력 해제 확인 필요')
 guard()
 now=time.time();attempt=row.get('emote_attempt',{})
 # Stay put during a possible server-side emote cooldown. A return home
 # would neither complete this requirement nor remove that cooldown.
 at=attempt.get('at')
 from owner_emote_cooldown import Rate
 if Rate(ui.adapter.project.root,scope,character).remaining()>0 or (type(at) in (int,float) and 0<=now-at<61):
  LOG.info('감정표현 입력 결과 대기 · 홈 복귀 보류 · 재전송 제한 유지')
  return 'waiting_emote'
 prior=row.get('position_recovery',{})
 if prior.get('phase') in ('intent','at_town'):
  return _resume_at_town(ui,book,key,row,guard,character,scope,now)
 events=[a for a in book.item.get('position_recovery_events',[]) if type(a) in (int,float) and 0<=now-a<WINDOW]
 if prior.get('phase')=='restart_intent' or (type(prior.get('at')) in (int,float) and now-prior['at']<WINDOW) or len(events)>=2:
  raise Pending('같은 자리 복구 반복 한도 · 임무 미완료 보존 · 다른 임무 우선')
 if not ui.normal() or not paired(ui,ui.normal_frame):raise Pending('자리 복구 전 일반 필드 재확인 필요')
 if '중앙 노란 장판' in reason and not paired(ui,target_zone):raise Pending('자리 복구 전 노란 지점 재확인 필요')
 guard();row['position_recovery']={'phase':'intent','at':now,'reason':reason,'quest_completed':False,'character':character,'scope':scope}
 book.item['position_recovery_events']=events+[now];book.commit()
 LOG.warning('서사 자리 정체 복구 · %s · 기존 홈 귀환 후 같은 임무 재시작 · 전체 목록 탐색 없음',row['title'])
 ui.adapter.run_town_return(ui.context,ui.inputs)
 guard()
 return _resume_at_town(ui,book,key,row,guard,character,scope,now,new_home=True)

def _resume_at_town(ui,book,key,row,guard,character,scope,now,*,new_home=False):
 """Reconcile durable Home from fresh town proof; never replay Home."""
 receipt=row['position_recovery']
 if receipt.get('character',character)!=character or receipt.get('scope',scope)!=scope:
  raise Pending('자리 복구 기록 캐릭터·설정 변경 · 재입력 없음')
 last=receipt.get('root_checked_at',receipt.get('at'))
 if not new_home and (type(last) not in (int,float) or now-last<61):
  raise Pending('같은 임무 복구 재확인 61초 대기 · 홈 재입력 없음')
 from owner_town_return import town_pair
 guard()
 if not ui.normal() or not paired(ui,ui.normal_frame) or not town_pair(ui.adapter,ui.context,ui.inputs):
  raise Pending('자리 복구 후 홈 마을 도착 확인 필요 · 홈 재입력 없음')
 # Save town arrival BEFORE root lookup, not only after the AUTO request.
 receipt.update(phase='at_town',town_verified_at=time.time(),town_proof='paired_native_town_label',character=character,scope=scope)
 book.commit()
 window=receipt.get('root_window_at',now);count=receipt.get('root_attempts',0)
 if type(window) not in (int,float) or not 0<=now-window<WINDOW:window=now;count=0
 if type(count) is not int or count>=2:raise Pending('같은 임무 화면 재확인 한도 · 홈 재입력 없음')
 receipt.update(root_window_at=window,root_attempts=count+1,root_checked_at=now);book.commit()
 # The mission panel remembers its current view. Select only the exact
 # active root visible there; never sweep the catalog for a historic glyph.
 ui.open('sub_quest');guard()
 from owner_story_groups import Groups
 from owner_progression import state
 groups=Groups(ui,book,state(ui.adapter).power)
 # Only the stored root in the current viewport, on two agreeing frames.
 # Existing glyph/name matching is reused; no catalog/slot discovery.
 first=groups.locate(key);ui.context.wait(.12);guard();second=groups.locate(key)
 if not first or not second or abs(first['y']-second['y'])>=3 or first.get('open')!=second.get('open'):
  raise Pending('홈 복귀 후 같은 임무의 현재 표시 두 화면 확인 필요')
 if not groups.select(key):raise Pending('홈 복귀 후 같은 임무의 현재 단계 실행 조건 확인 필요')
 guard();receipt.update(phase='restart_intent',restart_requested_at=time.time());book.commit()
 ui.start_selected();guard()
 receipt.update(phase='restarted_unverified',restarted_at=time.time())
 book.commit()
 ui.adapter._owner_emote_requested=None
 LOG.info('홈 복귀 후 같은 서사 자동 진행 요청 · 실제 이동·완료는 별도 확인')
 return True

def resume_pending(ui,book):
 """At a worker boundary retry a proved town receipt, not a catalog scan."""
 active=book.item.get('active')
 if active and not book.item.get('quests',{}).get(active,{}).get('position_recovery'):return False
 now=time.time()
 for key,row in book.item.get('quests',{}).items():
  receipt=row.get('position_recovery',{});block=row.get('block',{})
  if active not in (None,key) or row.get('completed') or row.get('identity_alias_of'):continue
  if receipt.get('phase') not in ('intent','at_town') or not is_position_stall(receipt.get('reason','')):continue
  if block and not (block.get('functional_hold') and str(block.get('detail','')).startswith('자리 정체 복구 확인 필요')):continue
  last=receipt.get('root_checked_at',receipt.get('at'))
  if type(last) not in (int,float) or now-last<61:continue
  window=receipt.get('root_window_at',now);count=receipt.get('root_attempts',0)
  if type(window) in (int,float) and 0<=now-window<WINDOW and (type(count) is not int or count>=2):continue
  from owner_town_return import town_pair
  if not ui.normal() or not paired(ui,ui.normal_frame) or not town_pair(ui.adapter,ui.context,ui.inputs):return False
  prior_active=active;book.item['active']=key
  try:result=recover(ui,book,key,receipt['reason'])
  except Pending as exc:
   LOG.info('저장된 홈 복구 재확인 보류 · %s',exc)
   book.item['active']=prior_active;book.commit();return False
  if result is not True:
   book.item['active']=prior_active;book.commit();return False
  # Release only this exact recovery hold after same-root selection. Keep
  # an audit history, every completed/death/prerequisite receipt unchanged.
  if row.get('block') is block and block.get('functional_hold'):
   row.setdefault('position_recovery_hold_history',[]).append(dict(block));row.pop('block',None)
  book.item.update(active=key,work=row['mode']);book.commit();return True
 return False
