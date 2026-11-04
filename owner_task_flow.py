"""Defer menu-only services until the game's own quest/hunt is active.

Native game handlers remain sequential on their owning worker. No second input
thread is created and no game movement/combat implementation is replaced.
"""
from functools import wraps
import logging
import re
import threading
import time

class ServiceThreat(BaseException):pass

LOCAL=threading.local()
IN_PLACE={
    'auto_rewards.guide.enabled','auto_rewards.event.enabled','auto_rewards.mail.enabled',
    'auto_rewards.achievement.enabled','auto_rewards.album.enabled','auto_rewards.training_log.enabled',
    'auto_rewards.inventory_use.enabled','auto_rewards.blessing.enabled','auto_rewards.seal_release.enabled',
    'auto_growth.equipment.enabled','auto_growth.blessing.enabled','auto_growth.taoist.enabled',
    'auto_growth.energy.enabled','inner_path.enabled'}
BOOTSTRAP={'auto_rewards.inventory_use.enabled'}


def selected_values(old,keys):
    values={key:(False if key.endswith('.enabled') else value) for key,value in old.items()}
    for key in keys:values[key]=True
    return values


def bootstrap(adapter,context,inputs,ordinary):
    """Open/equip early gear first. Enhancement stays after reward collection."""
    if adapter.mode not in ('main_quest','sub_quest'):return set()
    if getattr(adapter,'_owner_bootstrapped_context',None) is context:return set()
    keys={key for key in BOOTSTRAP if adapter.values.get(key) is True}
    from owner_progression import state
    from owner_startup_receipts import Preparation
    progress=state(adapter)
    ready=False
    if keys and progress.character:
        try:ready=Preparation(adapter.project.root,progress.character).starter_ready()
        except (OSError,ValueError):logging.getLogger('project_gui.DKB').warning('초기 준비 기록 재확인 필요 · 실제 장착 상태로 확인')
    if ready:
        logging.getLogger('project_gui.DKB').info('초기 장비 준비 완료 기록 · 무기·반지·팔찌 장착 · 시작 시 상자·구매·장착 재처리 생략')
        context.checkpoint();adapter._owner_bootstrapped_context=context;return keys
    if keys:
        context.checkpoint();old=adapter.values;adapter.values=selected_values(old,keys)
        adapter._owner_preparing_gears=True
        try:
            adapter.exit_sleep_mode(context,inputs)
            logging.getLogger('project_gui.DKB').info('초반 준비 · 부채·팔찌·반지 수령·장착 후 퀘스트 시작 · 강화는 보상 수령 이후')
            ordinary(adapter,context,inputs,wait_for_hunt=False,potion_done=True,periodic_wait=False)
        finally:adapter.values=old;adapter._owner_preparing_gears=False
    context.checkpoint();adapter._owner_bootstrapped_context=context
    return keys


def pending(adapter,context):
    item=getattr(adapter,'_owner_pending_services',None)
    return item if item and item['context'] is context and not context.stop.is_set() else None


def defer(adapter,context,inputs):
    keys={key for key in IN_PLACE if adapter.values.get(key) is True}
    if keys:adapter._owner_pending_services={'context':context,'inputs':inputs,'keys':keys}
    return keys


def dispatch(adapter,context,ordinary):
    # Native waits may call back on the same worker. Never start another
    # ancillary scope inside the scope already owning its menu/input.
    if getattr(LOCAL,'servicing',False):return False
    item=pending(adapter,context)
    if not item:return False
    context.checkpoint()
    from owner_schedule_priority import hold_reason
    if hold_reason(adapter):
        logging.getLogger('project_gui.DKB').info('부수 작업 보류 · 보스 출발 시간 보호 · 기존 대기열 유지')
        return False
    old=adapter.values
    # Favorite-hunt's normal receipt includes entering sleep mode. Wake before
    # opening menus, while preserving the game's AUTO mode and location.
    keys={key for key in item['keys'] if old.get(key) is True};milestone=None
    if adapter.mode in ('main_quest','sub_quest'):
        from owner_progression import state,GROWTH
        milestone=state(adapter).due()
        if milestone is None:keys.discard(GROWTH)
    # A quest opportunity processes one feature, then gives control back to
    # the native quest/death/boss watcher. Hunting can drain the full queue.
    eligible=set(keys)
    if adapter.mode in ('main_quest','sub_quest') and keys:
        order=('auto_rewards.inventory_use.enabled','auto_growth.equipment.enabled',
               'auto_rewards.mail.enabled','auto_rewards.guide.enabled','auto_rewards.achievement.enabled',
               'auto_rewards.album.enabled','auto_rewards.event.enabled')
        chosen=next((key for key in order if key in keys),sorted(keys)[0]);keys={chosen}
    remaining=eligible-keys
    adapter._owner_pending_services=dict(item,keys=remaining) if remaining else None
    if not keys:
        adapter._owner_last_service=time.monotonic()
        return True
    adapter.exit_sleep_mode(context,item['inputs'])
    context.checkpoint()
    if hasattr(adapter,'window'):
        from project_adapter.main_quest import StateROIs
        from project_adapter.town_services import TownServices
        slots=getattr(adapter,'_owner_service_slots',None)
        if slots is None:
            slots=StateROIs(adapter.project.root/'profiles'/adapter.project.code)
            adapter._owner_service_slots=slots
        probe=TownServices(adapter,context,item['inputs'],[slots.by_key[k]['roi'] for k in ('death','boss')])
        frame=probe.capture()
        if any(probe.detector.find(slots.by_key[k]['roi'],frame,threshold=.98) for k in ('death','boss')):
            adapter._owner_pending_services=item
            adapter._owner_last_service=time.monotonic()
            return False
    adapter.values=selected_values(old,keys)
    from owner_rewards import LOCAL as REWARD_LOCAL
    previous_adapter=getattr(REWARD_LOCAL,'adapter',None);REWARD_LOCAL.adapter=adapter
    previous_servicing=getattr(LOCAL,'servicing',False);LOCAL.servicing=True
    previous_milestone=getattr(adapter,'_owner_growth_milestone',None)
    adapter._owner_growth_milestone=milestone
    try:
        logger=logging.getLogger('project_gui.DKB')
        logger.info('퀘스트 이동·자동사냥 확인 · 현재 자리에서 보상·성장 처리')
        result=ordinary(adapter,context,item['inputs'],wait_for_hunt=False,potion_done=True,periodic_wait=False)
        if result is not False and 'auto_growth.taoist.enabled' in keys:
            from owner_skill_growth_candidate import dispatch_after_native
            from owner_timetable import scheduled_call,BY_KEY
            # Style is an outer-loop operation, not the native menu-entry
            # callback. It must still obey the same gear appointment.
            scheduled_call(dispatch_after_native,BY_KEY['gear'].label,
                           (adapter,context,item['inputs']),{},adapter)
        if milestone is not None and 'auto_growth.equipment.enabled' in keys:
            from owner_progression import state
            state(adapter).attempted(milestone)
            logger.info('레벨 구간 강화 점검 완료 · %d레벨 구간 · 재료 부족 시 실제 강화 생략',milestone)
        return True
    except __import__('owner_chore_transition').ChoreYield:
        adapter._owner_pending_services=dict(item,keys=eligible)
        raise
    except ServiceThreat:
        adapter._owner_pending_services=item
        logging.getLogger('project_gui.DKB').warning('부수 작업 중 사망 화면 감지 · 보상 입력을 중단하고 퀘스트 감시로 복귀')
        return False
    except RuntimeError as exc:
        # 19:35 real run: one unopened mail window ended the whole session. The native
        # dispatcher already recovered its screen; a side job waits for its next cycle.
        if '처리 중단' not in str(exc):raise
        logging.getLogger('project_gui.DKB').warning('부수 작업 미완료 · %s · 다음 주기에 재시도 · 매크로 계속',str(exc)[:80])
        return False
    finally:
        adapter.values=old;adapter._owner_last_service=time.monotonic();LOCAL.servicing=previous_servicing;REWARD_LOCAL.adapter=previous_adapter
        adapter._owner_growth_milestone=previous_milestone


def wrap_features(ordinary):
    @wraps(ordinary)
    def features(adapter,context,inputs,**kwargs):
        if getattr(LOCAL,'dispatching',False):return ordinary(adapter,context,inputs,**kwargs)
        prepared=bootstrap(adapter,context,inputs,ordinary)
        keys=defer(adapter,context,inputs)-prepared
        if pending(adapter,context):adapter._owner_pending_services['keys']=keys
        if not keys:adapter._owner_pending_services=None
        if not keys and not prepared:return ordinary(adapter,context,inputs,**kwargs)
        old=adapter.values
        masked=set(keys)|prepared
        from owner_progression import state
        if adapter.mode in ('main_quest','sub_quest') or (state(adapter).route=='hunt' and not getattr(adapter,'_owner_hunt_ready',False)):
            masked|={key for key in old if key.endswith('.enabled') and key.startswith(('auto_schedule.','auto_challenge.'))}
        adapter.values=dict(old,**{key:False for key in masked})
        saved_hunt=getattr(adapter,'run_favorite_hunt',None)
        had_override='run_favorite_hunt' in vars(adapter)
        def arrived(*args,**kw):
            result=saved_hunt(*args,**kw)
            if result is True or (isinstance(result,str) and result in ('HUNTING_RESUMED','HUNTING_STARTED')):
                context.checkpoint();LOCAL.dispatching=True
                try:dispatch(adapter,context,ordinary)
                finally:LOCAL.dispatching=False
            return result
        if callable(saved_hunt):adapter.run_favorite_hunt=arrived
        try:return ordinary(adapter,context,inputs,**kwargs)
        finally:
            adapter.values=old
            if callable(saved_hunt):
                if had_override:adapter.run_favorite_hunt=saved_hunt
                else:del adapter.run_favorite_hunt
    features._owner_task_flow=True
    return features


class MotionLogs(logging.Handler):
    def emit(self,record):
        try:
            match=re.search(r'퀘스트 상태판정: mode=(\w+) selected=(\w+)',record.getMessage())
            if match:LOCAL.quest_state=(match[1],match[2],time.monotonic())
        except Exception:pass


def install(gui):
    if getattr(gui,'_owner_task_flow',False):return
    from project_adapter._entry import Adapter
    from project_adapter.main_quest import BoundedMainQuestRunner
    import runtime_capture,sys
    if not getattr(runtime_capture.capture,'_owner_service_death',False):
        from project_adapter.main_quest import StateROIs
        slots=StateROIs(gui.project.root/'profiles'/gui.project.code)
        capture_original=runtime_capture.capture
        @wraps(capture_original)
        def capture(*args,**kwargs):
            frame=capture_original(*args,**kwargs)
            if getattr(LOCAL,'servicing',False):
                spec=slots.by_key['death'];hit=slots.detector.find(spec['roi'],frame,threshold=.98)
                if hit:
                    now=time.monotonic();previous=getattr(LOCAL,'death_frame',None)
                    if previous is not None and .08<=now-previous<2:raise ServiceThreat()
                    LOCAL.death_frame=now
                else:LOCAL.death_frame=None
            return frame
        capture._owner_service_death=True;runtime_capture.capture=capture
        for name,module in tuple(sys.modules.items()):
            if name.startswith('project_adapter') and module is not None:
                for key,value in tuple(vars(module).items()):
                    if value is capture_original:setattr(module,key,capture)
    class ServiceOpportunity(BaseException):pass
    if not getattr(Adapter._run_auto_features,'_owner_task_flow',False):
        ordinary_features=Adapter._run_auto_features
        ordinary_run=Adapter.run
        ordinary_quest=Adapter.run_main_quest
        ordinary_step=BoundedMainQuestRunner.step
        Adapter._run_auto_features=wrap_features(ordinary_features)
        @wraps(ordinary_run)
        def run(adapter,context,inputs):
            if getattr(adapter,'_owner_initial_context',None) is not context:
                context.checkpoint()
                if adapter.mode in ('main_quest','sub_quest'):
                    adapter.exit_sleep_mode(context,inputs)
                    if adapter.values.get('main_quest.first_coupon.enabled') is True:
                        from owner_startup_receipts import initial_coupons
                        coupon_changed=initial_coupons(adapter,context,inputs)
                        # Coupon items arrive through mail before box selection.
                        before=adapter.values;adapter.values=dict(before,**{'auto_rewards.mail.enabled':True})
                        try:
                            if coupon_changed and adapter.run_mail_rewards(context,inputs) is False:
                                raise RuntimeError('초반 쿠폰 우편 수령 확인 실패 · 장비 상자 사용 전에 확인이 필요합니다.')
                        finally:adapter.values=before
                    prepared=bootstrap(adapter,context,inputs,ordinary_features)
                    defer(adapter,context,inputs)
                    if pending(adapter,context):adapter._owner_pending_services['keys']-=prepared
                adapter._owner_initial_context=context
            return ordinary_run(adapter,context,inputs)
        Adapter.run=run
        @wraps(ordinary_quest)
        def quest(adapter,context,inputs):
            old=getattr(LOCAL,'quest_owner',None)
            LOCAL.quest_owner=(adapter,context,inputs)
            try:
                from owner_progression import state
                from owner_work_resume import ResumeWork
                progress=state(adapter)
                if not getattr(adapter,'_owner_temporary_work',None):
                    target=progress.choose_mode(adapter.mode)
                    if target!=adapter.mode:raise ResumeWork(target,allow_growth=True)
                    progress.grant_retry(adapter.mode)
                    progress.begin_work(adapter.mode)
                    from owner_quest_preflight import read_quest
                    read_quest(adapter,context,inputs)
                while True:
                    context.checkpoint()
                    try:
                        mode=adapter.mode;result=ordinary_quest(adapter,context,inputs)
                        from owner_progression import state
                        state(adapter).outcome(mode,result)
                        if result=='DEATH_RECOVERED' and progress.blocked(mode):
                            target=progress.choose_mode(mode)
                            LOG=logging.getLogger('project_gui.DKB')
                            LOG.info('퀘스트 전투 보류 저장 · 모드=%s · 사망 2회 · 당시 전투력=%s · 다음=%s',mode,progress.power,target)
                            raise ResumeWork(target,allow_growth=True)
                        return result
                    except ServiceOpportunity:
                        LOCAL.dispatching=True
                        try:dispatch(adapter,context,ordinary_features)
                        finally:LOCAL.dispatching=False
                        # A fresh native runner starts its timers after services.
            finally:LOCAL.quest_owner=old
        Adapter.run_main_quest=quest
        @wraps(ordinary_step)
        def step(runner,*args,**kwargs):
            started=time.monotonic()
            try:result=ordinary_step(runner,*args,**kwargs)
            except TypeError as exc:
                # The native guide detector can return nothing on one frame. It killed a run after an hour.
                if 'cannot unpack non-iterable NoneType' not in str(exc):raise
                logging.getLogger('project_gui.DKB').warning('튜토리얼 판독 한 프레임 건너뜀 · %s',exc)
                result=None
            owner=getattr(LOCAL,'quest_owner',None);state=getattr(LOCAL,'quest_state',None)
            if owner and state and state[1]=='auto_move' and state[2]>=started:
                adapter,context,inputs=owner
                elapsed=time.monotonic()-getattr(adapter,'_owner_last_service',-1e30)
                if not pending(adapter,context) and elapsed>=120:defer(adapter,context,inputs)
                if pending(adapter,context) and elapsed>=20 and not getattr(inputs,'held',()):
                    context.checkpoint();raise ServiceOpportunity('현재 위치에서 부수 작업 처리')
            return result
        BoundedMainQuestRunner.step=step
    handler=MotionLogs();gui.logger.addHandler(handler)
    gui.root.bind('<Destroy>',lambda event:gui.logger.removeHandler(handler) if event.widget is gui.root else None,add='+')
    gui._owner_task_flow=True
