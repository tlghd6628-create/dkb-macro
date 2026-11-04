"""Quest-only progress watchdog. No input or second action worker.

Stable quest tracker AND no world/minimap activity are required for recovery.
Ongoing combat/travel with unchanged quest produces evidence only, not clicks.
"""
from collections import deque
from functools import wraps
import json,logging,re,sys,threading,time
LOCAL=threading.local();LOG=logging.getLogger('project_gui.DKB')
EXEMPT={'boss','death','boss_timeout','tutorial','loading','cutscene','movie'}


def patches(frame):
    import cv2
    return tuple(cv2.resize(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_RGB2GRAY),(48,24))
                 for x,y,w,h in ((732,49,155,194),(170,180,530,180),(5,30,94,70)))


def different(a,b):
    import numpy as np
    delta=np.abs(a.astype('int16')-b.astype('int16'))
    return float(delta.mean())>4 or float((delta>30).mean())>.035


class Watch:
    def __init__(self):
        self.previous=None;self.mode=None;self.last=None;self.quest_at=None;self.activity_at=None
        self.next_sample=0.;self.suspected=None;self.next_notice=0.;self.recoveries=deque()
    def reset(self,now):
        self.previous=None;self.last=None;self.quest_at=now;self.activity_at=now;self.suspected=None;self.next_sample=0.
    def observe(self,frame,mode,selected,now,blocked=False):
        if blocked or mode not in ('main_quest','sub_quest') or selected in EXEMPT:
            self.reset(now);return None
        if getattr(frame,'shape',None)!=(479,897,3):self.reset(now);return None
        if self.mode!=mode or (self.last is not None and now-self.last>10):self.reset(now)
        self.mode=mode
        if now<self.next_sample:return None
        self.next_sample=now+2;self.last=now;current=patches(frame)
        if self.previous is None:
            self.quest_at=self.activity_at=now
        else:
            if different(current[0],self.previous[0]):self.quest_at=now;self.suspected=None
            if any(different(a,b) for a,b in zip(current[1:],self.previous[1:])):
                self.activity_at=now;self.suspected=None
        self.previous=current
        quest_age=now-self.quest_at;idle_age=now-self.activity_at
        limit=300 if selected=='auto_move' else 180
        data={'mode':mode,'selected':selected,'quest_unchanged_seconds':round(quest_age,1),
              'no_visual_activity_seconds':round(idle_age,1),'idle_limit_seconds':limit}
        if quest_age>=limit and idle_age>=limit:
            if self.suspected is None:
                self.suspected=now;return dict(data,event='suspected')
            if now-self.suspected>=10:return dict(data,event='recover')
        elif quest_age>=600 and now>=self.next_notice:
            self.next_notice=now+600
            return dict(data,event='long_activity_without_tracker_change')
        return None
    def allow_recovery(self,now):
        while self.recoveries and now-self.recoveries[0]>=900:self.recoveries.popleft()
        if len(self.recoveries)>=2:return False
        self.recoveries.append(now);self.reset(now);return True


class QuestStalled(BaseException):pass


def record(gui,adapter,context,frame,data):
    from owner_scene_archive import unknown_observed
    unknown_observed(gui,adapter,context,frame,'quest_watchdog_'+data['event'])
    snapshot=dict(data,observed_at=time.strftime('%Y-%m-%dT%H:%M:%S'),cause_confirmed=False)
    gui._owner_watchdog_snapshot=snapshot
    try:
        path=adapter.project.root/'settings/owner-quest-watchdog.json';temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    except OSError:LOG.warning('퀘스트 감시 기록 저장 실패')
    if data['event']=='long_activity_without_tracker_change':
        LOG.warning('퀘스트 감시 · 진행 표시 10분간 동일 · 전투·이동 흔적이 있어 입력 복구 없이 화면 기록')
    elif data['event']=='suspected':
        LOG.warning('퀘스트 감시 · 정체 의심 · 진행·활동 변화 %s초 없음 · 10초 추가 관측',data['no_visual_activity_seconds'])
    else:LOG.warning('퀘스트 감시 · 정체 재확인 · 현재 퀘스트 처리기를 새로 구성합니다 · %s',data['selected'])


class StateLog(logging.Handler):
    def emit(self,record):
        owner=getattr(LOCAL,'owner',None)
        if owner is None:return
        match=re.search(r'퀘스트 상태판정: mode=(\w+) selected=([^\s]+)',record.getMessage())
        if match:LOCAL.selected=(match[1],match[2],time.monotonic())


def install(gui):
    if getattr(gui,'_owner_quest_watchdog',False):return
    from project_adapter._entry import Adapter
    import runtime_capture
    original_capture=runtime_capture.capture
    @wraps(original_capture)
    def capture(*a,**k):
        frame=original_capture(*a,**k);owner=getattr(LOCAL,'owner',None)
        if owner is None:return frame
        adapter,context,inputs,watch=owner
        from owner_task_flow import LOCAL as task
        selected=getattr(LOCAL,'selected',None);now=time.monotonic()
        # Missing/stale state classifications do not authorize a restart.
        state=selected[1] if selected and selected[0]==adapter.mode and now-selected[2]<10 else None
        if context.input_depth or getattr(inputs,'held',()):return frame
        blocked=(context.stop.is_set() or context.pause.is_set()
                 or getattr(task,'servicing',False) or state is None)
        event=watch.observe(frame,adapter.mode,state,now,blocked=blocked)
        if event:
            record(gui,adapter,context,frame,event)
            if event['event']=='recover':raise QuestStalled()
        return frame
    runtime_capture.capture=capture
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                if value is original_capture:setattr(module,key,capture)
    original_quest=Adapter.run_main_quest
    @wraps(original_quest)
    def quest(adapter,context,inputs):
        if getattr(LOCAL,'owner',None):return original_quest(adapter,context,inputs)
        watch=getattr(adapter,'_owner_quest_watch',None)
        if watch is None or getattr(adapter,'_owner_watch_context',None) is not context:
            watch=Watch();adapter._owner_quest_watch=watch;adapter._owner_watch_context=context
        LOCAL.owner=(adapter,context,inputs,watch);LOCAL.selected=None
        try:
            while True:
                context.checkpoint()
                try:return original_quest(adapter,context,inputs)
                except QuestStalled:
                    context.checkpoint()
                    if not watch.allow_recovery(time.monotonic()):
                        raise RuntimeError('퀘스트 감시 복구가 15분 안에 2회 반복되어 자동 중지합니다. 진단 확인이 필요합니다.')
                    # Prior handlers have unwound through their own finally
                    # blocks. Rebuild only the quest runner, no login/bootstrap,
                    # quest-mode change, guessed button or new input thread.
                    LOCAL.selected=None;context.wait(1);context.checkpoint()
                    LOG.info('퀘스트 감시 · 기존 모드 유지 · 새 화면으로 진행 재확인 · 복구 %d/2',len(watch.recoveries))
        finally:LOCAL.owner=None;LOCAL.selected=None
    Adapter.run_main_quest=quest
    handler=StateLog();gui.logger.addHandler(handler)
    gui.root.bind('<Destroy>',lambda event:gui.logger.removeHandler(handler) if event.widget is gui.root else None,add='+')
    gui._owner_quest_watchdog=True
    LOG.info('퀘스트 감시 준비 완료 · 메인·서사만 감시 · 일반 180초/이동 300초+10초 재확인 · 15분 내 복구 2회 제한')
