"""Confirmed death thresholds; timeout/recognition failures are separate."""
from functools import wraps
import logging,threading
from owner_progression import state
from owner_work_resume import ResumeWork
LOCAL=threading.local();LOG=logging.getLogger('project_gui.DKB')


class RetryRoute(BaseException):
    def __init__(self,mode):self.mode=mode


def route(progress,requested):
    if progress.blocked('main_quest') and requested=='sub_quest' and progress.last_mode=='main_quest':
        return progress.choose_mode(requested,growth_retry=False)
    if progress.blocked('sub_quest') and requested=='auto_mode' and progress.last_mode=='sub_quest':return 'auto_mode'
    if progress.level is None:
        if requested=='sub_quest' and progress.last_mode=='main_quest':return 'retry_main'
        if requested=='auto_mode' and progress.last_mode=='sub_quest':return 'retry_sub'
        return requested
    if progress.level<50:return requested
    if requested=='sub_quest' and progress.last_mode=='main_quest':
        return 'sub_quest' if progress.deaths.get('main_quest',0)>=2 else 'retry_main'
    if requested=='auto_mode' and progress.last_mode=='sub_quest':
        return 'auto_mode' if progress.deaths.get('sub_quest',0)>=2 else 'retry_sub'
    return requested


def install(gui):
    from project_adapter._entry import Adapter
    if getattr(Adapter.run,'_owner_routes',False):return
    ordinary=Adapter.run
    @wraps(ordinary)
    def run(adapter,context,inputs):
        # Explicit stationary hunt is never redirected to a remembered quest.
        if getattr(adapter,'_owner_stationary_mode',False):
            while True:
                context.checkpoint()
                try:return ordinary(adapter,context,inputs)
                except ResumeWork as resume:
                    if resume.mode!='auto_mode':raise RuntimeError('제자리 사냥 중 예기치 않은 퀘스트 전환이 요청되었습니다.')
                    adapter.mode='auto_mode'
        if getattr(adapter,'_owner_catalog_enabled',False):
            from owner_mission_controller import run as run_catalog
            return run_catalog(adapter,context,inputs)
        if getattr(LOCAL,'active',False):return ordinary(adapter,context,inputs)
        transition=getattr(adapter,'mode_transition',None)
        had_override='mode_transition' in vars(adapter)
        progress=state(adapter)
        def adopt(target,*,growth=True):
            if target not in ('main_quest','sub_quest','auto_mode'):return
            if growth:progress.grant_retry(target)
            before=adapter.mode;adapter.mode=target
            progress.route=({'main_quest':'main','sub_quest':'sub'}[target] if target!='auto_mode'
                            else ('hunt' if progress.blocked('sub_quest') else 'auto'))
            if target=='auto_mode' and before!=target:adapter._owner_hunt_ready=False
            if before!=target:
                LOG.info('저장된 육성 경로 적용 · %s → %s · 현재 전투력=%s · 보류된 임무는 성장 확인 전 건너뜀',before,target,progress.power)
                if callable(transition):transition(target,context)
        # Startup-stage's outer wrapper has already handled special combat.
        # Identify the current character before consulting another character's
        # stored blocks. A stopped session never retains authorization to act.
        if getattr(adapter,'_owner_policy_context',None) is not context:
            context.checkpoint()
            if adapter.mode in ('main_quest','sub_quest') or progress.has_blocks():
                from owner_quest_preflight import read_power
                if not read_power(adapter,context,inputs) and progress.has_blocks():
                    raise RuntimeError('현재 캐릭터·전투력을 확인하지 못해 저장된 퀘스트 보류 경로 적용을 중단합니다.')
            context.checkpoint();adopt(progress.choose_mode(adapter.mode))
            adapter._owner_policy_context=context
        def change(requested,ctx):
            progress=state(adapter);target=route(progress,requested)
            if target.startswith('retry_'):
                progress.functional_retries+=1
                LOG.warning('퀘스트 전환 보류 · 사망 2회 미충족 · 레벨=%s · 모드=%s · 결과=%s · 기능 재확인=%d',progress.level,progress.last_mode,progress.last_outcome,progress.functional_retries)
                if progress.functional_retries>=3:raise RuntimeError('사망 2회가 아닌 퀘스트 기능 오류가 반복되어 확인이 필요합니다.')
                raise RetryRoute('main_quest' if target=='retry_main' else 'sub_quest')
            progress.functional_retries=0
            target=progress.choose_mode(target,growth_retry=False)
            if target=='sub_quest' and progress.level==50:
                progress.route='sub';LOG.info('육성 경로 · 50레벨 메인퀘 사망 2회 확인 → 서사퀘 계속 진행')
            if target=='auto_mode' and progress.level==50 and progress.last_mode=='sub_quest':
                progress.route='hunt';LOG.info('육성 경로 · 서사퀘 사망 2회 확인 → 전투력 기준 사냥터 선택')
            return transition(target,ctx) if callable(transition) else None
        adapter.mode_transition=change;LOCAL.active=True
        try:
            while True:
                context.checkpoint()
                try:return ordinary(adapter,context,inputs)
                except ResumeWork as resume:
                    context.checkpoint()
                    # A return must preserve the actual work, not trigger a
                    # growth retry of a different task merely because it ends.
                    adopt(progress.choose_mode(resume.mode,growth_retry=resume.allow_growth),growth=resume.allow_growth)
                except RetryRoute as retry:
                    # Unwind native nested mode recursion before retrying.
                    context.wait(10);context.checkpoint();adapter.mode=retry.mode
                    if callable(transition):transition(retry.mode,context)
        finally:
            LOCAL.active=False
            if had_override:adapter.mode_transition=transition
            else:del adapter.mode_transition
    run._owner_routes=True;Adapter.run=run;gui._owner_routes=True
    LOG.info('육성 보류 기록 준비 완료 · 캐릭터별 영구 저장 · 확인된 사망 2회 · 재도전 전투력 +15%')
