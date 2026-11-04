"""After an actual exit, repeat the SAME original entry/time-reading path.

No alternate clicks, OCR, input worker, or schedule timer. Zero is accepted
only from the original quota selector, never from an unread HUD countdown.
"""
from functools import wraps
from pathlib import Path
import hashlib,json,logging,math,threading,time

LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
KEYS={'daily':'auto_challenge.secret_exploration','weekly':'auto_challenge.secret_folktale_5h',
      'tale24':'auto_challenge.secret_folktale','daily24':'auto_challenge.secret_exploration_always'}
GOAL_KINDS=frozenset(('tale24','daily24'))
LEAVE_READ_SECONDS=5;LEAVE_READS=3;LEAVE_SETTLE_SECONDS=20
BUSY=('leave','finish','yield_boss','death_recovery','wake_for_exit')
class ReentryPending(RuntimeError):pass
class DungeonLeft(BaseException):
    """The character left while the native loop waits out the whole timer."""

def leave_reader(flow):
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_startup_stage import DUNGEON,EXIT,MENU
    from owner_special_contexts import NAMES
    return TownServices(flow.adapter,flow.context,flow.inputs,list(dict.fromkeys([DUNGEON,EXIT,MENU,*AUTO_NAMES,*NAMES])))

def watching(flow):
    """Whether a plain field right now can only mean the character was removed."""
    entered=getattr(flow,'_owner_entered_at',None)
    return (entered is not None and time.monotonic()-entered>=LEAVE_SETTLE_SECONDS
            and not getattr(flow,'_owner_native_busy',0) and not getattr(flow,'death_resupply_pending',False)
            and not getattr(flow.context,'input_depth',0))

def watch_leaving(flow,call):
    """Read only, through the native sleeps. Sends no input of its own."""
    from owner_startup_stage import scene
    context=flow.context;original=context.wait;fields=[0];last=[time.monotonic()];reader=[None]
    def tick(seconds):
        end=time.monotonic()+max(0,seconds)
        while True:
            original(min(1,max(0,end-time.monotonic())))
            if watching(flow):
                if time.monotonic()-last[0]>=LEAVE_READ_SECONDS:
                    last[0]=time.monotonic()
                    if reader[0] is None:reader[0]=leave_reader(flow)
                    fields[0]=fields[0]+1 if scene(reader[0].detector,reader[0].capture())=='field' else 0
                    if fields[0]>=LEAVE_READS:raise DungeonLeft()
            else:fields[0]=0
            if time.monotonic()>=end:break
    try:context.wait=tick
    except (AttributeError,TypeError):
        LOG.warning('비경 이탈 감시 연결 실패 · 시간 종료 시에만 확인');return call()
    try:return call()
    finally:context.wait=original

def wrap_busy(original):
    @wraps(original)
    def busy(flow,*args,**kwargs):
        flow._owner_native_busy=getattr(flow,'_owner_native_busy',0)+1
        try:return original(flow,*args,**kwargs)
        finally:flow._owner_native_busy-=1
    busy._owner_dungeon_reentry_busy=True
    return busy

def kind_of(flow):
    from project_adapter.secret_folktale import Daily24Exploration,FolktaleExploration
    if isinstance(flow,Daily24Exploration):return 'daily24'
    if isinstance(flow,FolktaleExploration):return 'weekly' if flow.kind=='5h' else 'tale24'
    return 'daily'

def fingerprint(adapter,kind):
    prefix=KEYS[kind]+'.'
    values={k:v for k,v in adapter.values.items() if k.startswith(prefix) and k!=prefix+'enabled'}
    return hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=True).encode()).hexdigest()

def current_period(kind):
    from owner_timetable import now,period,BY_KEY
    return period(BY_KEY['weekly_dungeon' if kind=='weekly' else 'daily_dungeon'],now())

def save_record(adapter,kind,state,*,budget=None):
    from owner_timetable import identity,read,save,now
    path=adapter.project.root/'settings/owner-dungeon-entry.json'
    data=read(path,{'version':1,'characters':{}})
    if data.get('version')!=1:raise ReentryPending('비경 입장 기억 형식 확인 필요')
    record={'kind':kind,'state':state,'period':current_period(kind),'settings':fingerprint(adapter,kind),
            'budget':budget,'updated_at':now().isoformat()}
    data.setdefault('characters',{})[identity(adapter.project.root)]=record;save(path,data)
    adapter._owner_dungeon_entry_record=record
    return record

def valid_record(adapter):
    from owner_timetable import identity,read
    path=adapter.project.root/'settings/owner-dungeon-entry.json'
    record=read(path,{}).get('characters',{}).get(identity(adapter.project.root))
    if not isinstance(record,dict) or record.get('kind') not in KEYS:return None
    kind=record['kind']
    if record.get('period')!=current_period(kind) or record.get('settings')!=fingerprint(adapter,kind):return None
    return record

class ResumeGoal:
    """A saved 24h-content target keeps counting while resuming its map."""
    def __init__(self,kind,budget):self.kind=kind;self.budget=float(budget);self.at=time.monotonic();self.done=False;self.handed_off=False;self.leave_requested=False;self.leave_at=None
    def left(self):return max(0.,self.budget-(time.monotonic()-self.at))

def resume_goal(adapter):
    record=valid_record(adapter)
    if not record or record['kind'] not in GOAL_KINDS or record.get('state')=='goal_complete':return None
    budget=record.get('budget')
    if type(budget) not in (int,float) or not math.isfinite(budget) or not 0<=budget<=86400:
        raise ReentryPending('24시간 비경 이어가기 목표 시간 기록 확인 필요')
    return ResumeGoal(record['kind'],budget)

def request_goal_leave(adapter,context,inputs,goal):
    check_owner(adapter,context,goal.kind)
    # Existing native exit only, from a currently proved dungeon map. Never
    # invokes entry/select, and is called once per resumed target completion.
    flow=make_flow(adapter,context,inputs,goal.kind,0);flow.location='inside';goal.leave_at=time.monotonic();flow.leave()
    goal.leave_requested=True

def preserve_resume_goal(adapter,goal):
    if goal is None or goal.done or goal.handed_off:return
    save_record(adapter,goal.kind,'inside',budget=goal.left())

def check_owner(adapter,context,kind):
    context.checkpoint()
    from owner_timetable import character_mismatch
    if character_mismatch(adapter):raise ReentryPending('비경 재확인 보류 · 캐릭터 불일치')
    if adapter.values.get(KEYS[kind]+'.enabled') is not True:
        raise ReentryPending('비경 재확인 보류 · 해당 비경 사용 해제됨')

def field_ready(adapter,context,inputs):
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_startup_stage import scene,DUNGEON,EXIT,MENU
    from owner_special_contexts import NAMES
    context.checkpoint();adapter.exit_sleep_mode(context,inputs)
    service=TownServices(adapter,context,inputs,list(dict.fromkeys([DUNGEON,EXIT,MENU,*AUTO_NAMES,*NAMES])))
    for index in range(3):
        context.checkpoint();service.check()
        if scene(service.detector,service.capture())!='field':return False
        if index<2:context.wait(.15)
    return True

def remaining_goal(flow):
    value=flow.remaining()
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=86400:
        raise ReentryPending('24시간 비경 남은 목표 시간 확인 필요')
    return float(value)

def make_flow(adapter,context,inputs,kind,budget=None):
    from project_adapter.secret_exploration import Exploration
    from project_adapter.secret_folktale import FolktaleExploration,Daily24Exploration
    if kind=='daily':flow=Exploration(adapter,context,inputs)
    elif kind=='weekly':flow=FolktaleExploration(adapter,context,inputs,'5h')
    elif kind=='tale24':flow=FolktaleExploration(adapter,context,inputs,'24h')
    else:flow=Daily24Exploration(adapter,context,inputs)
    if budget is not None:flow._owner_goal_budget=float(budget)
    return flow

def completed(adapter,kind,state):
    """A real native zero/goal result may finish only its own occurrence."""
    adapter._owner_dungeon_cycle_outcome={'state':state,'kind':kind}
    from owner_timetable import planner,LOCAL as timetable,now
    key={'daily':'daily_dungeon','weekly':'weekly_dungeon','daily24':'daily24_dungeon'}.get(kind)
    if key is None or getattr(timetable,'job',None)==key:return
    plan=planner(adapter)
    if key not in plan.state:return
    plan.finish(key,True,unverified=False)
    if state=='exhausted':plan.recheck_dungeon(key,True,now())

def wrap_select(original):
    @wraps(original)
    def select(flow,*args,**kwargs):
        kind=kind_of(flow)
        class NativeZero(logging.Handler):
            def __init__(self):super().__init__();self.thread=threading.get_ident();self.seen=False
            def emit(self,record):
                if record.thread==self.thread and '전래동화-5시간' in record.getMessage() and '남은 기본시간 00:00:00' in record.getMessage():self.seen=True
        observed=NativeZero();logger=getattr(flow,'log',LOG);logger.addHandler(observed)
        try:result=original(flow,*args,**kwargs)
        finally:logger.removeHandler(observed)
        if kind in GOAL_KINDS:
            budget=getattr(flow,'_owner_goal_budget',None)
            if budget is not None and flow.total is not None:flow.total=min(float(flow.total),budget)
        elif (kwargs.get('read_time',args[0] if args else False) is True
              and ((type(flow.total) in (int,float) and flow.total==0) or (kind=='weekly' and observed.seen))):
            # Native regular exploration already sums base+additional time.
            # A zero base read alone is NEVER sufficient for this marker.
            flow._owner_quota_zero=True
        return result
    select._owner_dungeon_reentry_select=True
    return select

def wrap_enter(original):
    @wraps(original)
    def enter(flow,*args,**kwargs):
        result=original(flow,*args,**kwargs)
        if result is True:
            flow._owner_entry_seen=True;flow._owner_entered_at=time.monotonic()
            save_record(flow.adapter,kind_of(flow),'inside',budget=remaining_goal(flow) if kind_of(flow) in GOAL_KINDS else None)
        return result
    enter._owner_dungeon_reentry_enter=True
    return enter

def wrap_run(original):
    @wraps(original)
    def run(flow):
        if getattr(LOCAL,'active',False):return original(flow)
        LOCAL.active=True;current=flow;recent=[];flow.adapter._owner_dungeon_cycle_outcome=None
        try:
            while True:
                adapter,context,inputs=current.adapter,current.context,current.inputs
                kind=kind_of(current);check_owner(adapter,context,kind)
                if kind in GOAL_KINDS and getattr(current,'_owner_goal_budget',None)==0:
                    save_record(adapter,kind,'goal_complete',budget=0);completed(adapter,kind,'goal_complete')
                    return True
                try:result=watch_leaving(current,lambda:original(current))
                except DungeonLeft:LOG.info('비경 이탈 감지 · 맵 이름 없음·일반 필드 %d회 확인 · %s',LEAVE_READS,kind)
                except BaseException:
                    # Stop/Pause/errors never trigger an extra input or erase
                    # the last successfully entered character-scoped record.
                    if kind in GOAL_KINDS and getattr(current,'_owner_entry_seen',False):
                        try:save_record(adapter,kind,'inside',budget=remaining_goal(current))
                        except (OSError,ValueError,RuntimeError):LOG.warning('비경 중단 시 남은 목표 기록 확인 필요')
                    raise
                context.checkpoint()
                if getattr(current,'_owner_quota_zero',False):
                    save_record(adapter,kind,'exhausted')
                    completed(adapter,kind,'exhausted')
                    LOG.info('비경 잔여시간 소진 확인 · %s · 원본 입장 시간 0초',kind)
                    return True
                if not getattr(current,'_owner_entry_seen',False):
                    save_record(adapter,kind,'time_unverified')
                    raise ReentryPending('비경 입장 시간 미확인 · 완료하지 않고 중단 · 원본 입장 경로 확인 필요')
                budget=remaining_goal(current) if kind in GOAL_KINDS else None
                if budget is not None and budget<=0:
                    save_record(adapter,kind,'goal_complete',budget=0)
                    completed(adapter,kind,'goal_complete')
                    LOG.info('24시간 비경 설정 시간 완료 · 재입장 없음 · %s',kind)
                    return True
                save_record(adapter,kind,'exit_pending',budget=budget)
                if not field_ready(adapter,context,inputs):
                    raise ReentryPending('비경 이탈 후 기본 화면 확인 필요 · 재입장 입력 보류')
                check_owner(adapter,context,kind)
                at=time.monotonic();recent=[v for v in recent if at-v<60];recent.append(at)
                if len(recent)>3:raise ReentryPending('비경 이탈·재입장 1분 내 반복 · 진단 확인 필요')
                LOG.info('비경 이탈 확인 · 즉시 같은 원본 입장 경로로 시간 재확인 · %s',kind)
                current=make_flow(adapter,context,inputs,kind,budget)
        finally:LOCAL.active=False
    run._owner_dungeon_reentry_run=True
    return run

def after_exit(adapter,context,inputs):
    """A resumed-in-progress dungeon exited: identify the same original entry."""
    context.checkpoint();record=valid_record(adapter)
    if record and record.get('state')=='goal_complete' and record['kind'] in GOAL_KINDS:
        return
    if record:kind=record['kind'];budget=record.get('budget')
    else:
        choices=[k for k,prefix in KEYS.items() if adapter.values.get(prefix+'.enabled') is True]
        if len(choices)!=1:
            raise ReentryPending('비경 이탈 시간 확인 필요 · 기존 입장 종류 미확인 · 임의 비경 선택 없음')
        kind=choices[0];budget=None
        if kind in GOAL_KINDS:raise ReentryPending('24시간 비경 남은 목표 기록 필요 · 임의 시간 초기화 없음')
    check_owner(adapter,context,kind)
    if not field_ready(adapter,context,inputs):raise ReentryPending('비경 이탈 기본 화면 재확인 필요')
    LOG.info('비경 이탈 확인 · 즉시 같은 원본 입장 경로로 시간 재확인 · %s',kind)
    return make_flow(adapter,context,inputs,kind,budget).run()

def install():
    from project_adapter.secret_exploration import Exploration
    from project_adapter.secret_folktale import FolktaleExploration,Daily24Exploration
    # Capture inherited originals before replacing the base class; otherwise a
    # child would receive a wrapper around a wrapper and duplicate the cycle.
    classes=(Exploration,FolktaleExploration,Daily24Exploration)
    originals={(cls,name):getattr(cls,name) for cls in classes for name in ('select','enter','run',*BUSY)}
    for cls in classes:
        for name,wrapper in (('select',wrap_select),('enter',wrap_enter),('run',wrap_run)):
            old=originals[cls,name]
            if not getattr(old,'_owner_dungeon_reentry_'+name,False):setattr(cls,name,wrapper(old))
        for name in BUSY:
            old=originals[cls,name]
            if not getattr(old,'_owner_dungeon_reentry_busy',False):setattr(cls,name,wrap_busy(old))
