"""One input-owning quest loop with individual durable mission boundaries."""
from functools import wraps
import inspect,logging,threading,time,math
from owner_skill_goal import Pending
from owner_mission_policy import QuestBook,movement_distance
from owner_mission_ui import MissionUI,quest_screen
from owner_quest_emote_candidate import require_cleanup_closed,EmoteCleanupPending
from owner_emote_requirements import EmoteQuestMismatch
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
class QuestBoundary(BaseException):pass

def after_reward_idle(runner,adapter,context):
 """After reward + settled idle, return to mission list; do not assert clear."""
 seen=getattr(runner,'_owner_reward_seen_at',None)
 if seen is None:return False
 ui=getattr(adapter,'_owner_mission_ui',None)
 if ui is None or ui.context is not context:return False
 context.checkpoint()
 if time.monotonic()-seen>20:
  runner._owner_reward_seen_at=None
  return False
 first=getattr(runner,'_owner_reward_idle_since',None)
 if first is None:runner._owner_reward_idle_since=time.monotonic()
 # Let any next objective/cutscene appear before opening the mission list.
 if first is None or time.monotonic()-first<1.5:
  context.wait(.15);return True
 if not ui.normal() or ui.execution_dialogue_pair():
  context.wait(.15);return True
 context.wait(.12);context.checkpoint()
 if not ui.normal():return True
 runner._owner_reward_seen_at=None
 LOG.info('서사 보상 후 자동 진행 없음 · 임무 탭 맨 위 받은 임무 선택 · 완료 여부는 목록 확인')
 raise QuestBoundary()

def wait_selection(adapter,ui,context,error):
 """A visible-row handoff miss is not a death, completion or hunt request."""
 now=time.monotonic();since=getattr(adapter,'_owner_selection_wait_since',None)
 if since is None:adapter._owner_selection_wait_since=since=now
 if now-since>=30:raise RuntimeError('서사 목록 첫 임무 선택을 확인하지 못했습니다. 선택 진단 화면을 확인해 주세요.') from error
 message='서사 목록 첫 임무 재확인 · 진행·완료 기록 유지'
 if now-getattr(adapter,'_owner_selection_notice_at',-1e30)>=10:
  LOG.warning(message,extra={'gui_message':message,'state_transition':True});adapter._owner_selection_notice_at=now
 # Keep the current mission panel open. Do not reset the catalog, close and
 # reopen menus, increment the ordinary3-error counter, or enter hunting.
 context.wait(1)

def confirmed_progress(adapter,key):
 """Only independently verified progress ends a consecutive failure run."""
 adapter._owner_catalog_errors=0
 if getattr(LOCAL,'stalled',None)==key:LOCAL.stalled=None

def reselect_mismatched_emote(ui,error):
 """A wrong tracked quest needs selection repair, never Home or a send retry."""
 from owner_quest_emote_candidate import normalize_after_stop
 adapter,context=ui.adapter,ui.context
 context.checkpoint()
 normalize_after_stop(adapter,context,ui.inputs)
 if not ui.normal():raise EmoteCleanupPending('임무 불일치 후 일반 필드 확인 필요 · 추가 입력 없음')
 adapter._owner_restore_story_once=False
 adapter._owner_emote_requested=None
 count=getattr(adapter,'_owner_emote_binding_errors',0)+1
 adapter._owner_emote_binding_errors=count
 message='선택 임무와 게임 추적 불일치 · 감정 입력 없이 임무 탭 첫 항목 재선택'
 LOG.warning('%s · %s',message,error,extra={'gui_message':message,'state_transition':True})
 if count>=3:raise RuntimeError('임무 선택과 게임 추적이 3회 불일치했습니다. 감정 입력·홈 복귀 없이 중단합니다: '+str(error)) from error
 context.wait(.5)

def emote_failure_clock(ui,key,handled,since,now):
 """The server's 61-second wait is not 30 seconds of failed automation."""
 if handled or getattr(ui.adapter,'_owner_emote_requested',None)!=key:return None
 if now<getattr(ui,'_owner_emote_cooldown_until',0):return None
 return now if since is None else since

def native_emote_request(adapter,key):
 """A used request stays consumed; later goals need fresh recognition.
 Ending a request isn't proof of quest completion and never resets cooldown.
 """
 if getattr(adapter,'_owner_emote_request_consumed',None)==key:
  adapter._owner_emote_requested=None
  return False
 adapter._owner_emote_requested=key
 return True

def continue_progress(original,runner,*args,**kwargs):
 """A native progress observation isn't proof the story chapter ended."""
 active=getattr(LOCAL,'active',None)
 if active and getattr(LOCAL,'stalled',None)==active[2]:raise QuestBoundary()
 return original(runner,*args,**kwargs)

class StallLog(logging.Handler):
 """Associate only the native confirmed-stall event with this worker's quest."""
 def emit(self,record):
  active=getattr(LOCAL,'active',None)
  if active and '서브퀘 움직임 정체 3분 · 진행중2로 전환' in record.getMessage():
   LOCAL.stalled=active[2]

def defer_stalled(book,key):
 """Persist an independently diagnosed functional hold, preserving deaths."""
 row=book.item['quests'][key]
 book.defer(key,'condition',functional_hold=True,
            detail='180초 움직임 정체 · 자동 진행 기능 확인 필요 · 진단 화면 보존')
 LOG.warning('개별 임무 기능 보류 · %s · 사망 횟수 유지 · 다른 임무 우선',row['title'])

def release_functional_hold(book,key):
 """Explicit maintenance recovery after the handler is fixed; never automatic."""
 row=book.item['quests'].get(key)
 if not row or not row.get('block',{}).get('functional_hold'):return False
 row.pop('block');book.commit();return True

STORY_RECHECK_SECONDS=300
# Real minimap change at level 17: about 4 while standing with monsters around, 22 while walking.
IDLE_MINIMAP_CHANGE=10;IDLE_SECONDS=120;PREPARE_SECONDS=180

def pending_death_baselines(book):
 return [row for row in book.item.get('quests',{}).values() if row.get('block',{}).get('reason')=='death' and row['block'].get('baseline') is None and row.get('completed') is not True]

def establish_death_baselines(book,progress,character,after):
 """Use a fresh, same-character reading; never replace a known baseline."""
 pending=pending_death_baselines(book)
 if not pending:return False
 if progress.character!=character:raise Pending('사망 기록 캐릭터와 현재 캐릭터가 달라 재판독 보류')
 if type(progress.power) is not int or progress.power<=0 or progress.observed<after:return False
 for row in pending:
  row['block']['baseline']=progress.power
  row['block']['baseline_source']='first_fresh_read_after_failure'
 if pending:book.commit()
 return bool(pending)

def death_retry_crossed(entries,previous,current):
 if type(previous) is not int or type(current) is not int or current<=previous:return False
 for row in entries.values():
  block=row.get('block',{});base=block.get('baseline')
  if row.get('completed') or row.get('legacy_step') or row.get('identity_alias_of'):continue
  if block.get('reason')=='death' and type(base) is int and base>0 and previous<math.ceil(base*1.15)<=current:return True
 return False

def defer_full_queue(book,power):
 """Proved full counter, no known actionable roots: preserve every quest."""
 batch=book.item.get('batch',{})
 if batch.get('actual_accepted')!=20:return False
 known=list(dict.fromkeys(k for k in batch.get('keys',[]) if k in book.item.get('quests',{})))
 if any(book.eligible(k,power) for k in known):return False
 book.item['story_full_hunt']={'at':time.time(),'status':'waiting','accepted_counter':20,
  'known_roots':len(known),'full_catalog_proved':False,'recheck_seconds':STORY_RECHECK_SECONDS,
  'reason':'수락 20/20 · 현재 확인된 실행 대상 없음 · 임무 유지하며 사냥 후 재확인'}
 book.commit()
 LOG.warning('서사 수락 20/20 · 현재 확인된 실행 대상 없음 · 전체 완료 미확인 · 임무 유지하고 사냥 후 재확인')
 return True

def hunt_started(result):
 return result is True or result in ('HUNTING_RESUMED','HUNTING_STARTED')

def restart_idle_quest(ui,idle):
 """Auto-move can drop after a boss fight, and the native runner then only clicks empty ground.
 A minimap unchanged for two minutes on the bare field presses the quest's own auto-progress again.
 Observed only on a main quest. The same applies to story quests, since the risk does not depend on mode."""
 import numpy as np
 frame=ui.frame()
 if getattr(frame,'shape',None)!=(479,897,3):return False
 # A guide can open a known full-screen menu mid-quest, like the treatment screen. Nothing moves until it closes.
 from owner_start_menu import kind as menu_kind,normalize as leave_menu
 if menu_kind(frame) in ('몽련 치료','지도','성장','가호','영기 수련','문파') and not ui.opened:
  ui.context.wait(.12)
  if menu_kind(ui.frame()):
   leave_menu(ui.service);idle.update(crop=None,at=time.monotonic());return True
 now=time.monotonic();crop=frame[18:100,12:95].mean(axis=2)
 if idle.get('crop') is None or float(np.abs(crop-idle['crop']).mean())>IDLE_MINIMAP_CHANGE:
  idle.update(crop=crop,at=now);return False
 if now-idle['at']<IDLE_SECONDS or not ui.normal():return False
 LOG.info('임무 자리 정체 %d초 · 자동 진행 다시 누름 · %s',now-idle['at'],ui.adapter.mode)
 quest_range(ui.adapter,ui.context,ui.inputs)
 ui.open(ui.adapter.mode);ui.start_selected();idle.update(crop=None,at=now)
 if getattr(ui.frame(),'hi',None) is not None:
  # At 1366 the re-press alone left the character standing; the quest's title in the tracker walked it on (pc1 13:40,
  # pc2 lv9). Pressed after the re-press, on the row of this mode's quest.
  from owner_emote_real import tracker_title,click
  # Only this quest's own row: another title there would walk off to another quest, past its purchase or emote
  # handling (pc2 17:07, 메마른 늪 walked to while 도술 구매 was selected).
  head=tracker_title(ui.frame(),ui.adapter.mode,getattr(ui.adapter,'_owner_active_title',None))
  if head:
   click(ui,(round(head['rx']),round(head['ry'])),1.)
   LOG.info('임무 자리 정체 · 추적창 제목 누름 · %s',head['word'])
 return True

def quest_range(adapter,context,inputs):
 """A quest walks to its monsters: 제자리 off and range 30m, as for a boss (user's rule). The quest entry sets it once,
 but a failed panel read there, or a hunt between quests (its sleep entry puts hunting's ON 5m back), left the
 character fixed at 5m: pc2 11-06, 0/10 for 7 minutes beside the wrong monster. Only when no record says it is loose."""
 from owner_boss_range import pending,loosen
 if pending(adapter.project.root) is not None:return False
 return loosen(adapter,context,inputs)

def finish_scene(adapter,context,inputs):
 """F1 during a quest scene or dimmed guide: no panel can open until it ends. Uses the start stage's handlers."""
 from project_adapter.main_quest import StateROIs
 from project_adapter.town_services import TownServices
 from project_adapter import market_inventory as native
 from owner_startup_stage import known_dialog,press_dialog,guide_visible,guide_handler
 mode=adapter.mode if adapter.mode in ('main_quest','sub_quest') else 'sub_quest'
 slots=StateROIs(adapter.project.root/'profiles/DKB',mode=mode)
 service=TownServices(adapter,context,inputs,native.INVENTORY_USE_NAMES)
 handled=False;end=time.monotonic()+30
 while time.monotonic()<end:
  context.checkpoint();first=service.capture();context.wait(.12);second=service.capture()
  key=known_dialog(slots,first,second)
  if key:press_dialog(adapter,context,inputs,service,slots,key,second)
  elif not guide_visible(adapter,first,second):break
  elif guide_handler(adapter,context,inputs,service).handle_tutorial_if_present() in ('FAILED','DETECTED_BUT_UNSAFE'):break
  handled=True;context.wait(.6)
 if handled:
  LOG.info('임무 시작 전 대화·안내 정리 · 전투력 다시 확인')
  context.wait(1.5)
 return handled

def prepare(adapter,context,inputs):
 from owner_progression import state
 from owner_quest_preflight import read_power
 from owner_task_flow import bootstrap,defer
 from project_adapter._entry import Adapter
 context.checkpoint();adapter.exit_sleep_mode(context,inputs)
 # A quest fight or scene can hold the screen for minutes, and three quick tries used to stop the run.
 attempt=0;deadline=time.monotonic()+PREPARE_SECONDS
 while True:
  context.checkpoint()
  observed_after=time.monotonic()
  if read_power(adapter,context,inputs):break
  fresh=state(adapter)
  if getattr(adapter,'_owner_requested_quest_mode',getattr(adapter,'mode',None))=='sub_quest' and fresh.character and fresh.level is not None and fresh.observed>=observed_after and fresh.power is None:
   LOG.warning('전투력 숫자 미확인 · 캐릭터 새 화면 확인 완료 · 현재 단계 적합 표시 임무만 진행 · 성장 재시도 보류')
   break
  finish_scene(adapter,context,inputs)
  if time.monotonic()>=deadline:raise Pending('임무 선택 전 캐릭터·전투력 두 화면 확인 필요 · %d초 재확인 실패'%PREPARE_SECONDS)
  attempt+=1
  if attempt==1 or attempt%10==0:LOG.info('임무 시작 전 화면 재확인 · %d회 · 잘못된 전투력으로 진행하지 않음',attempt)
  context.wait(3)
 if getattr(adapter,'_owner_initial_context',None) is not context:
  from owner_growth_recovery import recover
  recover(adapter,context,inputs)
  if adapter.values.get('main_quest.first_coupon.enabled'):
   from owner_startup_receipts import initial_coupons
   if initial_coupons(adapter,context,inputs):adapter.run_mail_rewards(context,inputs)
  bootstrap(adapter,context,inputs,inspect.unwrap(Adapter._run_auto_features))
  # Starter gear is required before the first quest; repeatable energy claims
  # belong to the existing inventory appointment, after quest AUTO is active.
  # Its durable incomplete/result-only retry is maintained by the timetable.
  if adapter.values.get('common.potion_and_favorite.enabled'):
   if adapter.run_potion_purchase(context,inputs) is False:LOG.info('시작 물약 보충 보류 · 기존 보유 물약으로 퀘스트 진행')
  defer(adapter,context,inputs);adapter._owner_initial_context=context
 return state(adapter)

NOTHING_SECONDS=1800


def recent_nothing(adapter,book,power,now=None):
 """Once per F1: the last full check found nothing runnable within NOTHING_SECONDS, at no more power than now has."""
 if getattr(adapter,'_owner_nothing_used',None)==getattr(adapter,'_owner_nothing_run',None):return False
 adapter._owner_nothing_used=getattr(adapter,'_owner_nothing_run',None)
 row=book.item.get('nothing_runnable') or {}
 at,then=row.get('at'),row.get('power')
 if type(at) not in (int,float) or type(then) is not int or type(power) is not int:return False
 return 0<=(now or time.time())-at<=NOTHING_SECONDS and power<=then


def safe_jobs(adapter,context,inputs,*,boundary=False):
 from owner_task_flow import dispatch,pending,defer,LOCAL as task
 if getattr(task,'servicing',False):return False
 from owner_timetable import idle_once
 from project_adapter._entry import Adapter
 if context.input_depth or getattr(inputs,'held',()):return False
 ui=getattr(adapter,'_owner_mission_ui',None)
 if ui is not None and ui.context is context and ui.inputs is inputs:
  if ui.execution_dialogue(ui.frame()):return False
  from owner_emote_dispatch import navigation_open
  if navigation_open(ui):return False
 before=getattr(adapter,'_owner_quest_boundary',False);adapter._owner_quest_boundary=boundary
 try:
  # Existing timed jobs and boss return wrappers retain the same worker.
  # Restore the individual quest by the journal after the temporary job.
  if idle_once(adapter,context,inputs):return True
  from owner_chore_transition import ancillary_field_ready
  if not ancillary_field_ready(adapter,context,inputs):return False
  ui=getattr(adapter,'_owner_mission_ui',None)
  if ui is not None and ui.context is context and ui.inputs is inputs:
   from owner_clan_field_help import attempt
   try:
    if attempt(ui):return True
   except Pending as exc:LOG.info('문파도움 화면 재확인 · %s',exc)
  if time.monotonic()-getattr(adapter,'_owner_last_service',-1e30)>=120 and not pending(adapter,context):defer(adapter,context,inputs)
  if pending(adapter,context):
   return dispatch(adapter,context,inspect.unwrap(Adapter._run_auto_features))
  return False
 except __import__('owner_chore_transition').ChoreYield as exc:
  if isinstance(exc,__import__('owner_chore_transition').ReadOnlyViewUnavailable):
   LOG.info('장비 현재값 판독 양보 · 화면 반환 후 재확인 · 완료·강화 입력 없음')
  else:LOG.info('서사 대화 먼저 처리 · 중단한 부수 작업은 대화 종료 후 이어서 확인')
  return False
 finally:adapter._owner_quest_boundary=before

def teleport(ui):
 from owner_task_flow import LOCAL as task
 if getattr(task,'servicing',False):return False
 from owner_movement import travel
 try:
  return travel(ui)
 except Pending:return False

def finish_dialogue_before_pick(ui,context,runner):
 """Handle a proven ongoing cinematic before attempting to open menus."""
 from owner_quest_clicks import step
 if not ui.execution_dialogue_pair():return False
 end=time.monotonic()+30;changes=[]
 while ui.execution_dialogue_pair():
  context.checkpoint()
  if time.monotonic()>=end:raise Pending('임무 대화가 끝나지 않아 메뉴 열기 보류')
  result=step(runner,context,changes)
  if result in ('DEATH_RECOVERED','QUEST_NEXT_MODE','STALLED_SKIPPED','QUEST_PROGRESS_REPEAT_SKIPPED','BOSS_TIMEOUT_RECOVERED'):
   raise Pending('대화 처리 중 임무 상태 변경 확인 필요: '+str(result))
  context.wait(.15)
 LOG.info('임무 대화 종료 확인 · 임무 메뉴 탐색 재개')
 return True

def run(adapter,context,inputs):
 from owner_quest_clicks import step,CHANGED
 from project_adapter.main_quest import BoundedMainQuestRunner,StateROIs,dependencies
 from owner_work_resume import ResumeWork
 from owner_quest_watchdog import Watch,QuestStalled,LOCAL as watchdog
 from owner_task_flow import LOCAL as task
 from owner_story_groups import StorySelectionPending
 requested=adapter._owner_requested_quest_mode
 adapter._owner_nothing_run=object()   # this start: the recent-nothing shortcut may answer once in it
 prepared_after=time.monotonic();progress=prepare(adapter,context,inputs);book=QuestBook(adapter.project.root,progress.character)
 character=progress.character
 establish_death_baselines(book,progress,character,prepared_after)
 baseline_retry_at=0.
 adapter._owner_mission_book=book;ui=MissionUI(adapter,context,inputs)
 adapter._owner_mission_ui=ui
 watch=Watch();watchdog.owner=(adapter,context,inputs,watch);watchdog.selected=None
 old_owner=getattr(task,'quest_owner',None)
 try:
  while True:
   context.checkpoint()
   try:
    require_cleanup_closed(ui)
    # A dimmed guide or scene blocks every menu, so clear it before opening the quest list.
    finish_scene(adapter,context,inputs)
    # The next main quest stays locked behind this guide, so check before picking one.
    from owner_guide_skill import run as run_guide_skill
    run_guide_skill(ui)
    from owner_quest_position_recovery import resume_pending
    if resume_pending(ui,book):adapter._owner_restore_story_once=True
    if pending_death_baselines(book) and time.monotonic()>=baseline_retry_at:
     baseline_retry_at=time.monotonic()+60;fresh_after=time.monotonic()
     from owner_quest_preflight import read_power
     if read_power(adapter,context,inputs):establish_death_baselines(book,progress,character,fresh_after)
    if ui.execution_dialogue_pair():
     profile,deps=dependencies(adapter,context,inputs)
     finish_dialogue_before_pick(ui,context,BoundedMainQuestRunner(StateROIs(profile,mode=requested),**deps))
    previous_active=book.item.get('active')
    restored=(getattr(adapter,'_owner_restore_story_once',False) and previous_active
              and book.eligible(previous_active,progress.power) and ui.normal())
    if restored:
     key=previous_active;adapter._owner_restore_story_once=False
     LOG.info('임시 콘텐츠 복귀 · 현재 필드의 진행 임무 이어가기 · 목록 재탐색 없음')
    elif recent_nothing(adapter,book,progress.power):
     # A full check just found nothing to run, at this power: the lists are not read again on F1 (user 11-06: 3 min of
     # list reading before every hunt). The hunt's own rechecks (power growth, the story timer) are unchanged.
     key=None
     LOG.info('최근 임무 확인에서 진행 가능 임무 없음 · 같은 전투력 · 목록 재확인 없이 사냥')
    else:key=ui.pick(book,requested,progress.power)
    if key is not None and book.item.get('story_full_hunt',{}).get('status')=='waiting':
     book.item['story_full_hunt'].update(status='resumed',resumed_at=time.time());book.commit()
    boundary=not previous_active or book.item['quests'].get(previous_active,{}).get('completed') is True
    skill_ready=getattr(adapter,'_owner_skill_purchase_ready',False)
    from owner_skill_goal import runtime_ledger
    skill_stage=runtime_ledger(adapter,character).item.get('stage','story')
    if boundary and (skill_ready or (skill_stage!='story' and time.monotonic()-getattr(adapter,'_owner_skill_boundary_checked',-1e30)>=300)):
     adapter._owner_skill_boundary_checked=time.monotonic()
     ui.close_known();adapter._owner_quest_boundary=True
     try:
      from owner_skill_goal import execute
      execute(adapter,context,inputs,force=skill_ready)
     finally:adapter._owner_quest_boundary=False;adapter._owner_skill_purchase_ready=False
     # Even a read-only final-story check changes the selected UI row. Pick
     # the saved current quest afresh instead of sending AUTO to the old row.
     continue
    if key is None:
     full_deferred=defer_full_queue(book,progress.power)
     if not full_deferred and book.refill_finished_batch(progress.power):continue
     # A partial/20-cap scan does not prove every suitable story was cleared.
     if not full_deferred and book.item['batch'].get('scan_complete') is not True:
      book.item['story_group_fill_pending']=True;book.commit()
      raise Pending('서사 전체 목록 확인 전에는 사냥 전환하지 않음')
     # Route only with a fresh, verified power. Unknown power is never zero.
     ui.close_known()
     from owner_quest_preflight import read_power
     fresh_after=time.monotonic()
     if not read_power(adapter,context,inputs) or type(progress.power) is not int:
      raise Pending('사냥터 선택 전 현재 전투력 확인 필요')
     establish_death_baselines(book,progress,character,fresh_after)
     from owner_hunt_rules_candidate import ConfiguredHuntRules
     from owner_hunt_route_candidate import hunt_scope
     from owner_hunt import run as guide_hunt
     from project_adapter import favorite_hunt
     configured=ConfiguredHuntRules(adapter.project.root);rules=configured.destinations()
     adapter.mode='auto_mode';progress.begin_work('auto_mode')
     book.item['work']='auto_mode';book.commit()
     LOG.info('현재 가능한 임무 없음 · 전투력 기준 사냥터 선택')
     book.item['nothing_runnable']={'at':time.time(),'power':progress.power};book.commit()
     last_power=progress.power
     next_full_recheck=time.monotonic()+STORY_RECHECK_SECONDS if full_deferred else None
     # Existing native idle wait preserves reservations, periodic chores and
     # cancellation. Growth retry is checked after its normal return.
     from project_adapter.reservations import wait_reservations
     def periodic(*args,**kwargs):
      nonlocal last_power
      configured.assert_identity()
      safe_jobs(adapter,context,inputs)
      if time.monotonic()-progress.observed>=300:
       from owner_quest_preflight import read_power
       fresh_after=time.monotonic()
       if read_power(adapter,context,inputs) and type(progress.power) is int:
        establish_death_baselines(book,progress,character,fresh_after)
        from owner_story_threshold_candidate import needs_recheck
        if death_retry_crossed(book.item['quests'],last_power,progress.power) or needs_recheck(book.item['quests'],last_power,progress.power,book.item['batch'].get('scan_complete') is True):
         last_power=progress.power;raise ResumeWork(requested)
        from owner_growth_policy_candidate import choose_hunt_rule
        old_rule=choose_hunt_rule(last_power,rules);new_rule=choose_hunt_rule(progress.power,rules)
        if old_rule!=new_rule and not hunt_started(adapter.run_favorite_hunt(context,inputs)):raise Pending('전투력 변경 후 사냥터 이동 확인 필요')
        last_power=progress.power
      # A full incomplete catalog is checked periodically even without power
      # growth: quest prerequisites or external game state may have changed.
      if next_full_recheck is not None and time.monotonic()>=next_full_recheck:
       LOG.info('서사 수락 대기 재확인 · 사냥을 잠시 넘기고 임무 목록 확인')
       raise ResumeWork(requested)
      return True
     with hunt_scope(adapter,progress,rules,guide_hunt,favorite_hunt,guard=configured.assert_identity):
      if not hunt_started(adapter.run_favorite_hunt(context,inputs)):raise Pending('임무 우회 후 사냥 상태 확인 필요')
      wait_reservations(adapter,context,periodic=periodic,inputs=inputs)
     from owner_quest_preflight import read_power
     read_power(adapter,context,inputs);adapter.mode=requested;continue
    row=book.item['quests'][key];adapter.mode=row['mode'];progress.begin_work(adapter.mode)
    LOG.info('임무 탭 선택 · %s · %s · 전투력=%s',adapter.mode,row['title'],progress.power)
    adapter._owner_active_title=row['title']
    from owner_quest_purchase import execute as quest_purchase
    if quest_purchase(ui,book,key):continue
    if not restored:ui.start_selected()
    adapter._owner_selection_wait_since=None
    LOCAL.active=(adapter,context,key,time.monotonic()+6)
    profile,deps=dependencies(adapter,context,inputs)
    runner=BoundedMainQuestRunner(StateROIs(profile,mode=adapter.mode),**deps)
    from project_adapter.reservations import QuestBossReservation
    boss_reservation=QuestBossReservation(adapter,runner)
    started=time.monotonic();next_teleport=started+1;next_emote=started+1;next_guide=started+5;idle_quest={};scene_changes=[];emote_failed_since=None
    while True:
     context.checkpoint()
     if time.monotonic()>=next_guide:
      next_guide=time.monotonic()+15
      from owner_guide_skill import run as run_guide_skill
      if run_guide_skill(ui) or restart_idle_quest(ui,idle_quest):
       runner=BoundedMainQuestRunner(StateROIs(profile,mode=adapter.mode),**deps)
       boss_reservation=QuestBossReservation(adapter,runner);scene_changes=[]
       LOCAL.active=(adapter,context,key,time.monotonic()+6)
       continue
     if time.monotonic()>=next_emote:
      next_emote=time.monotonic()+(.3 if getattr(adapter,'_owner_emote_requested',None)==key else 2)
      from owner_quest_emote_candidate import run as run_observed_emote
      try:
       handled=run_observed_emote(ui,book,key)
       if handled:adapter._owner_emote_binding_errors=0
       tick=time.monotonic()
       emote_failed_since=emote_failure_clock(ui,key,handled,emote_failed_since,tick)
       if emote_failed_since is not None and tick-emote_failed_since>=30:raise Pending('감정 임무 자동 진행 응답 30초 없음')
      except EmoteQuestMismatch:
       raise
      except Pending as exc:
       require_cleanup_closed(ui)
       if isinstance(exc,EmoteCleanupPending):raise
       # A transient unopened/moving menu is not an unfixable quest hold.
       # Retain the same active runner so native stationary evidence can
       # trigger Home recovery instead of immediately abandoning the quest.
       if emote_failed_since is None:emote_failed_since=time.monotonic()
       next_emote=time.monotonic()+10
       LOG.warning('임무 감정표현 화면 재확인 · 같은 임무 유지 · %s',exc)
       if time.monotonic()-emote_failed_since>=30:
        from owner_quest_emote_candidate import normalize_after_stop
        from owner_quest_position_recovery import recover as recover_position
        try:
         normalize_after_stop(adapter,context,inputs)
         recovered=recover_position(ui,book,key,'서사 감정표현 진행 정체 30초')
        except Pending as recovery_exc:
         LOG.warning('서사 자리 복구 보류 · %s',recovery_exc)
         book.defer(key,'condition',functional_hold=True,detail='자리 정체 복구 확인 필요 · '+str(recovery_exc));break
        if recovered=='waiting_emote':
         next_emote=time.monotonic()+1;context.wait(1);continue
        if recovered is True:
         profile,deps=dependencies(adapter,context,inputs)
         runner=BoundedMainQuestRunner(StateROIs(profile,mode=adapter.mode),**deps)
         boss_reservation=QuestBossReservation(adapter,runner)
         scene_changes=[];emote_failed_since=None;next_emote=time.monotonic()+1
         LOCAL.active=(adapter,context,key,time.monotonic()+6)
         continue
     require_cleanup_closed(ui)
     # At 1366 the native death picture does not match; the death screen's own words count instead (owner_death_real).
     from owner_death_real import recover as real_death
     died=real_death(ui)
     try:result='DEATH_RECOVERED' if died else step(runner,context,scene_changes)
     except QuestBoundary:
      position_reason=getattr(runner,'_owner_position_reset_reason',None)
      if not position_reason and getattr(LOCAL,'stalled',None)==key:position_reason='서브퀘 움직임 정체 3분 · 진행중2로 전환'
      if position_reason:
       from owner_quest_position_recovery import recover as recover_position
       try:
        recovered=recover_position(ui,book,key,position_reason)
       except Pending as exc:
        LOG.warning('서사 자리 복구 보류 · %s',exc)
        book.defer(key,'condition',functional_hold=True,detail='자리 정체 복구 확인 필요 · '+str(exc));break
       if recovered=='waiting_emote':
        context.wait(1);continue
       if recovered is True:
        LOCAL.stalled=None
        profile,deps=dependencies(adapter,context,inputs)
        runner=BoundedMainQuestRunner(StateROIs(profile,mode=adapter.mode),**deps)
        boss_reservation=QuestBossReservation(adapter,runner)
        next_emote=time.monotonic()+1;next_teleport=time.monotonic()+1;scene_changes=[]
        LOCAL.active=(adapter,context,key,time.monotonic()+6)
        continue
      if getattr(LOCAL,'stalled',None)==key:
       # The native 180-second stationary evidence triggered this boundary;
       # do not count it as a death, completion, or game power restriction.
       defer_stalled(book,key)
      LOCAL.stalled=None
      break
     intermediate=getattr(runner,'_owner_intermediate_quest_return',False)
     runner._owner_intermediate_quest_return=False
     if intermediate and result=='QUEST_NEXT_MODE':
      context.wait(.1);continue
     if result is CHANGED:continue
     boss_reservation.check()
     if result=='DEATH_RECOVERED':
      # Record the second death before any additional UI interaction; the
      # old power may predate a long quest and is not a valid failure baseline.
      held=book.death(key,None)
      LOG.warning('개별 임무 사망 · %s · %d회 · %s',row['title'],row['deaths'],'전투력 15% 성장까지 보류' if held else '같은 임무 재시도')
      from owner_job_timing import after_death
      after_death(adapter)
      break
     if result in ('QUEST_NEXT_MODE','STALLED_SKIPPED','QUEST_PROGRESS_REPEAT_SKIPPED','BOSS_TIMEOUT_RECOVERED'):
      if result=='STALLED_SKIPPED' or getattr(LOCAL,'stalled',None)==key:
       defer_stalled(book,key);LOCAL.stalled=None
      LOG.warning('임무 실행 경계 · %s · 결과=%s · 사망으로 집계하지 않음',row['title'],result);break
     selected=getattr(task,'quest_state',None)
     if selected and time.monotonic()-selected[2]<2:
      if selected[1]=='quest_reward':runner._owner_reward_seen_at=time.monotonic()
      elif selected[1] in ('auto_move','quest_active'):
       runner._owner_reward_seen_at=None;runner._owner_reward_idle_since=None
     moving=bool(selected and selected[1]=='auto_move' and time.monotonic()-selected[2]<5)
     if time.monotonic()>=next_teleport and not context.input_depth and not getattr(inputs,'held',()):
      used=teleport(ui);next_teleport=time.monotonic()+(10 if used else 1)
     if moving:
      # A reward/equipment chore during auto-walk does not complete this
      # mission. Keep its runner so arrival/dialogue can finish; actual
      # activity handoffs still unwind through ResumeWork/QuestBoundary.
      safe_jobs(adapter,context,inputs)
     context.wait(.1)
    LOCAL.active=None
    if not ui.normal():
     # A cutscene/dialog/boss is still owned by the native runner; never open
     # another mission menu until the native handler reaches a field state.
     end=time.monotonic()+30
     while not ui.normal() and time.monotonic()<end:
      context.checkpoint();step(runner,context,scene_changes);context.wait(.2)
     if not ui.normal():raise Pending('임무 경계 후 일반 필드 확인 필요')
    from owner_job_timing import boundary as quest_boundary,arrow_check
    with quest_boundary():
     from owner_hunt_memory import signals
     signals(adapter,context,inputs)
     arrow_check(adapter,context,inputs)
     safe_jobs(adapter,context,inputs,boundary=False)
   except ResumeWork:
    LOCAL.active=None
    adapter._owner_restore_story_once=True
    # Journal active ID survives boss/service unwind; recovered main/skill
    # conditions cannot replace the current other quest.
    LOG.info('임시 콘텐츠 복귀 · 저장한 개별 임무 재확인')
   except QuestStalled:
    stalled=getattr(LOCAL,'active',None)
    if stalled and stalled[0] is adapter and stalled[1] is context and stalled[2] in book.item['quests']:
     try:
      from owner_quest_position_recovery import recover as recover_position
      recovered=recover_position(ui,book,stalled[2],'서사 진행 정체 180초')
      if recovered=='waiting_emote':
       adapter._owner_restore_story_once=True;context.wait(1);continue
      if recovered is True:adapter._owner_restore_story_once=True
      else:defer_stalled(book,stalled[2])
     except Pending as exc:
      LOG.warning('서사 자리 복구 보류 · %s',exc)
      book.defer(stalled[2],'condition',functional_hold=True,detail='자리 정체 복구 확인 필요 · '+str(exc))
    LOCAL.active=None
    if not watch.allow_recovery(time.monotonic()):raise Pending('임무 정체 복구 15분 내 2회 반복 · 진단 확인 필요')
   except EmoteQuestMismatch as exc:
    LOCAL.active=None
    reselect_mismatched_emote(ui,exc)
   except EmoteCleanupPending as exc:
    LOCAL.active=None
    raise RuntimeError('감정 입력 결과는 보존했습니다. 채팅 메뉴 정리 확인 전 자동 입력을 중단합니다: '+str(exc)) from exc
   except StorySelectionPending as exc:
    LOCAL.active=None
    wait_selection(adapter,ui,context,exc)
   except Pending as exc:
    LOCAL.active=None;LOG.warning('임무 판독 보류 · %s',exc)
    try:ui.close_known()
    except Pending:pass
    # Bounded functional retry; no death increment or false completion.
    failures=getattr(adapter,'_owner_catalog_errors',0)+1;adapter._owner_catalog_errors=failures
    if failures>=3:raise RuntimeError('임무 화면 확인이 반복 실패했습니다: '+str(exc)) from exc
    context.wait(3)
 finally:
  if getattr(adapter,'_owner_mission_ui',None) is ui:adapter._owner_mission_ui=None
  LOCAL.active=None;LOCAL.stalled=None;task.quest_owner=old_owner;watchdog.owner=None;watchdog.selected=None

def install(gui):
 if getattr(gui,'_owner_mission_catalog',False):return
 from owner_quest_clicks import install as install_click_retry
 install_click_retry()
 from project_adapter._entry import Adapter
 from project_adapter.main_quest import BoundedMainQuestRunner
 ordinary=Adapter.run
 @wraps(ordinary)
 def entered(adapter,context,inputs):
  if getattr(adapter,'_owner_catalog_context',None) is not context:
   adapter._owner_initial_mode=adapter.mode
   adapter._owner_catalog_enabled=adapter.mode in ('main_quest','sub_quest')
   adapter._owner_requested_quest_mode=adapter.mode if adapter._owner_catalog_enabled else None
   adapter._owner_catalog_context=context
   adapter._owner_catalog_errors=0
   adapter._owner_restore_story_once=False
   adapter._owner_selection_wait_since=None
   adapter._owner_emote_binding_errors=0
  stationary=adapter._owner_initial_mode=='auto_mode'
  prior_stationary=getattr(adapter,'_owner_stationary_mode',False)
  prior_hunt=getattr(adapter,'run_favorite_hunt');had_hunt='run_favorite_hunt' in vars(adapter)
  if stationary:
   from owner_hunt_rules_candidate import ConfiguredHuntRules
   from owner_hunt_route_candidate import route_hunt
   from project_adapter import favorite_hunt
   configured=ConfiguredHuntRules(adapter.project.root);routes=configured.destinations()
   if not routes:raise RuntimeError('사냥터 탭에서 고정 또는 전투력별 사냥터를 켜 주세요')
   adapter._owner_stationary_mode=True
   def stationary_hunt(ctx,inp):
    if configured.destinations()!=routes:raise RuntimeError('서버·캐릭터 또는 사냥 위치가 변경되어 복귀를 보류합니다')
    from owner_progression import state
    from owner_quest_preflight import read_power
    from owner_hunt import run as guide_hunt
    current=state(adapter)
    if not current.character or type(current.power) is not int or time.monotonic()-current.observed>=300:
     if not read_power(adapter,ctx,inp) or type(current.power) is not int:raise RuntimeError('제자리 사냥 시작 전 캐릭터·전투력 확인 필요')
    return route_hunt(adapter,ctx,inp,current.power,routes,guide_hunt,favorite_hunt,hunt=prior_hunt)
   adapter.run_favorite_hunt=stationary_hunt
  previous=getattr(adapter,'get_due_schedules');had='get_due_schedules' in vars(adapter)
  def due():
   scheduler=getattr(adapter,'server_scheduler',None)
   return scheduler.get_due_schedules(adapter.values,'auto_mode') if scheduler else []
  adapter.get_due_schedules=due
  try:return ordinary(adapter,context,inputs)
  finally:
   adapter._owner_stationary_mode=prior_stationary
   if stationary:
    if had_hunt:adapter.run_favorite_hunt=prior_hunt
    else:del adapter.run_favorite_hunt
   if had:adapter.get_due_schedules=previous
   else:del adapter.get_due_schedules
 Adapter.run=entered
 progress=BoundedMainQuestRunner.handle_progress
 @wraps(progress)
 def boundary(runner,*args,**kwargs):
  return continue_progress(progress,runner,*args,**kwargs)
 BoundedMainQuestRunner.handle_progress=boundary
 idle=BoundedMainQuestRunner.handle_idle
 @wraps(idle)
 def reward_idle(runner,*args,**kwargs):
  active=getattr(LOCAL,'active',None)
  if active and active[0].mode=='sub_quest' and after_reward_idle(runner,active[0],active[1]):return None
  return idle(runner,*args,**kwargs)
 BoundedMainQuestRunner.handle_idle=reward_idle
 next_mode=BoundedMainQuestRunner.request_next_mode
 @wraps(next_mode)
 def next_boundary(runner,*args,**kwargs):
  if getattr(LOCAL,'active',None):
   reason=str(args[0] if args else kwargs.get('reason','미확인'))
   if reason=='채팅창 닫힘 확인':
    runner._owner_intermediate_quest_return=True
    return None
   from owner_quest_position_recovery import is_position_stall
   if is_position_stall(reason):runner._owner_position_reset_reason=reason
   LOG.info('기존 임무 처리의 다음 임무 요청 · %s · 완료는 임무 목록에서 별도 확인',reason)
   raise QuestBoundary()
  return next_mode(runner,*args,**kwargs)
 BoundedMainQuestRunner.request_next_mode=next_boundary
 native_chat=BoundedMainQuestRunner.handle_sub_chat
 @wraps(native_chat)
 def guarded_chat(runner,spec,match,frame):
  active=getattr(LOCAL,'active',None)
  if active:
   adapter,context,key,_=active;book=getattr(adapter,'_owner_mission_book',None)
   context.checkpoint()
   if not native_emote_request(adapter,key):return None
   if not getattr(adapter,'_owner_emote_native_chat_held',False):
    LOG.info('감정 임무 · 고정 화남 입력 대신 요구 항목·캐릭터별 재전송 제한 확인')
    adapter._owner_emote_native_chat_held=True
   return None
  return native_chat(runner,spec,match,frame)
 BoundedMainQuestRunner.handle_sub_chat=guarded_chat
 handler=StallLog();gui.logger.addHandler(handler)
 gui.root.bind('<Destroy>',lambda event:gui.logger.removeHandler(handler) if event.widget is gui.root else None,add='+')
 gui._owner_mission_catalog=True
 LOG.info('임무 중심 육성 준비 · 개별 임무 사망·선행·투력 기록 · 진행 중인 임무 우선 보존')
 LOG.info('개인용 감정표현 보완 적용 · 20261103 · 공통 조건·원본 카드·재전송 대기 분리')
