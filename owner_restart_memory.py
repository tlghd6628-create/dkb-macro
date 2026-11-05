"""Cold-start chore filtering and durable native training appointments.

Only local automation state is read; no game capture or input worker is added.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from functools import wraps
import hashlib,json,logging,math,sqlite3,time
from owner_timetable import identity,read,save,planner,BY_KEY,enabled,period,now

LOG=logging.getLogger('project_gui.DKB')
TIMERS={
 'clan':('_clan_cooperative_next','auto_growth.clan_cooperative_training.enabled',5*3600),
}

def profile(adapter,key):
    fields=('auto_growth.spirit_training.interval_minutes',) if key=='spirit' else ('auto_growth.clan_cooperative_training.lamp',)
    return hashlib.sha256(json.dumps({f:adapter.values.get(f,10 if key=='spirit' else '산군석등') for f in fields},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

class TimerBook:
    def __init__(self,adapter,wall=time.time,mono=time.monotonic):
        self.adapter=adapter;self.identity=identity(adapter.project.root);self.wall=wall;self.mono=mono
        self.path=Path(adapter.project.root)/'settings/owner-restart-timers.json';self.seen={}
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict):raise ValueError('수련 예약 저장 형식 확인 필요')
        else:self.data={'version':1,'characters':{}}
        self.entries=self.data['characters'].setdefault(self.identity,{})
        if not isinstance(self.entries,dict):raise ValueError('캐릭터별 수련 예약 형식 확인 필요')

    def restore(self,context):
        restored=[]
        for key,(attr,setting,limit) in TIMERS.items():
            value=self.entries.get(key,{})
            if not isinstance(value,dict):continue
            if not self.adapter.values.get(setting) or value.get('profile')!=profile(self.adapter,key):continue
            at=value.get('at')
            if not isinstance(at,(int,float)) or not math.isfinite(at):continue
            remaining=at-self.wall()
            if not 0<remaining<=limit:continue
            deadline=self.mono()+remaining;setattr(self.adapter,attr,(context,deadline))
            if key=='clan' and isinstance(value.get('native_profile'),str):self.adapter._clan_cooperative_profile=value['native_profile']
            self.seen[key]=(context,deadline,profile(self.adapter,key))
            restored.append(key)
            LOG.info('수련 예약 복원 · %s · 다음 %s',key,datetime.fromtimestamp(at,timezone(timedelta(hours=9))).strftime('%m/%d %H:%M:%S'))
        return restored

    def capture(self,context):
        changed=False;pending={};seen={}
        for key,(attr,setting,limit) in TIMERS.items():
            value=getattr(self.adapter,attr,None)
            if not isinstance(value,tuple) or len(value)!=2 or value[0] is not context:continue
            deadline=value[1]
            if not isinstance(deadline,(int,float)) or not math.isfinite(deadline):continue
            signature=(context,deadline,profile(self.adapter,key))
            if self.seen.get(key)==signature:continue
            remaining=deadline-self.mono()
            if not 0<remaining<=limit:continue
            entry={'at':self.wall()+remaining,'profile':signature[2],'recorded_at':self.wall(),'source':'native timer'}
            if key=='clan' and isinstance(getattr(self.adapter,'_clan_cooperative_profile',None),str):entry['native_profile']=self.adapter._clan_cooperative_profile
            pending[key]=entry;seen[key]=signature;changed=True
        if changed:
            # Commit before accepting the new in-memory signature. Failed
            # writes remain retryable and never masquerade as a saved timer.
            candidate=json.loads(json.dumps(self.data));candidate['characters'][self.identity].update(pending)
            save(self.path,candidate);self.data=candidate;self.entries=candidate['characters'][self.identity];self.seen.update(seen)
        return changed

    def import_clan_receipt(self):
        """One-time upgrade from an explicit live receipt, never an ETA guess."""
        if 'clan' in self.entries:return False
        path=Path(self.adapter.project.root)/'settings/owner-schedule.sqlite3'
        if not path.exists():return False
        try:
            db=sqlite3.connect('file:'+str(path).replace('\\','/')+'?mode=ro',uri=True,timeout=.2)
            try:row=db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(self.identity,'clan_training',period_day())).fetchone()
            finally:db.close()
            state=json.loads(row[0]) if row else {};at=datetime.fromisoformat(state['planned_at']).timestamp()
            lamp=str(self.adapter.values.get('auto_growth.clan_cooperative_training.lamp','산군석등'))
            evidence=' '.join(h.get('note','') for h in state.get('history',[]) if h.get('source')=='실행 로그')
            if state.get('source')!='실행 로그' or lamp not in evidence or not 0<at-self.wall()<=5*3600:return False
        except (OSError,ValueError,KeyError,sqlite3.Error):return False
        if self.adapter.mode=='custom_mode':return False
        self.entries['clan']={'at':at,'profile':profile(self.adapter,'clan'),'native_profile':'','recorded_at':self.wall(),'source':'explicit live schedule receipt'}
        save(self.path,self.data);return True

def period_day():
    return (now()-timedelta(hours=5)).date().isoformat()

def suppress_flags(adapter,context,at=None,mono=time.monotonic):
    """Hide processed flags before native menus/logs. Never edit saved settings."""
    from owner_timetable import LOCAL
    if getattr(LOCAL,'job',None) or getattr(LOCAL,'native_job',None) or getattr(adapter,'_owner_preparing_gears',False):return set()
    plan=planner(adapter);at=at or now();result=set()
    for key,job in BY_KEY.items():
        item=plan.state.get(key,{})
        if not enabled(job,adapter.values) or item.get('period')!=period(job,at):continue
        if item.get('status') not in ('processed','confirmed') and not (job.once and item.get('status')=='held'):continue
        if adapter.mode in ('main_quest','sub_quest') and (key=='gear' or (key in ('mail','inventory') and getattr(adapter,'_owner_initial_context',None) is None)):continue
        result.add(job.setting)
        if key=='gear':result.add('auto_growth.blessing.enabled')
    for key,(attr,setting,_) in TIMERS.items():
        value=getattr(adapter,attr,None)
        if isinstance(value,tuple) and len(value)==2 and value[0] is context and isinstance(value[1],(int,float)) and math.isfinite(value[1]) and value[1]>mono():result.add(setting)
    return result

def install(gui):
    if getattr(gui,'_owner_restart_memory',False):return
    from project_adapter._entry import Adapter
    ordinary_run=Adapter.run;ordinary_features=Adapter._run_auto_features;ordinary_wait=Adapter._wait_for_spirit_training
    @wraps(ordinary_run)
    def run(adapter,context,inputs):
        try:
            book=TimerBook(adapter);adapter._owner_restart_book=book;book.import_clan_receipt();book.restore(context)
        except (OSError,ValueError,TypeError):
            LOG.warning('수련 예약 복원 실패 · 기존 파일 보존 · 원래 기능으로 진행 · 진단 확인 필요')
            return ordinary_run(adapter,context,inputs)
        wait=context.wait
        retry_at=0.
        def remembered_wait(seconds):
            nonlocal retry_at
            if time.monotonic()>=retry_at:
                try:book.capture(context)
                except (OSError,ValueError):
                    retry_at=time.monotonic()+30;LOG.warning('수련 예약 저장 실패 · 기존 기록 보존 · 30초 후 재확인')
            return wait(seconds)
        context.wait=remembered_wait
        try:return ordinary_run(adapter,context,inputs)
        finally:
            context.wait=wait
            try:book.capture(context)
            except (OSError,ValueError):LOG.warning('수련 예약 저장 실패 · 다음 실행 전 진단 확인 필요')
    @wraps(ordinary_features)
    def features(adapter,context,inputs,**kwargs):
        old=adapter.values;flags=suppress_flags(adapter,context)
        if not flags:return ordinary_features(adapter,context,inputs,**kwargs)
        signature=tuple(sorted(flags))
        if getattr(adapter,'_owner_skip_signature',None)!=signature:
            LOG.info('저장한 숙제·수련 예약 적용 · 재실행 제외 %d개 설정 · 초기화/예약 시각 유지',len(flags));adapter._owner_skip_signature=signature
        previous=getattr(adapter,'_owner_memory_full_values',None)
        adapter._owner_memory_full_values=old;adapter.values=dict(old,**{key:False for key in flags})
        try:return ordinary_features(adapter,context,inputs,**kwargs)
        finally:
            adapter.values=old
            if previous is None:del adapter._owner_memory_full_values
            else:adapter._owner_memory_full_values=previous
    @wraps(ordinary_wait)
    def waiting(adapter,context,inputs):
        old=adapter.values;adapter.values=getattr(adapter,'_owner_memory_full_values',old)
        try:return ordinary_wait(adapter,context,inputs)
        finally:adapter.values=old
    Adapter.run=run;Adapter._run_auto_features=features;Adapter._wait_for_spirit_training=waiting
    gui._owner_restart_memory=True
    LOG.info('재시작 기억 준비 · 저장한 숙제 선제 제외 · 문파 수련 예약 보존 · 영기는 기존 일일 횟수 기록 사용')
