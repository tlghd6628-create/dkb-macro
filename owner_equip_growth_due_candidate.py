"""Verified equipment changes request the next safe same-worker growth visit.

No inventory callback enters growth recursively. The existing idle admission,
boss windows, native growth invocation and configurable retry planner remain
in charge. An immediate visit is claimed once per durable equip receipt.
"""
from functools import wraps
import threading,time

LOCAL=threading.local()


def idle_admissible(timetable,adapter,context,inputs):
    from owner_schedule_priority import hold_reason,LOCAL as priority
    from owner_equip_runtime_install_candidate import LOCAL as equipment
    if (getattr(LOCAL,'active',False) or getattr(equipment,'active',False)
        or getattr(timetable.LOCAL,'job',None) or getattr(timetable.LOCAL,'native_job',None)
        or getattr(priority,'feature',None) or hold_reason(adapter)
        or getattr(context,'input_depth',0) or getattr(inputs,'held',())):return False
    ui=getattr(adapter,'_owner_mission_ui',None)
    if ui is not None and ui.context is context and ui.inputs is inputs:
        from owner_emote_dispatch import navigation_open
        if navigation_open(ui):return False
    return True


def pending_request(adapter,plan):
    from owner_hunt_rules_candidate import configured_identity
    from owner_progression import state
    from owner_equipment_upgrade_candidate import Journal
    from owner_gear_settings_candidate import Store
    if plan.values.get('auto_growth.equipment.enabled') is not True:return None
    profile=configured_identity(adapter.project.root);progress=state(adapter)
    if not profile or not progress.character or not 0<=time.monotonic()-progress.observed<=180:return None
    journal=Journal(adapter.project.root,profile+'|'+progress.character)
    if not journal.path.exists():return None
    request=journal.growth_request()
    if not request or Store(adapter.project.root,profile).read()['grades'][request.get('candidate_grade','희귀')].get('enabled') is not True:return None
    return journal,request,profile,progress.character


def install(timetable):
    if getattr(timetable.post_equip_growth,'_owner_equip_immediate_due',False):return
    original_post=timetable.post_equip_growth;original_idle=timetable.idle_once;original_invoke=timetable.invoke

    @wraps(original_post)
    def post(adapter,context,inputs,plan):
        from owner_equipment_upgrade_candidate import Hold
        if not idle_admissible(timetable,adapter,context,inputs):return False
        try:
            pending=pending_request(adapter,plan)
            if pending is None:return False
            journal,request,profile,character=pending
            occurrence=plan.state.get('gear')
            if not isinstance(occurrence,dict) or occurrence.get('status')=='running':return False
            current=timetable.now();days=timetable.selected_days(plan.cfg,timetable.BY_KEY['gear'])
            if not plan.cfg.get('enabled',True) or (days is not None and current.weekday() not in days):return False
            # An old request's10minute pre-input backoff cannot delay a newly
            # equipped item. Same-request failures retain their own backoff.
            key=(profile,character,request['growth_request_id'])
            if getattr(adapter,'_owner_post_equip_request_key',None)!=key:
                adapter._owner_post_equip_request_key=key;adapter._owner_post_equip_retry_at=0
            context.checkpoint()
            LOCAL.active=True;LOCAL.dispatch=(adapter,context,plan,journal,request)
            return original_post(adapter,context,inputs,plan)
        except (Hold,ValueError,KeyError,TypeError,OSError) as exc:
            timetable.LOG.warning('장착 후 성장 대기 · %s',exc);return False
        finally:
            LOCAL.active=False;LOCAL.dispatch=None

    @wraps(original_invoke)
    def invoke(adapter,job,context,inputs,*args,**kwargs):
        dispatch=getattr(LOCAL,'dispatch',None)
        if not dispatch or dispatch[0] is not adapter or dispatch[1] is not context or job.key!='gear':
            return original_invoke(adapter,job,context,inputs,*args,**kwargs)
        _,_,plan,journal,request=dispatch
        context.checkpoint();journal.claim_growth_dispatch(request['growth_request_id'])
        previous=getattr(timetable.LOCAL,'job',None);timetable.LOCAL.job='gear'
        old_target=getattr(adapter,'_owner_post_equip_target',None)
        adapter._owner_post_equip_target=dict(request)
        adapter._owner_growth_all_goals_verified=False
        result=False;finished=False;begun=False
        try:
            plan.begin('gear');begun=True
            result=original_invoke(adapter,job,context,inputs,*args,**kwargs)
            context.checkpoint();finished=True
            return result
        finally:
            # The claimed receipt survives interruption. Only the timed
            # planner may admit another fresh reading after this visit.
            adapter._owner_post_equip_target=old_target;timetable.LOCAL.job=previous
            pending_hold=getattr(adapter,'_owner_growth_pending_hold',False)
            complete=getattr(adapter,'_owner_growth_all_goals_verified',False)
            if begun:
                stop=getattr(context,'stop',None)
                if stop is not None and stop.is_set():
                    plan.state['gear']['status']='pending';plan.state['gear']['attempts']-=1;plan.commit()
                else:
                    from owner_outcome import classify
                    decided=classify('gear',adapter,result) if finished else None
                    if decided is not None:plan.apply_outcome('gear',decided)
                    else:plan.finish('gear',finished and result is not False and not pending_hold,
                                     unverified=finished and not complete)

    @wraps(original_idle)
    def idle(adapter,context,inputs):
        if idle_admissible(timetable,adapter,context,inputs):
            context.checkpoint()
            plan=timetable.planner(adapter)
            # Refresh reset/config/boss changes without invoking any job.
            refresh=getattr(plan,'due',None)
            if callable(refresh):refresh()
            if post(adapter,context,inputs,plan):return True
        return original_idle(adapter,context,inputs)

    post._owner_equip_immediate_due=True
    timetable.post_equip_growth=post;timetable.invoke=invoke;timetable.idle_once=idle
