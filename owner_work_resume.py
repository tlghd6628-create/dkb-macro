"""Restore actual work after a temporary world-boss activity, on one worker."""
from functools import wraps
from dataclasses import dataclass
import logging
from owner_progression import state
LOG=logging.getLogger('project_gui.DKB')


class ResumeWork(BaseException):
    def __init__(self,mode,*,allow_growth=False):self.mode=mode;self.allow_growth=allow_growth


@dataclass
class TemporaryWork:
    context:object
    mode:str
    character:object
    entry_mode:str
    stage_owner:object=None
    stage_epoch:object=None
    returned:bool=False


def current_work(adapter):
    progress=state(adapter)
    # Live quest ownership is stronger than a stored selection or route.
    from owner_task_flow import LOCAL as task
    owner=getattr(task,'quest_owner',None)
    if owner and owner[0] is adapter and adapter.mode in ('main_quest','sub_quest'):return adapter.mode
    return progress.work_mode or adapter.mode


def wrap_entry(ordinary):
    @wraps(ordinary)
    def entry(adapter,context,inputs,*a,**k):
        previous=getattr(adapter,'_owner_temporary_work',None)
        if previous is not None:return ordinary(adapter,context,inputs,*a,**k)
        context.checkpoint();progress=state(adapter)
        saved=TemporaryWork(context,current_work(adapter),progress.character,adapter.mode)
        from owner_startup_stage import LOCAL as stage
        owner=getattr(stage,'owner',None)
        if owner and owner[1] is context:
            saved.stage_owner=owner[0];saved.stage_epoch=owner[0]._owner_stage_epoch
        adapter._owner_temporary_work=saved
        LOG.info('월보 전 작업 보관 · 실제 작업=%s · 선택 모드=%s',saved.mode,adapter.mode)
        try:return ordinary(adapter,context,inputs,*a,**k)
        finally:
            if previous is None:del adapter._owner_temporary_work
            else:adapter._owner_temporary_work=previous
    return entry


def wrap_return(ordinary):
    @wraps(ordinary)
    def returned(adapter,context,inputs,*a,**k):
        saved=getattr(adapter,'_owner_temporary_work',None)
        if saved is None:return ordinary(adapter,context,inputs,*a,**k)
        context.checkpoint()
        if saved.stage_owner is not None and saved.stage_owner._owner_stage_epoch!=saved.stage_epoch:
            from owner_startup_stage import RecheckStage
            raise RecheckStage()
        if saved.context is not context or saved.character!=state(adapter).character:
            raise RuntimeError('월보 복귀 문맥이 변경되어 이전 작업 자동 복원을 보류했습니다.')
        previous_hunt=getattr(adapter,'run_favorite_hunt',None)
        had_override='run_favorite_hunt' in vars(adapter)
        def no_detour(*args,**kwargs):
            context.checkpoint();return True
        # Preserve native town/potion cleanup. A main/story return must not
        # take the native helper's unconditional favorite-hunt detour.
        if saved.mode in ('main_quest','sub_quest'):adapter.run_favorite_hunt=no_detour
        try:result=ordinary(adapter,context,inputs,*a,**k)
        finally:
            if saved.mode in ('main_quest','sub_quest'):
                if had_override:adapter.run_favorite_hunt=previous_hunt
                else:del adapter.run_favorite_hunt
        context.checkpoint()
        if result is not True:return result
        if saved.stage_owner is not None and saved.stage_owner._owner_stage_epoch!=saved.stage_epoch:
            from owner_startup_stage import RecheckStage
            raise RecheckStage()
        if not saved.returned:
            saved.returned=True
            LOG.info('월보 정상 복귀 · 이전 실제 작업=%s · 퀘스트 보류 기록 유지',saved.mode)
            # Unwind the old native activity scopes before the owning route
            # loop restarts a quest. Never recursively run quests inside boss.
            raise ResumeWork(saved.mode)
        return result
    returned._owner_work_resume=True
    return returned


def install(gui):
    from project_adapter._entry import Adapter
    from project_adapter import field_boss
    import sys
    if getattr(gui,'_owner_work_resume',False):return
    original=field_boss.finish_field_boss_return
    if not getattr(original,'_owner_work_resume',False):
        replacement=wrap_return(original)
        field_boss.finish_field_boss_return=replacement
        for name,module in tuple(sys.modules.items()):
            if name.startswith('project_adapter') and module is not None:
                for key,value in tuple(vars(module).items()):
                    if value is original:setattr(module,key,replacement)
        Adapter._run_field_boss_entry=wrap_entry(Adapter._run_field_boss_entry)
    gui._owner_work_resume=True
    LOG.info('월보 복귀 준비 완료 · 직전 실제 작업 복원 · 메인·서사 보류 상태 유지')
