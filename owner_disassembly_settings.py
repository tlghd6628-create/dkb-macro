"""Disassembly preferences, using the native schema and sole worker.

The original sequence is retained. User-supplied selected/unselected dialog
controls add a grade proof immediately before its existing commit button.
"""
import copy
import logging
import threading,time
from types import SimpleNamespace
from functools import wraps

MASTER='auto_register.equipment_disassembly.enabled'
GRADES=(('normal','일반'),('rare','희귀'),('hero','영웅'))
LOG=logging.getLogger('project_gui.DKB')
LOCAL=threading.local()
EXEC='버튼_인벤토리_분해실행'
CONFIRM='버튼_인벤토리_지금분해'
ENTRY='버튼_인벤토리_분해'


def grade_key(grade):return 'auto_register.equipment_disassembly.grades.'+grade


def add_fields(schema):
    groups=[g for t in schema['tabs'] for g in t['groups']]
    entries={f['id']:(g,f) for g in groups for f in g['fields']}
    if MASTER not in entries:return schema
    group,master=entries[MASTER]
    at=group['fields'].index(master)+1
    for code,label in GRADES:
        key=grade_key(code)
        if key in entries:continue
        field=copy.deepcopy(master)
        field.update(id=key,label=label,default=code=='normal',existing_default=code=='normal',settings_only=True)
        field.pop('enabled_if',None)
        group['fields'].insert(at,field);at+=1
    return schema


def selected(values):
    return tuple(label for code,label in GRADES if values.get(grade_key(code),code=='normal') is True)


def observe_result(scope,frame):
    from owner_reward_visual_guard import disassembly_result
    if not scope.commit or scope.proof:return
    now=time.monotonic()
    if not disassembly_result(frame):scope.proof_first=None;return
    if scope.proof_first is None:scope.proof_first=now
    elif now-scope.proof_first>=.08:scope.proof=True


class OptionalConfirmLog(logging.Filter):
    def filter(self,record):
        scope=getattr(LOCAL,'scope',None)
        if (scope and scope.proof and record.thread==threading.get_ident()
            and CONFIRM in record.getMessage() and '미감지' in record.getMessage()):
            record.msg='장비 분해 완료 확인 · 추가 확인창 없음';record.args=()
            record.gui_message=record.msg;record.state_transition=True
        return True


def install(native,aliases=()):
    original=native.run_equipment_disassembly
    if getattr(original,'_owner_disassembly_grades',False) is True:return
    from project_adapter.town_services import TownServices
    if getattr(TownServices.__init__,'_owner_disassembly_result',False) is not True:
        raw_init=TownServices.__init__
        @wraps(raw_init)
        def init(service,*args,**kwargs):
            raw_init(service,*args,**kwargs)
            # Native TownServices installs capture on each instance, not on
            # the class. Observe that exact existing callable without adding
            # captures, waits, input workers or a second action path.
            raw_capture=service.capture
            @wraps(raw_capture)
            def capture(*a,**k):
                frame=raw_capture(*a,**k);scope=getattr(LOCAL,'scope',None)
                if scope is not None and service.adapter is scope.adapter and service.context is scope.context:
                    observe_result(scope,frame)
                return frame
            service.capture=capture
        init._owner_disassembly_result=True;TownServices.__init__=init
    if getattr(TownServices.click_hit,'_owner_disassembly_grades',False) is not True:
        raw_click=TownServices.click_hit
        @wraps(raw_click)
        def guarded(service,hit,*args,**kwargs):
            scope=getattr(LOCAL,'scope',None)
            if scope is None or service.adapter is not scope.adapter or service.context is not scope.context:
                return raw_click(service,hit,*args,**kwargs)
            from owner_disassembly_ui import Hold,NoItems,configure,pair
            def requested(name):
                row=service.detector.entries.get(name)
                return row is not None and row['x']<=hit[0]<row['x']+row['w'] and row['y']<=hit[1]<row['y']+row['h']
            try:
                if requested(ENTRY):
                    from owner_disassembly_ui import observe
                    service.context.checkpoint();service.check()
                    if observe(service.capture()) is not None:
                        pair(service)
                        LOG.info('기존 분해 창 열림 확인 · 중복 열기 생략')
                        return True
                elif requested(EXEC):
                    if scope.commit:raise Hold('이전 분해 요청 결과 확인 필요')
                    configure(service,raw_click,scope.desired)
                    service.context.checkpoint();service.check()
                    view=pair(service)
                    if view.states!=scope.desired or view.empty:raise Hold('최종 분해 등급 재확인 필요')
                    frame=service.capture()
                    from owner_disassembly_ui import observe
                    if observe(frame)!=view:raise Hold('최종 분해 선택 화면 변경')
                    fresh=service.detector.find(EXEC,frame,threshold=.9)
                    if fresh is None or fresh!=hit:raise Hold('기존 분해 실행 버튼 변경')
                    LOG.info('분해 등급 확인 · %s · 기존 분해 절차 실행',', '.join(label for (code,label),enabled in zip(GRADES,scope.desired) if enabled))
                    scope.commit=True
                elif requested(CONFIRM):
                    if not scope.commit:raise Hold('등급 확인 전 최종 분해 확인 차단')
                    if scope.confirm:raise Hold('이전 지금분해 입력 결과 확인 필요')
                    service.context.checkpoint();service.check()
                    fresh=service.detector.find(CONFIRM,service.capture(),threshold=.9)
                    if fresh is None or fresh!=hit:raise Hold('기존 지금분해 확인 버튼 변경')
                    scope.confirm=True
                return raw_click(service,hit,*args,**kwargs)
            except Hold as exc:
                scope.hold=str(exc)
                if isinstance(exc,NoItems):return True
                raise
        guarded._owner_disassembly_grades=True
        TownServices.click_hit=guarded
    @wraps(original)
    def run(adapter,context,inputs,*args,**kwargs):
        context.checkpoint()
        if adapter.values.get(MASTER) is not True:return True
        grades=selected(adapter.values)
        if not grades or getattr(LOCAL,'scope',None) is not None:
            reason='분해 등급 미선택' if not grades else '장비 분해 이미 진행 중'
            adapter._owner_disassembly_outcome={'state':'not_attempted','reason':reason,'verified':False}
            LOG.info('자동 기능 보류 · 장비 분해 · %s',reason);return True
        desired=tuple(label in grades for code,label in GRADES)
        scope=SimpleNamespace(adapter=adapter,context=context,desired=desired,commit=False,confirm=False,hold=None,proof=False,proof_first=None)
        LOCAL.scope=scope
        log_filter=OptionalConfirmLog();LOG.addFilter(log_filter)
        adapter._owner_disassembly_outcome={'state':'running','grades':list(grades),'verified':False}
        try:
            from owner_disassembly_ui import Hold
            try:result=original(adapter,context,inputs,*args,**kwargs)
            except Hold as exc:scope.hold=str(exc);result=False
            context.checkpoint()
            if scope.hold:
                state='sent_unconfirmed' if scope.commit else 'not_attempted'
                adapter._owner_disassembly_outcome={'state':state,'reason':scope.hold,'verified':False}
                LOG.info('자동 기능 보류 · 장비 분해 · %s',scope.hold)
                return result if scope.commit else True
            if scope.proof:
                adapter._owner_disassembly_outcome={'state':'confirmed','reason':'분해 결과 알림 두 화면 확인','grades':list(grades),'verified':True}
                LOG.info('장비 분해 완료 · %s · 결과 알림 확인',', '.join(grades),extra={'gui_message':'장비 분해 완료 · '+', '.join(grades),'state_transition':True})
                return True
            state='processed_unverified' if scope.commit else 'not_attempted'
            adapter._owner_disassembly_outcome={'state':state,'reason':'기존 분해 경로 결과 확인' if scope.commit else '기존 분해 실행 단계 미도달','grades':list(grades),'verified':False}
            return result
        finally:LOG.removeFilter(log_filter);LOCAL.scope=None
    run._owner_disassembly_grades=True
    native.run_equipment_disassembly=run
    from owner_gear_native_install_candidate import _rebind_aliases
    _rebind_aliases(aliases,original,run)
