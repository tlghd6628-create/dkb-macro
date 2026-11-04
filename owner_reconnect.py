"""Reconnect a proved idle-disconnect notice on the existing owning worker.

No inputs run in GUI timers or capture threads. Stopped/paused sessions never
start themselves. Original window/PID guards and native reconnect UI are reused.
"""
from functools import wraps
import logging,sys,threading,time
LOG=logging.getLogger('project_gui.DKB')
LOCAL=threading.local()


class ReconnectRequired(BaseException):pass


class NoticeProbe:
    def __init__(self,detector,name,clock=time.monotonic):
        self.detector=detector;self.name=name;self.clock=clock
        self.seen=None;self.next_probe=0.
    def present(self,frame):
        try:return self.detector.find(self.name,frame,threshold=.97) is not None
        except (TypeError,ValueError):return False
    def observe(self,frame):
        now=self.clock()
        if now<self.next_probe:return False
        self.next_probe=now+.25
        if not self.present(frame):self.seen=None;return False
        if self.seen is not None and .12<=now-self.seen<2:return True
        self.seen=now
        return False


def recover(adapter,context,inputs,detector):
    from project_adapter import idle_reconnect
    from project_adapter.town_services import TownServices
    context.checkpoint()
    hwnd=adapter.window.hwnd
    item=adapter.window.describe(hwnd,require_size=True)
    if not item:raise RuntimeError('접속 복구 대상 게임 창을 확인하지 못했습니다.')
    LOG.warning('접속 종료 안내·게임 시작 화면 확인 · 현재 선택한 서버·캐릭터로 게임 화면 복귀 처리')
    before=context.checkpoint;end=time.monotonic()+120
    def checkpoint():
        before()
        if time.monotonic()>end:raise RuntimeError('접속 종료 안내 복구 120초 시간 초과')
    context.checkpoint=checkpoint
    previous=getattr(LOCAL,'recovering',False);LOCAL.recovering=True
    try:
        result=idle_reconnect.recover_connected_game(adapter,context,inputs,hwnd,item['pid'])
        if result is False:raise RuntimeError('접속 종료 안내 복구가 완료되지 않았습니다.')
        service=TownServices(adapter,context,inputs,idle_reconnect.NAMES)
        deadline=min(end,time.monotonic()+5)
        while time.monotonic()<deadline:
            context.checkpoint();frame=service.capture()
            if (detector.find(idle_reconnect.MENU,frame,threshold=.95) is not None
                and detector.find(idle_reconnect.CHECK,frame,threshold=.97) is None):
                LOG.info('접속 복구 완료 · 게임 기본 화면 재확인 · 기존 진행 모드 재개')
                return True
            context.wait(.1)
        raise RuntimeError('접속 복구 뒤 게임 기본 화면을 확인하지 못했습니다.')
    finally:
        LOCAL.recovering=previous;context.checkpoint=before


def install(gui):
    if getattr(gui,'_owner_reconnect',False):return
    from project_adapter._entry import Adapter
    from project_adapter import idle_reconnect
    from project_adapter.town_services import TownServices
    from roi_runtime import RoiDetector
    import runtime_capture
    detector=RoiDetector(gui.project.root/'profiles'/gui.project.code,idle_reconnect.NAMES)
    if not getattr(runtime_capture.capture,'_owner_idle_notice',False):
        ordinary_capture=runtime_capture.capture
        @wraps(ordinary_capture)
        def capture(*args,**kwargs):
            frame=ordinary_capture(*args,**kwargs)
            owner=getattr(LOCAL,'owner',None)
            if owner and not getattr(LOCAL,'recovering',False):
                adapter,context,inputs,probe=owner
                if (not context.stop.is_set() and not context.pause.is_set()
                    and not context.input_depth and not getattr(inputs,'held',())):
                    if probe.observe(frame):raise ReconnectRequired()
            return frame
        capture._owner_idle_notice=True;runtime_capture.capture=capture
        for name,module in tuple(sys.modules.items()):
            if name.startswith('project_adapter') and module is not None:
                for key,value in tuple(vars(module).items()):
                    if value is ordinary_capture:setattr(module,key,capture)
    if not getattr(Adapter.run,'_owner_idle_reconnect',False):
        ordinary_run=Adapter.run
        @wraps(ordinary_run)
        def run(adapter,context,inputs):
            if getattr(LOCAL,'owner',None):return ordinary_run(adapter,context,inputs)
            probe=NoticeProbe(detector,idle_reconnect.CHECK)
            LOCAL.owner=(adapter,context,inputs,probe);attempts=[]
            try:
                # Initial notice must be handled before coupon/inventory work.
                LOCAL.recovering=True
                try:
                    service=TownServices(adapter,context,inputs,idle_reconnect.NAMES)
                    first=service.capture()
                    def entry_present(frame):
                        return probe.present(frame) or any(
                            detector.find(name,frame,threshold=.97) is not None
                            for name in (idle_reconnect.TOUCH,idle_reconnect.START))
                    if entry_present(first):
                        context.wait(.15)
                        if entry_present(service.capture()):raise ReconnectRequired()
                except ReconnectRequired:
                    recover(adapter,context,inputs,detector);attempts.append(time.monotonic())
                finally:LOCAL.recovering=False
                while True:
                    context.checkpoint()
                    try:return ordinary_run(adapter,context,inputs)
                    except ReconnectRequired:
                        now=time.monotonic();attempts=[t for t in attempts if now-t<600]
                        if len(attempts)>=3:raise RuntimeError('접속 종료가 10분 내 3회 반복되어 추가 재접속을 중단했습니다.')
                        recover(adapter,context,inputs,detector);attempts.append(time.monotonic())
                        probe.seen=None;probe.next_probe=0.
            finally:LOCAL.owner=None;LOCAL.recovering=False
        run._owner_idle_reconnect=True;Adapter.run=run
    gui._owner_reconnect=True
