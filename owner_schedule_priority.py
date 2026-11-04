"""Defer ancillary feature starts around enabled combat reservations.

One owning worker remains. Never interrupts an in-flight click or battle.
"""
from datetime import datetime,timedelta,timezone,time
from contextlib import contextmanager
from functools import lru_cache,wraps
from pathlib import Path
import importlib,json,logging,sys,threading
KST=timezone(timedelta(hours=9));LOCAL=threading.local()
LOG=logging.getLogger('project_gui.DKB')
LEAD_SECONDS=15*60
ISOLATED_ACTIVITIES=frozenset(('비경탐험','비경탐험(일일-24시간)','전래동화 비경'))

class HeldEnd(logging.Filter):
    """The native caller logs completion for any job that returns. A held job did not run."""
    def filter(self,record):
        text=record.getMessage()
        if text.startswith('자동 기능 보류 · '):LOCAL.held=True
        elif text.startswith('자동 기능 시작 · '):LOCAL.held=False
        elif text.startswith('자동 기능 완료 · ') and getattr(LOCAL,'held',False):
            LOCAL.held=False
            # One native step can cover several jobs (일일·주간), so only the held part is named.
            record.msg='자동 기능 종료 · '+text[len('자동 기능 완료 · '):]+' · 위 보류 항목은 실행 안 함';record.args=()
        return True

def wake_before_recovery(ordinary):
    """Sleep hides every button the screen recovery looks for, so it can only fail there.

    20:36 real run: spirit training ended on the sleep screen, recovery pressed its
    limit and waited for sixteen minutes, past the boss. Only an active recovery wakes:
    a passive check must not disturb a character sleeping on purpose.
    """
    @wraps(ordinary)
    def recover(stall,*,verify_only=False,wait_on_exhaustion=True,passive_wait=False):
        if not verify_only and not passive_wait and not getattr(LOCAL,'waking',False):
            LOCAL.waking=True
            try:
                stall.adapter.exit_sleep_mode(stall.context,stall.inputs)
            except Exception as exc:
                LOG.warning('복구 전 절전 해제 실패 · %s',str(exc)[:120])
            finally:LOCAL.waking=False
        return ordinary(stall,verify_only=verify_only,wait_on_exhaustion=wait_on_exhaustion,passive_wait=passive_wait)
    recover._owner_wakes=True
    return recover

@contextmanager
def activity_scope(label):
    """Same-worker instance ownership; ordinary field movement is unrelated."""
    previous=getattr(LOCAL,'combat',None);LOCAL.combat=label
    try:yield
    finally:LOCAL.combat=previous

@lru_cache(maxsize=4)
def _spec(path,mtime):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig')).get('schedules',[])
    except (OSError,ValueError):return []

def reservation_hold(root,values,when=None):
    when=when or datetime.now(KST)
    path=Path(root)/'profiles/DKB/config/server-schedule.json'
    try:specs=_spec(str(path),path.stat().st_mtime_ns)
    except OSError:specs=[]
    for spec in specs:
        if spec.get('id') not in ('auto_schedule.field_boss','auto_schedule.falling_battle','auto_schedule.artifact_charm'):continue
        if not values.get(spec.get('setting'),False):continue
        clock=spec.get('window_start') or spec.get('time')
        # Falling's native config omits its clock. The game calendar says22:00;
        # this is only an ancillary hold, NOT a new automatic entry time.
        if not clock and spec['id']=='auto_schedule.falling_battle':clock='22:00'
        if not clock:continue
        for offset in (-1,0,1):
            day=when.date()+timedelta(days=offset)
            if day.weekday() not in spec.get('weekdays',range(7)):continue
            start=datetime.combine(day,time.fromisoformat(clock),tzinfo=KST)
            end=datetime.combine(day,time.fromisoformat(spec['window_end']),tzinfo=KST) if spec.get('window_end') else start+timedelta(minutes=10)
            if end<start:end+=timedelta(days=1)
            if start-timedelta(seconds=LEAD_SECONDS)<=when<=end:
                return '%s 예약 보호 (%s)'%(spec.get('label','보스'),start.strftime('%H:%M'))
    return None

def hold_reason(adapter,when=None,*,label=None):
    active=getattr(LOCAL,'combat',None)
    if active:
        from owner_reward_context import LABELS,DUNGEONS
        if not (active in DUNGEONS and label in LABELS):return active+' 진행 중'
    return reservation_hold(adapter.project.root,adapter.values,when)

def service_wrapper(original,label):
    @wraps(original)
    def run(*args,**kwargs):
        # The native folktale entry calls the exploration entry inside its own
        # scope. That is the same activity going on, not a new start to hold.
        if label in ISOLATED_ACTIVITIES and getattr(LOCAL,'combat',None) in ISOLATED_ACTIVITIES:
            return original(*args,**kwargs)
        if label=='비경탐험' and kwargs.get('variant')=='daily24h':
            return service_wrapper(original,'비경탐험(일일-24시간)')(*args,**kwargs)
        # A timed clan battle is not today's already-processed application job.
        if label=='문파 보스 신청' and kwargs.get('combat') is True:
            return combat_wrapper(original,'문파 전투')(*args,**kwargs)
        adapter=next((value for value in (*args,*kwargs.values()) if hasattr(value,'project') and hasattr(value,'values')),None)
        if adapter is None:
            from owner_rewards import LOCAL as reward
            adapter=getattr(reward,'adapter',None)
        if adapter is None:return original(*args,**kwargs)
        context=next((value for value in (*args,*kwargs.values()) if callable(getattr(value,'checkpoint',None))),None)
        if context is not None:context.checkpoint()
        reason=hold_reason(adapter,label=label)
        if not reason:
            from owner_reward_context import LABELS,admit
            if label in LABELS and context is not None:
                inputs=args[2] if len(args)>=3 else kwargs.get('inputs')
                if inputs is not None:
                    observation=admit(adapter,context,inputs)
                    if not observation['allowed']:reason=observation['reason']
        if not reason:
            from owner_timetable import LABEL_JOB,BY_KEY,busy_windows,fit,now
            key=LABEL_JOB.get(label)
            if key:
                at=now();safe=fit(at,BY_KEY[key].minutes,busy_windows(adapter.values,at,root=adapter.project.root))
                if safe>at:reason='보스 출발 시간 충돌 · '+safe.strftime('%H:%M')+' 이후'
        if reason:
            from owner_reward_context import LABELS
            if label in LABELS:adapter._owner_reward_cycle_hold=reason
            if label=='인벤토리 사용':adapter._owner_inventory_skip_generation=getattr(adapter,'_owner_inventory_skip_generation',0)+1
            LOG.info('자동 기능 보류 · %s · %s · 전투 종료 후 재확인',label,reason)
            return True
        from owner_timetable import scheduled_call
        previous=getattr(LOCAL,'feature',None);LOCAL.feature=label
        try:
            if label in ISOLATED_ACTIVITIES:
                with activity_scope(label):return scheduled_call(original,label,args,kwargs,adapter)
            return scheduled_call(original,label,args,kwargs,adapter)
        except RecursionError as exc:
            # 20:19 real run lost its mail step to this with no trace of where it looped.
            import traceback
            rows=traceback.extract_tb(exc.__traceback__)
            LOG.warning('재귀 초과 위치 · %s · %s',label,' > '.join('%s:%s'%(Path(row.filename).stem,row.lineno) for row in rows[-12:]))
            raise
        finally:LOCAL.feature=previous
    return run

def combat_wrapper(original,label):
    @wraps(original)
    def run(*args,**kwargs):
        previous=getattr(LOCAL,'combat',None);LOCAL.combat=label
        try:
            adapter=next((value for value in (*args,*kwargs.values()) if hasattr(value,'project') and hasattr(value,'values')),None)
            if adapter is not None:
                from owner_timetable import scheduled_call
                return scheduled_call(original,label,args,kwargs,adapter)
            return original(*args,**kwargs)
        finally:LOCAL.combat=previous
    return run

def install(gui):
    if getattr(gui,'_owner_schedule_priority',False):return
    service_targets={
        'guide_rewards':{'run_guide_rewards':'길라잡이'},
        'event_rewards':{'run_event_rewards':'이벤트'},
        'mail_rewards':{'run_mail_rewards':'우편'},
        'achievement_rewards':{'run_achievement_rewards':'업적','run_album_rewards':'화첩','run_blessing_rewards':'가호','run_energy_entry':'기운 발현','run_growth_entry':'성장 장비·가호'},
        'market_inventory':{'run_inventory_use':'인벤토리 사용','run_growth_equipment':'성장 장비·가호','run_equipment_disassembly':'장비 분해','run_market_inventory':'거래소'},
        'seal_release':{'run_seal_release':'단 봉인해제'},
        'treasure_entry':{'run_treasure_region_entry':'보물찾기'},
        'spirit_training':{'run_spirit_training':'영기 수련'},
        'clan_cooperative_training':{'run_clan_cooperative_training':'문파 협력수련'},
        'mission_quests':{'run_mission_quests':'일일·주간 임무'},
        'clan_boss_request':{'run_clan_boss_request':'문파 보스 신청'},
        'secret_exploration':{'run_secret_exploration':'비경탐험'},
        'secret_folktale':{'run_folktale_exploration':'전래동화 비경'},
    }
    combat_targets={
        'field_boss':{'run_field_boss_entry':'월드보스'},
        'boss_raid':{'run_boss_raid':'보스 레이드'},
        'falling_battle':{'run_falling_battle':'낙화의 전장'},
        'ascension_tower':{'run_ascension_tower':'승천의 탑'},
    }
    replacements=[]
    for targets,wrapper in ((service_targets,service_wrapper),(combat_targets,combat_wrapper)):
        for module,functions in targets.items():
            loaded=importlib.import_module('project_adapter.'+module)
            for name,label in functions.items():
                original=getattr(loaded,name,None)
                if original is not None:replacements.append((original,wrapper(original,label)))
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                replacement=next((new for old,new in replacements if value is old),None)
                if replacement is not None:setattr(module,key,replacement)
    # Some native reward helpers are keyword-only and do not receive an
    # adapter. Protect their adapter entry points as well, before invocation.
    from project_adapter._entry import Adapter
    for methods,wrapper in (({
        'run_guide_rewards':'길라잡이','run_event_rewards':'이벤트','run_mail_rewards':'우편',
        'run_achievement_rewards':'업적','run_album_rewards':'화첩','run_blessing_rewards':'가호',
        'run_inventory_use':'인벤토리 사용','run_market_inventory':'거래소','run_seal_release':'단 봉인해제',
        'run_treasure_region_entry':'보물찾기','run_spirit_training':'영기 수련'},service_wrapper),
        ({'run_field_boss_entry':'월드보스','_run_field_boss_entry':'월드보스',
          'run_falling_battle':'낙화의 전장','run_ascension_tower':'승천의 탑'},combat_wrapper)):
        for name,label in methods.items():
            original=getattr(Adapter,name,None)
            if original is not None:setattr(Adapter,name,wrapper(original,label))
    # Movement/resupply may run inside the native idle monitor. They are not
    # rescheduled, but their internal waits must not become appointment slots.
    for name in ('run_favorite_hunt','run_town_return','run_potion_purchase'):
        original=getattr(Adapter,name,None)
        if original is not None:
            def scoped(*args,_original=original,_name=name,**kwargs):
                previous=getattr(LOCAL,'feature',None);LOCAL.feature=_name
                try:return _original(*args,**kwargs)
                finally:LOCAL.feature=previous
            setattr(Adapter,name,scoped)
    LOG.addFilter(HeldEnd())
    from project_adapter.stall_recovery import StallRecovery
    if not getattr(StallRecovery._recover,'_owner_wakes',False):
        StallRecovery._recover=wake_before_recovery(StallRecovery._recover)
    from owner_town_wait import install as install_town_wait
    install_town_wait()
    from owner_dungeon_time import install as install_dungeon_time
    install_dungeon_time()
    from owner_dungeon_reentry import install as install_dungeon_reentry
    install_dungeon_reentry()
    gui._owner_schedule_priority=True
    LOG.info('일정 충돌 방지 준비 · 보스 예약 15분 전부터 부수 작업 신규 시작 보류 · 전투 중 재진입 금지')
