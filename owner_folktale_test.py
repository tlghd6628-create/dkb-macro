"""One real 전래동화 비경 5시간 run: the timetable's own dispatch on the ordinary Session.

Entry, region choice, AUTO, death return and exit all stay in the native
FolktaleExploration. Nothing here clicks, and no timetable receipt is written.
"""
import logging

LOG=logging.getLogger('project_gui.DKB')
KEY='auto_challenge.secret_folktale_5h.enabled'
LABEL='전래동화 비경 5시간'

def visible(message,*args):
    text=message%args if args else message
    LOG.info(text,extra={'gui_message':text,'state_transition':True})

def prepare(adapter,context,inputs):
    """Wake and leave menus through production paths; entry starts from the field only."""
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_special_contexts import NAMES
    from owner_startup_stage import scene,DUNGEON,EXIT,MENU
    from owner_start_menu import normalize
    context.checkpoint()
    adapter.exit_sleep_mode(context,inputs)
    service=TownServices(adapter,context,inputs,list(dict.fromkeys([DUNGEON,EXIT,MENU,'버튼_나가기',*AUTO_NAMES,*NAMES])))
    normalize(service)
    kinds=[]
    for index in range(2):
        context.checkpoint();service.check()
        kinds.append(scene(service.detector,service.capture()))
        if index==0:context.wait(.12)
    if kinds[0]!=kinds[1] or kinds[0] not in ('field','inventory'):
        raise RuntimeError('필드에서 눌러 주세요 · 비경·보스 안에서는 새로 입장하지 않습니다')

def execute(adapter,context,inputs):
    """The same call the timetable makes at the appointment, with this one switch on.

    The switch is on for this run only; settings on disk stay as saved.
    """
    from owner_timetable import BY_KEY,invoke
    before=adapter.values
    adapter.values=dict(before,**{KEY:True})
    try:return invoke(adapter,BY_KEY['weekly_dungeon'],context,inputs)
    finally:adapter.values=before

class OneRun:
    """An adapter delegate, owned and closed by the ordinary Session worker."""
    def __init__(self,adapter,ready,events):
        self.adapter,self.ready,self.events=adapter,ready,events
    def __getattr__(self,name):return getattr(self.adapter,name)
    def close(self):return self.adapter.close()
    def run(self,context,inputs):
        try:
            if self.ready is not None:self.ready.wait(context)
            context.checkpoint()
            visible('실전 TEST 시작 · %s · 실제 입장',LABEL)
            prepare(self.adapter,context,inputs)
            result=execute(self.adapter,context,inputs)
            # A native return alone does not prove the hunt ran its full time.
            text='실패 · 실행 로그 확인' if result is False else '처리 종료 · 실행 로그 확인'
            visible('실전 TEST 결과 · %s · %s',LABEL,text)
            self.events.put((text,None))
        except BaseException as exc:
            from biol_base.session import Cancelled
            text='중지됨' if isinstance(exc,Cancelled) else '실패 · '+str(exc)
            visible('실전 TEST 결과 · %s · %s',LABEL,text)
            self.events.put((text,str(exc)))
            raise

def start(gui,result):
    """Shares the reward TEST controller, so only one TEST runs and an update never resumes it as a full macro."""
    from owner_reward_action_test import controller
    from operating_policy import PolicyAdapter
    runner=controller(gui);session=gui.session
    try:
        with session.lock:
            state=session.snapshot()
            busy=getattr(getattr(gui,'input_preparation',None),'busy',lambda:False)()
            closing=getattr(gui,'closed',None)
            if (runner.active or state.get('worker_alive') or state.get('status') in ('running','paused')
                or busy or (closing is not None and closing.is_set())):
                result.set('완전히 중지한 뒤 TEST');return False
            factory=session.adapter_factory
            ready=getattr(gui,'_owner_ocr_readiness',None)
            runner.active=True
            def one_adapter():
                outer=factory()
                if not isinstance(outer,PolicyAdapter):
                    outer.close()
                    raise RuntimeError('기존 실행 정책 연결 확인 필요 · 입력 없음')
                outer.adapter=OneRun(outer.adapter,ready,runner.events)
                return outer
            session.adapter_factory=one_adapter
            try:session.start()
            finally:session.adapter_factory=factory
        result.set('실행 중');gui.root.after(100,lambda:runner.poll(result))
        return True
    except Exception as exc:
        runner.active=False;result.set(str(exc));visible('실전 TEST 준비 실패 · %s',exc);return False
