"""One explicit real action on the production Session and native dispatcher.

Only the current reward/cleanup page is registered. No new navigation or input
implementation, no second worker, and no full macro startup is introduced.
"""
import logging
import queue
import tkinter as tk
import importlib

LOG=logging.getLogger('project_gui.DKB')

def visible(message,*args):
    text=message%args if args else message
    LOG.info(text,extra={'gui_message':text,'state_transition':True})

TARGETS={
 'auto_rewards.guide.enabled':('guide','길라잡이'),
 'auto_rewards.event.enabled':('events','이벤트·출석'),
 'auto_rewards.mail.enabled':('mail','우편'),
 'auto_rewards.achievement.enabled':('achievement','업적'),
 'auto_rewards.training_log.enabled':('training_log','도사 수행록'),
 'auto_register.market.enabled':('market','거래소 등록'),
 'auto_register.equipment_disassembly.enabled':('disassembly','장비 분해'),
}
# Production entry points, exactly those called by the original orchestrator.
# The original DKB capability list and native dispatcher have no training-log
# implementation. Keep that slot disabled instead of inventing a substitute.
PATHS={
 'auto_rewards.guide.enabled':('adapter','run_guide_rewards'),
 'auto_rewards.event.enabled':('adapter','run_event_rewards'),
 'auto_rewards.mail.enabled':('adapter','run_mail_rewards'),
 'auto_rewards.achievement.enabled':('adapter','run_achievement_rewards'),
 'auto_rewards.training_log.enabled':None,
 'auto_register.market.enabled':('adapter','run_market_inventory'),
 'auto_register.equipment_disassembly.enabled':('project_adapter.market_inventory','run_equipment_disassembly'),
}


def prepare(adapter,context,inputs):
    """Reuse production wake/menu paths; rewards are allowed in a dungeon."""
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_special_contexts import NAMES
    from owner_startup_stage import DUNGEON,EXIT,MENU
    from owner_start_menu import normalize
    context.checkpoint()
    adapter.exit_sleep_mode(context,inputs)
    service=TownServices(adapter,context,inputs,list(dict.fromkeys([DUNGEON,EXIT,MENU,'버튼_나가기',*AUTO_NAMES,*NAMES])))
    normalize(service)
    # The inventory's left panel covers the original dungeon clock. Reuse
    # its existing paired I-key protocol before reading remaining time.
    from owner_progression import inventory_parts,open_inventory_by_key
    if any(inventory_parts(service.capture())):
        context.wait(.12)
        if any(inventory_parts(service.capture())):
            open_inventory_by_key(service);context.checkpoint();service.key(0x49);context.wait(.2)
            if any(inventory_parts(service.capture())):
                raise RuntimeError('인벤토리 닫힘 확인 필요 · 남은 시간 확인 후 TEST 가능')
    from owner_reward_context import admit
    observation=admit(adapter,context,inputs,service=service)
    if not observation['allowed']:raise RuntimeError(observation['reason'])


def execute(adapter,context,inputs,key,*,manual=True):
    """Call the same production entry, retaining its guards and policies.

TEST is a one-shot request, independent of the automatic ON/OFF switch. Its
copied values expose only this feature; disk settings and timetable receipts
are never marked completed by the test UI.
"""
    from owner_timetable import LOCAL
    job_id,label=TARGETS[key]
    context.checkpoint()
    path=PATHS[key]
    if path is None:raise RuntimeError('기존 실행 경로 없음 · '+label)
    from owner_schedule_priority import hold_reason
    reason=hold_reason(adapter,label=label)
    if reason:raise RuntimeError('TEST 보류 · '+reason)
    target=adapter if path[0]=='adapter' else importlib.import_module(path[0])
    function=getattr(target,path[1])
    before=adapter.values
    prefix=key.removesuffix('enabled')
    adapter.values={k:(v if not k.endswith('.enabled') or k.startswith(prefix) else False) for k,v in before.items()}
    adapter.values[key]=True
    previous=getattr(LOCAL,'native_job',None);LOCAL.native_job=job_id
    from owner_reward_cycle import LOCAL as cycle
    old_manual=getattr(cycle,'manual',False);cycle.manual=manual
    try:
        operation=(lambda:function(context,inputs)) if path[0]=='adapter' else (lambda:function(adapter,context,inputs))
        return context.run_action(key.removesuffix('.enabled'),operation)
    finally:LOCAL.native_job=previous;adapter.values=before;cycle.manual=old_manual


class OneAction:
    """An adapter delegate, owned and closed by the ordinary Session worker."""
    def __init__(self,adapter,key,ready,events):
        self.adapter,self.key,self.ready,self.events=adapter,key,ready,events
    def __getattr__(self,name):return getattr(self.adapter,name)
    def close(self):return self.adapter.close()
    def run(self,context,inputs):
        label=TARGETS[self.key][1]
        try:
            if not callable(getattr(context,'run_action',None)):
                raise RuntimeError('실전 실행 문맥이 연결되지 않았습니다 · 입력 없음')
            if self.ready is not None:self.ready.wait(context)
            context.checkpoint()
            visible('실전 TEST 시작 · %s · 선택 항목 1회 실행',label)
            from owner_scene_archive import capture_scope
            with capture_scope(self.adapter,context,source='reward_test'):
                prepare(self.adapter,context,inputs)
                result=execute(self.adapter,context,inputs,self.key)
            held=getattr(self.adapter,'_owner_disassembly_outcome',None) if self.key.endswith('equipment_disassembly.enabled') else None
            if getattr(self.adapter,'_owner_reward_cycle_hold',None):text='보류 · '+self.adapter._owner_reward_cycle_hold
            elif isinstance(held,dict) and held.get('state')=='confirmed' and held.get('verified') is True:text='분해 완료 · 결과 확인'
            elif isinstance(held,dict) and held.get('state')=='not_attempted':text='보류 · '+held['reason']
            elif getattr(self.adapter,'_owner_reward_last_outcome',None) in ('claimed','none','partial','failed'):
                from owner_reward_flow import LABELS
                text=LABELS[self.adapter._owner_reward_last_outcome]+' · 실행 로그 확인'
            elif result is False:text='실패 · 실행 로그 확인'
            else:text='처리 종료 · 실행 로그 확인'
            # Returning True from a native routine alone proves neither a
            # received reward nor a destructive action's postcondition.
            visible('실전 TEST 결과 · %s · %s',label,text)
            self.events.put((text,None))
        except BaseException as exc:
            from biol_base.session import Cancelled
            text='중지됨' if isinstance(exc,Cancelled) else '실패 · '+str(exc)
            visible('실전 TEST 결과 · %s · %s',label,text)
            self.events.put((text,str(exc)))
            raise


class Controller:
    def __init__(self,gui):self.gui=gui;self.events=queue.Queue();self.active=False
    def start(self,key,result,parent):
        gui=self.gui
        if key not in TARGETS:raise ValueError('이 탭의 TEST 대상이 아닙니다.')
        session=gui.session
        try:
            with session.lock:
                state=session.snapshot()
                busy=getattr(getattr(gui,'input_preparation',None),'busy',lambda:False)()
                closing=getattr(gui,'closed',None)
                if (self.active or state.get('worker_alive') or state.get('status') in ('running','paused')
                    or busy or (closing is not None and closing.is_set())):
                    result.set('완전히 중지한 뒤 TEST');return False
                from owner_content_entry import prepare_test_window
                prepare_test_window(gui)
                # Session.start owns the gate, input factory, stop/pause,
                # generation and cleanup. Restore its factory synchronously;
                # ordinary Start can never inherit a queued test adapter.
                factory=session.adapter_factory
                ready=getattr(gui,'_owner_ocr_readiness',None)
                self.active=True
                def one_adapter():
                    from operating_policy import PolicyAdapter
                    outer=factory()
                    if not isinstance(outer,PolicyAdapter):
                        outer.close()
                        raise RuntimeError('기존 실행 정책 연결 확인 필요 · 입력 없음')
                    # Preserve the product's context.run_action, before-action
                    # policy, Stop/Pause and error handling around the delegate.
                    outer.adapter=OneAction(outer.adapter,key,ready,self.events)
                    return outer
                session.adapter_factory=one_adapter
                try:session.start()
                finally:session.adapter_factory=factory
            result.set('실행 중');gui.root.after(100,lambda:self.poll(result))
            return True
        except Exception as exc:
            self.active=False;result.set(str(exc));visible('실전 TEST 준비 실패 · %s',exc);return False
    def poll(self,result):
        try:text,error=self.events.get_nowait()
        except queue.Empty:
            if self.gui.session.snapshot().get('worker_alive'):
                self.gui.root.after(100,lambda:self.poll(result));return
            text='종료 · 실행 로그 확인'
        # Keep the UI locked until the production worker releases its inputs.
        if self.gui.session.snapshot().get('worker_alive'):
            self.events.put((text,None));self.gui.root.after(100,lambda:self.poll(result));return
        state=self.gui.session.snapshot()
        if state.get('error'):text='실패 · '+str(state['error'])
        self.active=False
        try:result.set(text)
        except tk.TclError:pass


def controller(gui):
    if getattr(gui,'_owner_reward_action_test',None) is None:gui._owner_reward_action_test=Controller(gui)
    return gui._owner_reward_action_test
