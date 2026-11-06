"""Three-hour character-scoped reward/cleanup cadence on the sole input worker."""
import copy,json,logging,threading,time
from pathlib import Path
from functools import wraps
from owner_reward_context import JOBS,LABELS,DUNGEONS,admit

INTERVAL=3*60*60
RECHECK=30*60;RECHECK_LIMIT=2
RECHECK_STATES=('partial','failed','failed_or_unconfirmed')
LOCAL=threading.local()
LOG=logging.getLogger('project_gui.DKB')

def visible(text):LOG.info(text,extra={'gui_message':text,'state_transition':True})


class Ledger:
    def __init__(self,root,identity):
        self.path=Path(root)/'settings/owner-reward-cycle.json';self.identity=identity
        try:self.data=json.loads(self.path.read_text(encoding='utf-8-sig'))
        except FileNotFoundError:self.data={'version':1,'characters':{}}
        if not isinstance(self.data,dict) or self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict):raise ValueError('보상·정리 실행 기록 확인 필요')
        self.rows=self.data['characters'].setdefault(identity,{})
        if not isinstance(self.rows,dict):raise ValueError('캐릭터 보상·정리 기록 확인 필요')
    def due(self,key,at):
        row=self.rows.get(key)
        if row is None:return True
        if not isinstance(row,dict) or type(row.get('at')) not in (int,float):raise ValueError('보상·정리 실행 시각 확인 필요')
        # An unconfirmed run gets a bounded early look so a reward is not lost for
        # three hours, without becoming an endless retry.
        early=row.get('state') in RECHECK_STATES and row.get('rechecks',0)<RECHECK_LIMIT
        return at-row['at']>=(RECHECK if early else INTERVAL)
    def record(self,key,state,at):
        from owner_timetable import save
        row={'at':at,'state':state}
        previous=self.rows.get(key)
        if isinstance(previous,dict):
            if state=='running':
                # The final record of this same run reads what came before it.
                row['last_state']=previous.get('state');row['rechecks']=previous.get('rechecks',0)
            elif state in RECHECK_STATES and previous.get('last_state') in RECHECK_STATES:
                row['rechecks']=previous.get('rechecks',0)+1
        self.rows[key]=row
        save(self.path,self.data)


def ledger(adapter):
    from owner_hunt_rules_candidate import configured_identity
    identity=configured_identity(adapter.project.root)
    if not identity or not identity.strip(' /|'):raise ValueError('서버·캐릭터 설정 확인 필요')
    existing=getattr(adapter,'_owner_reward_cycle_ledger',None)
    if existing is None or existing.identity!=identity:
        existing=Ledger(adapter.project.root,identity);adapter._owner_reward_cycle_ledger=existing
    return existing


def wrap(original,key):
    @wraps(original)
    def run(adapter,context,inputs,*args,**kwargs):
        if adapter.values.get(key) is not True:return True
        context.checkpoint()
        manual=getattr(LOCAL,'manual',False)
        book=None
        if not manual:
            from owner_character_binding import mismatch
            if mismatch(adapter):return True
            try:
                book=ledger(adapter)
                if not book.due(key,time.time()):return True
            except (OSError,ValueError) as exc:LOG.info('보상·정리 보류 · %s',exc);return True
        previous=getattr(LOCAL,'running',False);LOCAL.running=True
        try:observation=admit(adapter,context,inputs)
        finally:LOCAL.running=previous
        if not observation['allowed']:
            adapter._owner_reward_cycle_hold=observation['reason']
            if getattr(adapter,'_owner_reward_cycle_last_hold',None)!=observation['reason']:
                LOG.info('보상·정리 보류 · %s',observation['reason']);adapter._owner_reward_cycle_last_hold=observation['reason']
            return True
        adapter._owner_reward_cycle_hold=None
        prior=copy.deepcopy(book.rows.get(key)) if book is not None else None
        if book is not None:book.record(key,'running',time.time())
        previous=getattr(LOCAL,'running',False);LOCAL.running=True
        result=None;adapter._owner_reward_last_outcome=None
        try:
            from owner_reward_flow import owning
            with owning(adapter):result=original(adapter,context,inputs,*args,**kwargs)
            return result
        finally:
            LOCAL.running=previous
            if book is not None:
                try:
                    if getattr(adapter,'_owner_reward_cycle_hold',None):
                        if prior is None:book.rows.pop(key,None)
                        else:book.rows[key]=prior
                        from owner_timetable import save
                        save(book.path,book.data)
                    else:
                        outcome=getattr(adapter,'_owner_reward_last_outcome',None)
                        book.record(key,outcome or ('failed_or_unconfirmed' if result is False or result is None else 'processed_unverified'),time.time())
                except OSError:LOG.exception('보상·정리 결과 기록 실패 · 기존 running 기록 보존')
    run._owner_reward_cycle=True
    return run


def tick(adapter,context,inputs):
    if getattr(LOCAL,'running',False) or getattr(context,'input_depth',0) or getattr(inputs,'held',()):return False
    context.checkpoint()
    if time.monotonic()<getattr(adapter,'_owner_reward_cycle_recheck',0):return False
    from owner_task_flow import LOCAL as task
    from owner_schedule_priority import LOCAL as priority,reservation_hold
    from owner_timetable import LOCAL as timetable
    if getattr(task,'servicing',False):return False
    feature=getattr(priority,'feature',None);combat=getattr(priority,'combat',None)
    if (feature and feature not in DUNGEONS) or (combat and combat not in DUNGEONS):return False
    # A scheduled dungeon holds its job for hours; rewards still run inside it.
    dungeon=(None,'daily_dungeon','weekly_dungeon','daily24_dungeon')
    if getattr(timetable,'job',None) not in dungeon or getattr(timetable,'native_job',None) not in dungeon:return False
    from owner_reward_action_test import TARGETS,PATHS,execute,prepare
    from owner_job_timing import long_ok,LONG_REWARDS
    long=long_ok(adapter)
    selected=[key for key in TARGETS if PATHS[key] is not None and adapter.values.get(key) is True and (long or key not in LONG_REWARDS)]
    if not selected:return False
    if reservation_hold(adapter.project.root,adapter.values):return False
    try:book=ledger(adapter);selected=[key for key in selected if book.due(key,time.time())]
    except (OSError,ValueError) as exc:LOG.info('보상·정리 보류 · %s',exc);return False
    if not selected:return False
    # Use the existing quest's safe field reader before opening an unrelated
    # menu. Dungeon ownership permits these jobs without leaving the instance.
    ui=getattr(adapter,'_owner_mission_ui',None)
    if ui is None and combat not in DUNGEONS and getattr(adapter,'_owner_initial_context',None) is not context:return False
    if combat not in DUNGEONS and ui is not None and not ui.normal_frame(ui.frame()):return False
    key=selected[0];previous=getattr(LOCAL,'running',False);LOCAL.running=True
    try:
        adapter.exit_sleep_mode(context,inputs)
        observation=admit(adapter,context,inputs)
        if not observation['allowed']:
            adapter._owner_reward_cycle_recheck=time.monotonic()+30
            if getattr(adapter,'_owner_reward_cycle_last_hold',None)!=observation['reason']:
                visible('보상·정리 보류 · '+observation['reason']);adapter._owner_reward_cycle_last_hold=observation['reason']
            return False
        adapter._owner_reward_cycle_last_hold=None
        prepare(adapter,context,inputs)
        visible('보상·정리 3시간 주기 시작 · '+TARGETS[key][1])
        before=copy.deepcopy(book.rows.get(key))
        try:execute(adapter,context,inputs,key,manual=False)
        except RuntimeError as exc:
            from biol_base.session import Cancelled
            if isinstance(exc,Cancelled):raise
            # A hold (a boss window at 20:37) stopped the whole program from here; it only waits now.
            LOG.info('보상·정리 보류 · %s · %s',TARGETS[key][1],str(exc)[:120])
            adapter._owner_reward_cycle_recheck=time.monotonic()+60;return False
        if book.rows.get(key)==before:
            # Not run at all (the native step said 미구현): without a record it came back every 7 s (20:36).
            book.record(key,'skipped',time.time())
        return True
    finally:LOCAL.running=previous


def install(gui,aliases=()):
    from project_adapter._entry import Adapter
    from project_adapter import market_inventory
    from owner_reward_action_test import PATHS
    from owner_gear_native_install_candidate import _rebind_aliases
    if not hasattr(Adapter,'run_training_log'):
        from owner_training_log import run as training_log
        Adapter.run_training_log=training_log
    for key,path in PATHS.items():
        if path is None:continue
        target=Adapter if path[0]=='adapter' else market_inventory
        original=getattr(target,path[1])
        if getattr(original,'_owner_reward_cycle',False) is True:continue
        replacement=wrap(original,key);setattr(target,path[1],replacement)
        if target is market_inventory:_rebind_aliases(aliases,original,replacement)
    if getattr(Adapter.run,'_owner_reward_cycle_wait',False):return
    original_run=Adapter.run
    @wraps(original_run)
    def run(adapter,context,inputs):
        original_wait=context.wait;busy=False;last=0.
        def wait(seconds):
            nonlocal busy,last
            end=time.monotonic()+max(0,seconds)
            while True:
                original_wait(min(1,max(0,end-time.monotonic())))
                if not busy and time.monotonic()-last>=5:
                    busy=True;last=time.monotonic()
                    try:tick(adapter,context,inputs)
                    finally:busy=False
                if time.monotonic()>=end:break
        context.wait=wait
        try:return original_run(adapter,context,inputs)
        finally:context.wait=original_wait
    run._owner_reward_cycle_wait=True;Adapter.run=run
