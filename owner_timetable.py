"""Persistent per-character work appointments; game actions stay on owner worker."""
from dataclasses import dataclass
from datetime import datetime,timedelta,time,timezone
from pathlib import Path
from functools import wraps
import hashlib,json,os,secrets,threading,logging,importlib,sqlite3,re,copy
from owner_outcome import classify as classify_outcome,clear as clear_outcome,FINISHED,FAILED,NOT_ATTEMPTED,SENT_UNCONFIRMED
from owner_character_binding import mismatch as character_mismatch
KST=timezone(timedelta(hours=9));LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()

@dataclass(frozen=True)
class Job:
    key:str
    label:str
    setting:str
    clock:str
    minutes:int
    target:str
    week:bool=False
    once:bool=False
    weekday:int=None

# Allocation policy, NOT claims about guaranteed game completion durations.
JOBS=(
 Job('guide','길라잡이','auto_rewards.guide.enabled','05:03',3,'@run_guide_rewards'),
 Job('events','이벤트','auto_rewards.event.enabled','05:07',5,'@run_event_rewards'),
 Job('mail','우편','auto_rewards.mail.enabled','05:14',3,'@run_mail_rewards'),
 Job('daily_missions','일일 임무','auto_schedule.daily_quest.enabled','05:20',10,'mission_quests.run_mission_quests'),
 Job('weekly_missions','주간 임무','auto_schedule.weekly_quest.enabled','23:45',30,'mission_quests.run_mission_quests',True,weekday=1),
 Job('clan_request','문파 보스 신청','auto_schedule.clan_boss_request.enabled','05:35',5,'@run_clan_boss_request'),
 Job('achievement','업적','auto_rewards.achievement.enabled','05:43',5,'@run_achievement_rewards'),
 Job('album','화첩','auto_rewards.album.enabled','05:51',5,'@run_album_rewards'),
 Job('inventory','인벤토리 사용','auto_rewards.inventory_use.enabled','06:00',5,'@run_inventory_use'),
 Job('blessing','가호','auto_rewards.blessing.enabled','06:10',5,'@run_blessing_rewards'),
 Job('gear','성장 장비·가호','auto_growth.equipment.enabled','06:20',10,'achievement_rewards.run_growth_entry'),
 Job('growth','기운 발현','auto_growth.energy.enabled','06:35',5,'achievement_rewards.run_energy_entry'),
 Job('treasure','보물찾기','auto_challenge.treasure_hunt.enabled','06:45',15,'@run_treasure_region_entry',once=True),
 Job('daily_dungeon','비경탐험','auto_challenge.secret_exploration.enabled','07:10',75,'secret_exploration.run_secret_exploration'),
 Job('weekly_dungeon','전래동화 비경','auto_challenge.secret_folktale_5h.enabled','09:00',320,'secret_folktale.run_folktale_exploration',True,weekday=1),
 Job('tower','승천의 탑','auto_challenge.ascension_tower.enabled','15:00',60,'@run_ascension_tower',True,weekday=1),
 Job('training_log','도사 수행록','auto_rewards.training_log.enabled','16:10',5,'#training_log',True,weekday=1),
 Job('raid','보스 레이드','auto_schedule.boss_raid.enabled','17:30',60,'boss_raid.run_boss_raid'),
 Job('daily24_dungeon','비경탐험(일일-24시간)','auto_challenge.secret_exploration_always.enabled','10:30',75,'secret_exploration.run_secret_exploration'),
 Job('shop','잡화상점 구매','owner_shop.enabled','11:45',15,'#shop'),
 Job('shop_weekly_verify','주간 상점 구매 확인','owner_shop.enabled','23:10',15,'#shop',True,weekday=1),
)
BY_KEY={job.key:job for job in JOBS};LABEL_JOB={job.label:job.key for job in JOBS}
# The native dispatcher reads these switches only in auto_mode. In a quest mode
# it would return at once with nothing entered, so they run under that mode.
DUNGEON_JOBS=frozenset(('daily_dungeon','weekly_dungeon','daily24_dungeon'))
# A return from these does not prove the time is used up. Only the native zero
# read does. daily24 stops at its chosen hours with time left on purpose.
RECHECK_JOBS=frozenset(('daily_dungeon','weekly_dungeon'))
# The rest of the jobs that same dispatcher only runs in auto_mode.
AUTO_MODE_JOBS=DUNGEON_JOBS|frozenset(('daily_missions','weekly_missions','clan_request','treasure','tower','raid'))
NO_TIME_LEFT=('비경 이용 시간 0초','비경 잔여시간 소진 확인')
TREASURE_REGION='auto_challenge.treasure_hunt.region'
EXCLUDED_USER_SETTINGS=frozenset(('mail','events'))
CATALOG_JOB={'events':'events','mail':'mail','daily_quest':'daily_missions','weekly_quest':'weekly_missions','daily_dungeon':'daily_dungeon',
 'weekly_dungeon':'weekly_dungeon','raid':'raid','tower':'tower','yosin':'clan_request','defense':'clan_request',
 'album':'album','achievement':'achievement','guide':'guide','inventory':'inventory','blessing':'blessing',
 'gear':'gear','growth':'growth','treasure':'treasure','training_log':'training_log','daily24_dungeon':'daily24_dungeon','daily_shop':'shop','weekly_shop_verify':'shop_weekly_verify'}
LOCK=threading.RLock()
# After the two quick attempts, later cycles in the same reset period.
FAILED_CYCLES=2;FAILED_COOLDOWN_DAY=120;FAILED_COOLDOWN_WEEK=360
DUNGEON_RETRY_FIRST=2;DUNGEON_RETRY_MAX=10

class RunOutcome(logging.Handler):
    def __init__(self,label):super().__init__();self.label=label;self.thread=threading.get_ident();self.failed=False;self.no_time_left=False
    def emit(self,record):
        if record.thread!=self.thread:return
        text=record.getMessage()
        if (any(mark in text for mark in NO_TIME_LEFT)
            or ('전래동화-5시간' in text and '남은 기본시간 00:00:00' in text)):self.no_time_left=True
        if self.label in text and text.startswith(('자동 기능 부분 완료','자동 기능 복구 중')):self.failed=True
        if self.label=='승천의 탑' and '승천 미완료' in text:self.failed=True
        if self.label=='보물찾기' and '보물찾기' in text and any(word in text for word in ('획득 확인 시간 초과','부분 완료','수령 실패')):self.failed=True

def now():return datetime.now(KST)
def parse_at(value):
    # Python3.10 accepts only3/6 fractional digits; other JSON writers may
    # round-trip the same instant with1/2/4/5 digits. Normalize, never guess.
    value=re.sub(r'(T\d{2}:\d{2}:\d{2})\.(\d{1,9})(?=[+-]|Z|$)',lambda m:m[1]+'.'+m[2][:6].ljust(6,'0'),value)
    return datetime.fromisoformat(value.replace('Z','+00:00'))
def read(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return default
def read_required_if_present(path,default):
    path=Path(path)
    if not path.exists():return default
    try:value=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:raise ValueError('시간표 파일 읽기 실패 · 기존 기록 유지') from exc
    if not isinstance(value,dict) or value.get('version')!=1:raise ValueError('시간표 파일 형식 오류 · 기존 기록 유지')
    return value
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    import threading,time as clock
    tmp=path.with_name('%s.%d.tmp'%(path.stem,threading.get_ident()));tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    # Windows refuses the swap while anything has the file open for a moment, and that ended a run (11-05).
    for attempt in range(8):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==7:raise
            clock.sleep(.1*(attempt+1))
def day_at(at):return (at-timedelta(hours=5)).date()
def period(job,at):
    if job.once:return 'all'
    day=day_at(at)
    if job.week:day-=timedelta(days=(day.weekday()-2)%7)
    return day.isoformat()
def identity(root):
    value=read(Path(root)/'settings/manager_identity.json',{})
    return str(value.get('server_name',''))+' / '+str(value.get('character_name',''))

def shop_selection_enabled(root):
    """Read configured profile's explicit shop choices; never invent one."""
    from owner_shop_runtime_candidate import configured_identity
    from owner_shop_settings_candidate import ShopSettingsStore
    try:
        store=ShopSettingsStore(root,configured_identity(root))
        if not store.path.exists():return False
        doc=store.read_document()
        return doc.get('enabled',True) is True and any(row.get('enabled') is True for row in doc['items'])
    except (OSError,ValueError,TypeError,RuntimeError):
        return False

def treasure_confirmed(root):
    path=Path(root)/'settings/owner-schedule.sqlite3'
    if not path.exists():return False
    try:
        db=sqlite3.connect('file:'+str(path).replace('\\','/')+'?mode=ro',uri=True,timeout=.2)
        try:row=db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity(root),'treasure','all')).fetchone()
        finally:db.close()
        body=json.loads(row[0]) if row else {}
        return bool(body.get('manual_at') or body.get('confirmed_at'))
    except (OSError,ValueError,sqlite3.Error):return None
def enabled(job,values):
    from owner_reward_context import JOBS as reward_jobs
    if job.key in reward_jobs:return False
    if job.key=='gear':return any(values.get(k) is True for k in ('auto_growth.equipment.enabled','auto_growth.blessing.enabled','auto_growth.taoist.enabled'))
    return bool(values.get(job.setting,False))

def budget(job,values):
    if job.key=='daily24_dungeon':
        match=re.fullmatch(r'(\d{1,2})시간',str(values.get('auto_challenge.secret_exploration_always.hours','1시간')))
        return max(1,min(24,int(match[1]) if match else 1))*60+15
    return job.minutes

def admission_budget(job,values):
    # Longer always-dungeons use the native boss-yield loop. Requiring a
    # continuous 24-hour gap would postpone them forever when bosses are on.
    return min(75,budget(job,values)) if job.key=='daily24_dungeon' else budget(job,values)

def busy_windows(values,at,days=9,*,root=None):
    result=[]
    configured=[]
    enabled_bosses={'auto_schedule.field_boss':'auto_schedule.field_boss.enabled',
                    'auto_schedule.falling_battle':'auto_schedule.falling_battle.enabled',
                    'auto_schedule.artifact_charm':'auto_schedule.artifact_charm.enabled'}
    required={key for key,setting in enabled_bosses.items() if values.get(setting)}
    if root is not None and required:
        path=Path(root)/'profiles/DKB/config/server-schedule.json'
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'));specs=data['schedules']
            if not isinstance(specs,list):raise ValueError('schedules')
            for identifier in required:
                matches=[spec for spec in specs if isinstance(spec,dict) and spec.get('id')==identifier]
                if len(matches)!=1:raise ValueError('missing or duplicate boss schedule')
                spec=matches[0];weekdays=spec.get('weekdays',list(range(7)))
                if not isinstance(weekdays,list) or any(type(x) is not int or x not in range(7) for x in weekdays):raise ValueError('invalid weekdays')
                start=spec.get('window_start') or spec.get('time')
                # Falling has no configured time; retain legacy protection but
                # do not manufacture a claimed time for the game.
                if not start and identifier=='auto_schedule.falling_battle':continue
                if not isinstance(start,str):raise ValueError('missing configured boss time')
                start=time.fromisoformat(start);end=spec.get('window_end')
                if end is not None and not isinstance(end,str):raise ValueError('invalid window end')
                configured.append((start,time.fromisoformat(end) if end else None,weekdays))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise ValueError('활성 보스의 프로그램 예약 설정을 확인할 수 없어 시간표를 보류합니다') from exc
    for n in range(-1,days):
        day=at.date()+timedelta(days=n)
        ranges=[]
        if values.get('auto_schedule.field_boss.enabled'):ranges.append(('20:35','21:20'))
        if values.get('auto_schedule.falling_battle.enabled'):ranges.append(('21:40','23:40'))
        if values.get('auto_schedule.artifact_charm.enabled') and day.weekday() in (4,5):ranges.extend((('13:35','15:20'),('19:35','21:30')))
        for a,b in ranges:result.append((datetime.combine(day,time.fromisoformat(a),KST),datetime.combine(day,time.fromisoformat(b),KST)))
        for start_clock,end_clock,weekdays in configured:
            if day.weekday() not in weekdays:continue
            start=datetime.combine(day,start_clock,KST)
            end=datetime.combine(day,end_clock,KST) if end_clock else start+timedelta(minutes=10)
            if end<start:end+=timedelta(days=1)
            result.append((start-timedelta(minutes=15),end))
    return sorted(result)

def fit(candidate,minutes,windows):
    duration=timedelta(minutes=minutes)
    for start,end in windows:
        if candidate<end and candidate+duration>start:candidate=end+timedelta(minutes=2)
    return candidate

def boss_signature(root,values):
    flags=tuple(bool(values.get(k)) for k in ('auto_schedule.field_boss.enabled','auto_schedule.falling_battle.enabled','auto_schedule.artifact_charm.enabled'))
    if not any(flags):return (flags,None)
    try:raw=(Path(root)/'profiles/DKB/config/server-schedule.json').read_bytes()
    except OSError as exc:raise ValueError('활성 보스의 프로그램 예약 설정을 확인할 수 없어 시간표를 보류합니다') from exc
    return flags,hashlib.sha256(raw).digest()

def config(root):
    path=Path(root)/'settings/owner-timetable.json'
    with LOCK:
        value=read_required_if_present(path,None)
        if value is None:
            value={'version':1,'enabled':True,'jitter_seconds':60,'seed':secrets.token_hex(16),
                'jobs':{job.key:{'time':job.clock} for job in JOBS}}
            save(path,value)
        if not isinstance(value.get('jobs'),dict) or not isinstance(value.get('seed'),str) or not value['seed']:
            raise ValueError('시간표 설정 항목 오류 · 기존 기록 유지')
        missing=[job for job in JOBS if job.key not in value.get('jobs',{})]
        if missing:
            for job in missing:value.setdefault('jobs',{})[job.key]={'time':job.clock}
            save(path,value)
    return value

def fingerprint(cfg,job):
    value={key:cfg.get(key) for key in ('enabled','seed','jitter_seconds')}
    value['time']=cfg.get('jobs',{}).get(job.key,{}).get('time',job.clock)
    rule=cfg.get('jobs',{}).get(job.key,{})
    value['weekday']=job.weekday
    if job.key not in EXCLUDED_USER_SETTINGS:
        value['weekdays']=rule.get('weekdays')
        value['job_jitter_seconds']=rule.get('jitter_seconds')
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def selected_days(cfg,job):
    if job.key in EXCLUDED_USER_SETTINGS:return None
    days=cfg.get('jobs',{}).get(job.key,{}).get('weekdays')
    if days is None:return None  # preserve existing allocation policy
    if not isinstance(days,list) or not days or any(type(d) is not int or not 0<=d<=6 for d in days) or len(days)!=len(set(days)):
        raise ValueError('시간표 요일은 월~일 중 하나 이상이어야 합니다')
    return set(days)

def set_user_rule(cfg,key,clock,weekdays,jitter_seconds):
    if key in EXCLUDED_USER_SETTINGS:raise ValueError('우편·출석/이벤트는 사용자 예약 설정에서 제외됩니다')
    if key not in BY_KEY:raise ValueError('실행 가능한 일정이 아닙니다')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('시각 형식 오류')
    trial=dict(cfg);trial['jobs']=dict(cfg.get('jobs',{}))
    rule=dict(trial['jobs'].get(key,{}));rule.update(time=clock,weekdays=list(weekdays),jitter_seconds=jitter_seconds)
    trial['jobs'][key]=rule
    selected_days(trial,BY_KEY[key]);jitter_range(trial,BY_KEY[key]);return trial

def save_user_rule(root,key,clock,weekdays,jitter_seconds,*,expected_rule):
    """Merge into fresh settings without silently overwriting another editor."""
    with LOCK:
        latest=config(root)
        if latest['jobs'].get(key)!=expected_rule:
            raise ValueError('다른 창에서 같은 일정을 변경했습니다. 창을 다시 열어 확인해 주세요.')
        updated=set_user_rule(latest,key,clock,weekdays,jitter_seconds)
        save(Path(root)/'settings/owner-timetable.json',updated)
        return updated

def save_user_rules(root,changes,*,expected_rules):
    """Validate the whole editor before atomically replacing its one file."""
    with LOCK:
        latest=config(root);updated=latest
        for key,rule in changes.items():
            if latest['jobs'].get(key)!=expected_rules.get(key):
                raise ValueError('다른 창에서 같은 일정을 변경했습니다. 다시 열어 주세요.')
            updated=set_user_rule(updated,key,rule['clock'],rule['weekdays'],rule['jitter_seconds'])
        if changes:save(Path(root)/'settings/owner-timetable.json',updated)
        return updated

def jitter_range(cfg,job):
    setting=cfg.get('jobs',{}).get(job.key,{})
    value=(cfg.get('jitter_seconds',60) if job.key in EXCLUDED_USER_SETTINGS
           else setting.get('jitter_seconds',cfg.get('jitter_seconds',60)))
    if type(value) is not int or not 0<=value<=120:raise ValueError('시간표 랜덤 범위는 0~120초입니다')
    return value

def preferred_base(job,cfg,at,key):
    """Select occurrence in the current *game* day/week, or defer it."""
    clock=time.fromisoformat(cfg.get('jobs',{}).get(job.key,{}).get('time',job.clock))
    days=selected_days(cfg,job)
    anchor=day_at(at) if job.once else datetime.fromisoformat(key).date()
    if days is None:
        if job.week and job.weekday is not None:anchor+=timedelta(days=(job.weekday-anchor.weekday())%7)
        return datetime.combine(anchor,clock,KST)
    period_start=datetime.combine(anchor,time(5),KST)
    period_end=period_start+timedelta(days=7 if job.week else 1)
    opts=[]
    for offset in range(0,8 if job.week else 2):
        day=anchor+timedelta(days=offset)
        if day.weekday() not in days:continue
        when=datetime.combine(day,clock,KST)
        if period_start<=when<period_end:opts.append(when)
    upcoming=[when for when in opts if when>=at]
    if upcoming:return min(upcoming)
    # A late start can catch up on the user's chosen civil day only.
    earlier=[when for when in opts if when.date()==at.date() and when<=at]
    return max(earlier) if earlier else None

class Planner:
    def __init__(self,root,values,at=None):
        self.root=Path(root);self.values=dict(values);self.values['owner_shop.enabled']=shop_selection_enabled(root);self.identity=identity(root)
        self.path=self.root/'settings/owner-timetable-state.json';self.cfg=config(root)
        self.data=read_required_if_present(self.path,{'version':1,'characters':{}})
        if not isinstance(self.data.get('characters'),dict):raise ValueError('시간표 실행 기록 형식 오류 · 기존 기록 유지')
        self.state=self.data.setdefault('characters',{}).setdefault(self.identity,{})
        for item in self.state.values():
            if item.get('status')=='running':item.update(status='failed',at=(at or now()).isoformat(),interrupted=True)
        self.active=None;self.last_check=0.;self.build(at or now())
        self.startup_recheck(at or now())
        self.migrate_dungeon_recheck(at or now())
        # Old inventory failures exhausted the two-attempt daily cap without
        # proving completion. Revisit through current guarded handlers; never
        # erase resource journals or migrate successful/disabled occurrences.
        inventory=self.state.get('inventory',{})
        if inventory.get('status')=='failed' and inventory.get('attempts',0)>=2:
            self.retry_incomplete('inventory',{'retryable':True,'retry_mode':'recheck',
                'reason':'이전 인벤토리 실패 기록 · 새 화면으로 재확인'},at or now())

    def commit(self):
        with LOCK:save(self.path,self.data)

    def migrate_dungeon_recheck(self,at):
        """Move legacy three-hour holds to the current safe entry check once."""
        changed=False
        for key in RECHECK_JOBS:
            item=self.state.get(key,{})
            if (item.get('status')!='pending' or not item.get('dungeon_recheck')
                or item.get('entry_recheck_policy')=='immediate-v1' or item.get('period')!=period(BY_KEY[key],at)):continue
            candidate=fit(at,admission_budget(BY_KEY[key],self.values),busy_windows(self.values,at,root=self.root))
            item.update(at=candidate.isoformat(),entry_recheck_policy='immediate-v1',deferred_for='비경 잔여시간 즉시 재확인',result_unverified=True)
            changed=True
        if changed:self.commit()

    def startup_recheck(self,at):
        """Restore unfinished anytime chores once per planner/start, not per tick.

        A handler still checks actual quota/admission and its resource journal.
        This does not manufacture completion or clear any pending input.
        Timed field bosses live outside this anytime-job catalogue.
        """
        if not self.cfg.get('enabled',True):return []
        restored=[]
        for job in JOBS:
            row=self.state.get(job.key,{})
            if job.once or not enabled(job,self.values) or row.get('period')!=period(job,at):continue
            days=selected_days(self.cfg,job)
            if days is not None and at.weekday() not in days:continue
            if row.get('status')=='confirmed' or (row.get('last_outcome') in FINISHED and not row.get('result_unverified')):continue
            status=row.get('status')
            # Zero dungeon time was already read today, so a restart has nothing to recheck.
            if status=='processed' and row.get('no_time_left_at') and not row.get('result_unverified'):continue
            if status not in ('processed','failed','pending','calendar_hold'):continue
            # Tried under 20 minutes ago with nothing sent: every F1 spent three minutes redoing the clan,
            # blessing and gear visits. Its own retry time still brings it back.
            if row.get('ended_at') and row.get('last_outcome')!=SENT_UNCONFIRMED and not row.get('interrupted'):
                try:
                    if 0<=(at-parse_at(row['ended_at'])).total_seconds()<1200:continue
                except (TypeError,ValueError):pass
            # A second planner in the same start must not replace the original
            # receipt in startup_previous with its own pending copy.
            if status=='pending' and row.get('startup_recheck'):continue
            # A restart must not bring a remaining-time recheck forward.
            if status=='pending' and row.get('dungeon_recheck') and parse_at(row['at'])>at:continue
            planned=parse_at(row['at'])
            # A never-started future appointment keeps its requested time.
            nominal=preferred_base(job,self.cfg,at,row['period'])
            if status=='pending' and planned>at and not row.get('incomplete_retry') and not row.get('interrupted') and (nominal is None or nominal>at):continue
            if status=='calendar_hold' and not row.get('last_attempt_failed'):continue
            retry=fit(at+timedelta(seconds=5),admission_budget(job,self.values),busy_windows(self.values,at,root=self.root))
            if period(job,retry)!=row['period']:continue
            row['startup_previous']={k:row.get(k) for k in ('status','at','attempts','last_outcome','ended_at')}
            row.update(status='pending',at=retry.isoformat(),attempts=0,startup_recheck=True,
                       result_unverified=True,deferred_for='재시작 · 미완료 재확인')
            if row.get('last_outcome')==SENT_UNCONFIRMED:
                row.update(incomplete_retry=True,retry_mode='reconcile')
            restored.append(job.key)
        if restored:
            self.commit()
            LOG.info('시작 일정 재확인 · 미완료 %d개 · 완료 확인 항목·사용 해제 항목 제외',len(restored))
        return restored

    def retry_incomplete(self,key,outcome,at):
        """Keep explicitly reported, safely closed work due across restarts.

        This never clears a purchase/claim intent. Result-only visits cannot
        turn into new resource input if the old journal is still uncertain.
        """
        if not isinstance(outcome,dict) or outcome.get('retryable') is not True:return False
        if key not in ('inventory','shop','shop_weekly_verify'):return False
        job=BY_KEY[key];item=self.state.get(key,{})
        if not enabled(job,self.values) or not self.cfg.get('enabled',True):return False
        if item.get('period')!=period(job,at) or item.get('status')=='running':return False
        days=selected_days(self.cfg,job)
        if days is not None and at.weekday() not in days:return False
        candidate=fit(at+timedelta(minutes=20),admission_budget(job,self.values),
                      busy_windows(self.values,at,root=self.root))
        if period(job,candidate)!=item['period'] or (days is not None and candidate.weekday() not in days):return False
        if period(job,candidate+timedelta(minutes=admission_budget(job,self.values)))!=item['period']:return False
        mode='reconcile' if outcome.get('retry_mode')=='reconcile' else 'recheck'
        item.update(status='pending',at=candidate.isoformat(),result_unverified=True,
                    incomplete_retry=True,retry_mode=mode,
                    retry_reason=str(outcome.get('reason') or '판독 미확인')[:160])
        if key=='inventory':
            item['energy_followup']={'mode':mode}
        self.commit()
        LOG.warning('작업 미완료 · %s · %s · 다음 확인 %s%s',job.label,item['retry_reason'],
                    candidate.strftime('%H:%M:%S'),' · 결과 확인만' if mode=='reconcile' else '')
        return True

    def recheck_dungeon(self,key,no_time_left,at):
        """Done only on the native zero read; no three-hour detour."""
        job=BY_KEY[key];item=self.state[key]
        if no_time_left:
            item.pop('dungeon_recheck',None);item.pop('result_unverified',None);item['no_time_left_at']=at.isoformat();item['status']='processed'
            self.commit();LOG.info('비경 잔여시간 없음 확인 · %s',job.label);return False
        candidate=fit(at,admission_budget(job,self.values),busy_windows(self.values,at,root=self.root))
        # This continues an already started occurrence, not a new weekday slot.
        # Unknown quota must never become completed merely because midnight or
        # a reset boundary passed while the dungeon was running.
        item.update(status='pending',at=candidate.isoformat(),attempts=0,result_unverified=True,dungeon_recheck=True,entry_recheck_policy='immediate-v1',deferred_for='비경 잔여시간 즉시 재확인')
        self.commit();LOG.info('비경 잔여시간 즉시 재확인 · %s · %s',job.label,candidate.strftime('%m/%d %H:%M:%S'));return True

    def repeat_growth(self,at):
        """An unverified growth visit is not today's final goal completion."""
        item=self.state.get('gear',{});job=BY_KEY['gear']
        if not enabled(job,self.values) or not self.cfg.get('enabled',True):return False
        if item.get('period')!=period(job,at):return False
        days=selected_days(self.cfg,job)
        if days is not None and at.weekday() not in days:return False
        legacy=item.get('status')=='processed' and item.get('result_unverified') is True
        continuing=item.get('status')=='pending' and item.get('growth_recheck') is True
        if not (legacy or continuing):return False
        from owner_gear_settings_candidate import Store
        from owner_hunt_rules_candidate import configured_identity
        try:store=Store(self.root,configured_identity(self.root))
        except (OSError,ValueError,TypeError,KeyError):return False
        stamp=store.path.stat().st_mtime_ns if store.path.exists() else None
        cache=getattr(self,'_growth_interval_cache',None)
        if cache is None or cache[0]!=stamp:
            cache=(stamp,store.read()['recheck_minutes']);self._growth_interval_cache=cache
        minutes=cache[1]
        if continuing and item.get('recheck_minutes')==minutes:return False
        end=parse_at(item['ended_at'])
        candidate=max(end+timedelta(minutes=minutes),at)
        windows=busy_windows(self.values,candidate,root=self.root)
        for key,other in self.state.items():
            if key!='gear' and key in BY_KEY and enabled(BY_KEY[key],self.values) and other.get('status')=='pending':
                start=parse_at(other['at'])
                windows.append((start,start+timedelta(minutes=admission_budget(BY_KEY[key],self.values))))
        candidate=fit(candidate,admission_budget(job,self.values),sorted(windows))
        if days is not None and candidate.weekday() not in days:return False
        if period(job,candidate)!=item['period']:return False
        if legacy:item['last_cycle_attempts']=item.get('attempts',0)
        item.update(status='pending',at=candidate.isoformat(),growth_recheck=True,recheck_minutes=minutes,attempts=0)
        self.commit();return True

    def repeat_energy(self,outcome,at):
        """Continue a verified partial box batch, never repeat an unknown input."""
        item=self.state.get('inventory',{});job=BY_KEY['inventory']
        if (not isinstance(outcome,dict) or outcome.get('needs_recheck') is not True
            or not enabled(job,self.values) or not self.cfg.get('enabled',True)
            or item.get('period')!=period(job,at) or item.get('status')=='running'):return False
        days=selected_days(self.cfg,job)
        if days is not None and at.weekday() not in days:return False
        checking=outcome.get('reconcile_only') is True
        if checking:
            op=outcome.get('pending_operation')
            if not isinstance(op,str) or len(op)!=32 or any(c not in '0123456789abcdef' for c in op):return False
            retries=item.get('energy_confirm_retries',0) if item.get('energy_confirm_operation')==op else 0
            if type(retries) is not int or retries>=2:return False
            marker={'mode':'reconcile','operation_id':op}
        else:
            if (not outcome.get('confirmed') or type(outcome.get('remaining')) is not int
                or outcome['remaining']<1):return False
            marker={'mode':'claim','remaining':outcome['remaining']}
        candidate=at+timedelta(seconds=60)
        windows=busy_windows(self.values,candidate,root=self.root)
        for key,other in self.state.items():
            if key!='inventory' and key in BY_KEY and enabled(BY_KEY[key],self.values) and other.get('status')=='pending':
                start=parse_at(other['at']);windows.append((start,start+timedelta(minutes=admission_budget(BY_KEY[key],self.values))))
        candidate=fit(candidate,admission_budget(job,self.values),sorted(windows))
        if (period(job,candidate)!=item['period'] or (days is not None and candidate.weekday() not in days)
            or period(job,candidate+timedelta(minutes=admission_budget(job,self.values)))!=item['period']):return False
        item.update(status='pending',at=candidate.isoformat(),attempts=0,result_unverified=True,
                    energy_followup=marker,deferred_for='기운 상자 결과 확인' if checking else '기운 상자 남은 수량 처리')
        if checking:item.update(energy_confirm_operation=op,energy_confirm_retries=retries+1)
        else:
            item.pop('energy_confirm_operation',None);item.pop('energy_confirm_retries',None)
        self.commit();return True

    def build(self,at,*,readonly=False):
        if readonly:
            self.cfg=read_required_if_present(self.root/'settings/owner-timetable.json',None)
            if not isinstance(self.cfg,dict) or not isinstance(self.cfg.get('jobs'),dict) or not isinstance(self.cfg.get('seed'),str) or not self.cfg['seed']:
                raise ValueError('시간표 설정 항목 오류 · 기존 기록 유지')
        else:self.cfg=config(self.root)
        boss_windows=busy_windows(self.values,at,root=self.root)
        self._boss_stamp=boss_signature(self.root,self.values)
        windows=list(boss_windows)
        windows+= [(parse_at(item['at']),parse_at(item['at'])+timedelta(minutes=item.get('budget_minutes',5))) for key,item in self.state.items() if key in BY_KEY and enabled(BY_KEY[key],self.values) and item.get('period')==period(BY_KEY[key],at) and item.get('config')==fingerprint(self.cfg,BY_KEY[key]) and item.get('status')=='pending' and parse_at(item['at'])>=at and fit(parse_at(item['at']),admission_budget(BY_KEY[key],self.values),boss_windows)==parse_at(item['at'])]
        windows.sort();cursor=at+timedelta(seconds=5)
        def order(job):
            base=preferred_base(job,self.cfg,at,period(job,at))
            return (base or datetime.max.replace(tzinfo=KST),job.key)
        for job in sorted(JOBS,key=order):
            if not enabled(job,self.values):continue
            key=period(job,at);old=self.state.get(job.key,{})
            stamp=fingerprint(self.cfg,job)
            # A settings/reset/boss-window refresh may happen while the sole
            # worker owns this occurrence. Preserve its receipt until finish;
            # replacing it with pending would erase its attempt and identity.
            if old.get('status')=='running':
                self._rebuild_after_running=True
                continue
            if job.once and old and old.get('status') not in ('calendar_hold','pending'):
                # A held survey belongs to the region it was started for. Saving a
                # different region is a new, explicit request: it is planned again
                # once. Same region stays held; this is still not a daily rerun.
                region=self.values.get(TREASURE_REGION)
                if old.get('status')=='held' and old.get('region') and region and old['region']!=region:
                    LOG.info('보물찾기 지방 변경 · %s → %s · 보류 기록 해제 · 1회 재계획',old['region'],region)
                    old.clear()
                else:
                    old['period']='all';old['config']=stamp
                    # A partial first survey is not a complete account-wide clear.
                    # It stays held for evidence/eligibility review, not daily rerun.
                    if old.get('status')=='failed':old['status']='held'
                    continue
            if old.get('period')==key and old.get('status')=='processed':
                old['config']=stamp;continue
            if old.get('period')==key and old.get('config')==stamp and old.get('status')=='failed':
                candidate=fit(max(parse_at(old['at']),at),admission_budget(job,self.values),windows)
                if candidate>max(parse_at(old['at']),at):
                    chosen=selected_days(self.cfg,job)
                    if chosen is not None and (candidate.weekday() not in chosen or (not job.once and period(job,candidate)!=key)):
                        old.update(status='calendar_hold',at=candidate.isoformat(),calendar_day=day_at(at).isoformat(),deferred_for='요일 또는 초기화 경계')
                    else:old.update(at=candidate.isoformat(),deferred_for='보스 또는 앞 일정')
                continue
            pending_safe=(old.get('status')!='pending' or fit(parse_at(old['at']),admission_budget(job,self.values),boss_windows)==parse_at(old['at']))
            if old.get('period')==key and old.get('config')==stamp and old.get('budget_minutes')==budget(job,self.values) and pending_safe and not (job.once and old.get('status')=='calendar_hold' and old.get('calendar_day')!=day_at(at).isoformat()):continue
            base=preferred_base(job,self.cfg,at,key)
            if base is None:
                self.state[job.key]={'period':key,'config':stamp,'at':at.isoformat(),'status':'calendar_hold','calendar_day':day_at(at).isoformat(),'attempts':0,'budget_minutes':budget(job,self.values)}
                continue
            spread=jitter_range(self.cfg,job)
            digest=hashlib.sha256((self.cfg['seed']+self.identity+job.key+key).encode()).digest()
            jitter=int.from_bytes(digest[:4],'little')%(2*spread+1)-spread
            candidate=base+timedelta(seconds=jitter)
            # Late starts catch up in separate reserved slots, not all at once.
            candidate=max(candidate,cursor+timedelta(seconds=abs(jitter)))
            minutes=budget(job,self.values)
            candidate=fit(candidate,admission_budget(job,self.values),windows)
            selected=selected_days(self.cfg,job)
            # Fitting or jitter cannot move a scheduled occurrence into a
            # different user's weekday or a different reset period.
            if selected is not None and (candidate.weekday() not in selected or (not job.once and period(job,candidate)!=key)):
                self.state[job.key]={'period':key,'config':stamp,'at':candidate.isoformat(),'status':'calendar_hold','calendar_day':day_at(at).isoformat(),'attempts':0,'budget_minutes':minutes}
                continue
            reset=datetime.combine(day_at(candidate)+timedelta(days=1),time(5),KST)
            if not job.week and minutes<24*60 and candidate+timedelta(minutes=minutes)>reset:
                candidate=fit(reset+timedelta(minutes=3),admission_budget(job,self.values),windows)
                if selected is not None and (candidate.weekday() not in selected or (not job.once and period(job,candidate)!=key)):
                    self.state[job.key]={'period':key,'config':stamp,'at':candidate.isoformat(),'status':'calendar_hold','calendar_day':day_at(at).isoformat(),'attempts':0,'budget_minutes':minutes}
                    continue
            self.state[job.key]={'period':key,'config':stamp,'at':candidate.isoformat(),
                'jitter':jitter,'status':'pending','attempts':0,'budget_minutes':minutes}
            if old.get('status')=='pending' and not pending_safe:self.state[job.key]['deferred_for']='보스 출발 시간 변경'
            cursor=candidate+timedelta(minutes=minutes+2)
        self.commit()

    def due(self,at=None):
        at=at or now()
        shop_enabled=shop_selection_enabled(self.root);shop_changed=self.values.get('owner_shop.enabled')!=shop_enabled
        if shop_changed:
            self.values['owner_shop.enabled']=shop_enabled
            # Otherwise the shop appointment disappears from the timetable with no log line.
            LOG.info('잡화상점 구매 시간표 %s · 설정 상품 구매 사용 체크와 선택 품목 기준','사용' if shop_enabled else '해제')
        if shop_changed or config(self.root)!=self.cfg or boss_signature(self.root,self.values)!=self._boss_stamp or any(enabled(j,self.values) and (self.state.get(j.key,{}).get('period')!=period(j,at) or (j.once and self.state.get(j.key,{}).get('status')=='calendar_hold' and self.state[j.key].get('calendar_day')!=day_at(at).isoformat())) for j in JOBS):self.build(at)
        if not self.cfg.get('enabled',True):return []
        self.repeat_growth(at)
        result=[]
        for job in JOBS:
            item=self.state.get(job.key,{})
            if not enabled(job,self.values) or item.get('status') not in ('pending','failed'):continue
            if job.once and treasure_confirmed(self.root) is not False:continue
            if item.get('attempts',0)>=2 and item.get('incomplete_retry') is not True:continue
            planned=parse_at(item['at']);selected=selected_days(self.cfg,job)
            continuation=item.get('dungeon_recheck') is True and job.key in RECHECK_JOBS
            if not continuation and selected is not None and (planned.weekday() not in selected or (not job.once and period(job,planned)!=period(job,at))):
                item['status']='calendar_hold';item['calendar_day']=day_at(at).isoformat();self.commit();continue
            if not continuation and selected is not None and at.weekday() not in selected:continue
            if planned<=at:result.append(job)
        return sorted(result,key=lambda j:self.state[j.key]['at'])

    def reason(self,key,at=None):
        at=at or now()
        if config(self.root)!=self.cfg or boss_signature(self.root,self.values)!=self._boss_stamp:self.build(at)
        self.repeat_growth(at)
        item=self.state.get(key)
        if not self.cfg.get('enabled',True) or item is None:return None
        if item.get('status')=='calendar_hold':return '선택한 요일·초기화 주기 대기'
        days=selected_days(self.cfg,BY_KEY[key])
        if days is not None and at.weekday() not in days and not (key in RECHECK_JOBS and item.get('dungeon_recheck')):return '선택한 요일 대기'
        if BY_KEY[key].once:
            confirmed=treasure_confirmed(self.root)
            if confirmed:return '일회성 보물찾기 완료 확인 · 반복 없음'
            if confirmed is None:return '보물 완료 기록 읽기 실패 · 확인 필요'
        if item.get('status') in ('held','confirmed'):return '일회성 보물찾기 · 미수집·해금 조건 확인 후 재개' if item['status']=='held' else '보물찾기 완료 확인 · 반복 없음'
        if item.get('status')=='processed':return '일회성 탐색 처리 종료 · 미수집 확인 필요' if BY_KEY[key].once else '오늘/이번 주 시간표 처리 종료'
        if item.get('attempts',0)>=2 and item.get('incomplete_retry') is not True:return '시간표 재시도 2회 종료·진단 확인 필요'
        if item.get('incomplete_retry') is True and parse_at(item['at'])>at:
            return ('결과 확인만' if item.get('retry_mode')=='reconcile' else '미완료 재확인')+' '+parse_at(item['at']).strftime('%m/%d %H:%M:%S')
        if parse_at(item['at'])>at:return '시간표 '+parse_at(item['at']).strftime('%m/%d %H:%M:%S')
        safe=fit(at,admission_budget(BY_KEY[key],self.values),busy_windows(self.values,at,root=self.root))
        if safe>at:
            item['at']=safe.isoformat();item['deferred_for']='보스 출발 시간';self.commit()
            return '보스 일정 뒤 '+safe.strftime('%m/%d %H:%M:%S')
        due=self.due(at)
        if due and due[0].key!=key:return '앞 일정 '+due[0].label+' 종료 후'
        return None

    def begin(self,key,at=None):
        item=self.state[key];item['attempts']+=1;item['started_at']=(at or now()).isoformat();item['status']='running'
        if BY_KEY[key].once:item['region']=self.values.get(TREASURE_REGION)
        self.commit()
    def finish(self,key,ok,at=None,*,unverified=False,count_failure=True):
        at=at or now();item=self.state[key];item.update(status='processed' if ok else ('held' if BY_KEY[key].once else 'failed'),ended_at=at.isoformat())
        for field in ('incomplete_retry','retry_mode','retry_reason'):item.pop(field,None)
        if ok and unverified:item['result_unverified']=True
        else:item.pop('result_unverified',None)
        if ok:item.pop('not_attempted_count',None);item.pop('dungeon_failures',None)
        if not ok and key in DUNGEON_JOBS:
            # Time-limited content ends only on the actual zero read or its
            # chosen hours. A failure is retried with no cap and no long cooldown.
            count=item.get('dungeon_failures',0)
            retry=at+timedelta(minutes=min(DUNGEON_RETRY_MAX,DUNGEON_RETRY_FIRST*2**count))
            item.update(status='pending',at=retry.isoformat(),attempts=0,result_unverified=True,dungeon_failures=count+1,deferred_for='비경 실패 재시도')
            if key in RECHECK_JOBS:item.update(dungeon_recheck=True,entry_recheck_policy='immediate-v1')
            LOG.warning('비경 미완료 · %s · 다음 시도 %s',BY_KEY[key].label,retry.strftime('%H:%M:%S'))
        elif not ok:
            retry=at+timedelta(minutes=10);item['at']=retry.isoformat()
            job=BY_KEY[key];chosen=selected_days(self.cfg,job)
            if count_failure and not job.once and item.get('attempts',0)>=2 and item.get('failed_cycles',0)<FAILED_CYCLES:
                # Two quick failures must not lose the rest of a day or a week.
                # Resource intents still block any input that is unconfirmed.
                later=at+timedelta(minutes=FAILED_COOLDOWN_WEEK if job.week else FAILED_COOLDOWN_DAY)
                if period(job,later)==item['period']:
                    retry=later;item['at']=retry.isoformat();item['attempts']=0
                    item['failed_cycles']=item.get('failed_cycles',0)+1
            if chosen is not None and not job.once:
                reset=datetime.combine(datetime.fromisoformat(item['period']).date()+timedelta(days=7 if job.week else 1),time(5),KST)
                if retry.weekday() not in chosen or period(job,retry)!=item['period'] or (budget(job,self.values)<24*60 and retry+timedelta(minutes=budget(job,self.values))>reset):
                    item.update(status='calendar_hold',calendar_day=day_at(at).isoformat(),deferred_for='요일 또는 초기화 경계',last_attempt_failed=True)
        # Actual overrun moves subsequent appointments; never claims a fixed
        # duration is a guaranteed finish time.
        cursor=at+timedelta(minutes=2)
        windows=busy_windows(self.values,at,root=self.root)
        for job in sorted(JOBS,key=lambda j:self.state.get(j.key,{}).get('at','9999')):
            if not enabled(job,self.values):continue
            pending=self.state.get(job.key,{})
            if pending.get('status')!='pending':continue
            # Startup catch-up is a serial queue, not a second timetable of
            # estimated durations. The owning worker and reason() still guard
            # boss windows; finishing a short job must not delay every check.
            if pending.get('startup_recheck'):continue
            candidate=max(parse_at(pending['at']),cursor)
            minutes=budget(job,self.values)
            candidate=fit(candidate,admission_budget(job,self.values),windows)
            chosen=selected_days(self.cfg,job)
            if chosen is not None:
                # A prior task overrun must not move this task into another
                # selected game day/week while leaving the old receipt key.
                reset=(datetime.combine(datetime.fromisoformat(pending['period']).date()+timedelta(days=7 if job.week else 1),time(5),KST)
                       if not job.once else datetime.combine(day_at(candidate)+timedelta(days=1),time(5),KST))
                crosses_finish=minutes<24*60 and candidate+timedelta(minutes=minutes)>reset
                if candidate.weekday() not in chosen or (not job.once and period(job,candidate)!=pending['period']) or crosses_finish:
                    pending.update(status='calendar_hold',at=candidate.isoformat(),calendar_day=day_at(at).isoformat(),deferred_for='요일 또는 초기화 경계')
                    continue
            pending['at']=candidate.isoformat();cursor=candidate+timedelta(minutes=minutes+2)
        self.commit()
        if getattr(self,'_rebuild_after_running',False):
            self._rebuild_after_running=False
            self.build(at)
        if key=='gear' and ok and unverified:self.repeat_growth(at)

    def recheck_minutes(self):
        """The user's growth recheck interval for proven waits and result checks."""
        from owner_gear_settings_candidate import Store
        from owner_hunt_rules_candidate import configured_identity
        try:return Store(self.root,configured_identity(self.root)).read()['recheck_minutes']
        except (OSError,ValueError,TypeError,KeyError):return 20

    def apply_outcome(self,key,outcome,at=None):
        """The single place a reported result becomes schedule state."""
        at=at or now();item=self.state[key]
        if outcome.kind in FINISHED or outcome.kind==FAILED:
            self.finish(key,outcome.kind in FINISHED,at,unverified=outcome.unverified)
        else:
            self.finish(key,False,at,count_failure=False)
            if not BY_KEY[key].once:self.defer(key,outcome,at)
        item=self.state[key];item['last_outcome']=outcome.kind
        if outcome.reason:item['last_outcome_reason']=outcome.reason[:160]
        else:item.pop('last_outcome_reason',None)
        self.commit()

    def defer(self,key,outcome,at):
        """Keep work due without using an attempt. Never clears a resource intent."""
        job=BY_KEY[key];item=self.state[key]
        if outcome.kind==NOT_ATTEMPTED:
            count=item.get('not_attempted_count',0)
            minutes=min(60,10*2**count);item['not_attempted_count']=count+1
        else:minutes=self.recheck_minutes()
        item['attempts']=max(0,item.get('attempts',0)-1)
        candidate=fit(at+timedelta(minutes=minutes),admission_budget(job,self.values),busy_windows(self.values,at,root=self.root))
        days=selected_days(self.cfg,job)
        if period(job,candidate)!=item['period'] or (days is not None and candidate.weekday() not in days):
            item['at']=candidate.isoformat();return False
        item.update(status='pending',at=candidate.isoformat(),incomplete_retry=True,
                    retry_mode='reconcile' if outcome.kind==SENT_UNCONFIRMED else 'recheck',
                    retry_reason=(outcome.reason or '판독 미확인')[:160])
        if outcome.kind==SENT_UNCONFIRMED:item['result_unverified']=True
        LOG.warning('작업 미완료 · %s · %s · 다음 확인 %s',job.label,item['retry_reason'],candidate.strftime('%H:%M:%S'))
        return True

LIVE={'adapter':None}
def planner(adapter):
    value=getattr(adapter,'_owner_timetable',None)
    if value is None:
        value=Planner(adapter.project.root,adapter.values);adapter._owner_timetable=value
    import weakref
    try:LIVE['adapter']=weakref.ref(adapter)
    except TypeError:pass
    # A job in progress runs on a masked copy of the values, so a change saved during
    # a pause is applied again here, once the real values are back.
    patch=getattr(adapter,'_owner_settings_patch',None)
    if patch:
        adapter.values.update(patch)
        if isinstance(getattr(value,'values',None),dict):value.values.update(patch)
    return value

def live_settings(changes):
    """Settings saved during a pause reach the paused run. Returns False if none is running."""
    ref=LIVE['adapter'];adapter=ref() if ref else None
    if adapter is None or not isinstance(getattr(adapter,'values',None),dict):return False
    patch=dict(getattr(adapter,'_owner_settings_patch',None) or {});patch.update(changes)
    adapter._owner_settings_patch=patch;adapter.values.update(changes)
    plan=getattr(adapter,'_owner_timetable',None)
    if isinstance(getattr(plan,'values',None),dict):plan.values.update(changes)
    LOG.info('일시정지 중 설정 저장 · %d개 · 재개하면 적용 · 진행 중이던 작업은 기존 값으로 마침',len(changes))
    return True

def scheduled_call(original,label,args,kwargs,adapter,*,timed_dispatch=False,run_context=None,run_inputs=None):
    key=LABEL_JOB.get(label)
    from owner_reward_context import JOBS as reward_jobs
    if key in reward_jobs:return original(*args,**kwargs)
    # This entry only revisits a durable sent enhancement and returns before
    # any fresh resource input. It must not consume or reset timed attempts,
    # nor let a timed retry limit prevent confirming an already sent result.
    if key=='gear' and getattr(adapter,'_owner_growth_reconcile_only',False) is True:
        return original(*args,**kwargs)
    if key is None or getattr(LOCAL,'job',None)==key or getattr(LOCAL,'native_job',None):return original(*args,**kwargs)
    # Starter equipment/coupon mail and main-quest level milestones retain
    # their established character-growth policy instead of waiting all day.
    if not timed_dispatch and getattr(adapter,'_owner_preparing_gears',False):return original(*args,**kwargs)
    user_rule=config(adapter.project.root).get('jobs',{}).get(key,{})
    if not timed_dispatch and getattr(adapter,'mode','auto_mode') in ('main_quest','sub_quest') and ((key=='gear' and 'weekdays' not in user_rule and getattr(adapter,'_owner_growth_milestone',None) in (20,30,40,45)) or (key in ('mail','inventory') and getattr(adapter,'_owner_initial_context',None) is None)):
        return original(*args,**kwargs)
    plan=planner(adapter)
    if not enabled(BY_KEY[key],plan.values):return True
    if key not in plan.state:return original(*args,**kwargs)
    # This ledger belongs to the configured character. Another logged-in
    # character must neither spend nor consume this character's occurrence.
    if character_mismatch(adapter):
        LOG.info('자동 기능 보류 · %s · 설정 캐릭터와 현재 캐릭터 불일치',label);return True
    reason=plan.reason(key)
    if reason:
        if key=='inventory':adapter._owner_inventory_skip_generation=getattr(adapter,'_owner_inventory_skip_generation',0)+1
        LOG.info('자동 기능 보류 · %s · %s',label,reason);return True
    previous=getattr(LOCAL,'job',None);LOCAL.job=key
    outcome=RunOutcome(label);LOG.addHandler(outcome)
    # A slot retried only to read a sent input's result must not spend again.
    result_only=key in ('gear','growth') and plan.state[key].get('incomplete_retry') is True and plan.state[key].get('retry_mode')=='reconcile'
    try:
        plan.begin(key);clear_outcome(adapter,key)
        if key=='gear':adapter._owner_growth_pending_hold=False;adapter._owner_style_growth_outcome=None
        if key=='blessing':adapter._owner_blessing_policy_outcome=None
        if key=='inventory':adapter._owner_energy_box_outcome=None
        if key in ('shop','shop_weekly_verify'):adapter._owner_shop_outcome=None
        LOG.info('자동 기능 시작 · %s',label)
        if key=='inventory' and plan.state[key].get('energy_followup',{}).get('mode')=='reconcile':
            context=run_context or next((value for value in args if callable(getattr(value,'checkpoint',None))),None)
            inputs=run_inputs if run_inputs is not None else (args[2] if len(args)>=3 else None)
            if context is None or inputs is None:
                adapter._owner_energy_box_outcome={'state':'held','reason':'수령 확인 작업자 연결 필요'};result=False
            else:
                from owner_energy_next_integration_candidate import attempt as confirm_energy
                old=getattr(adapter,'_owner_energy_box_reconcile_only',False);adapter._owner_energy_box_reconcile_only=True
                try:result=confirm_energy(adapter,context,inputs) in ('confirmed','nothing_pending','disabled')
                finally:adapter._owner_energy_box_reconcile_only=old
        elif result_only:
            old=getattr(adapter,'_owner_growth_reconcile_only',False);adapter._owner_growth_reconcile_only=True
            try:result=original(*args,**kwargs)
            finally:adapter._owner_growth_reconcile_only=old
        else:result=original(*args,**kwargs)
    except BaseException as exc:
        # Timed dispatch uses a zero-argument closure. Keep its Context outside
        # the closure too, so user Stop is not mislabeled as an execution error.
        context=run_context or next((value for value in (*args,*kwargs.values()) if hasattr(value,'stop')),None)
        from owner_work_resume import ResumeWork
        from owner_chore_transition import ChoreYield,ReadOnlyViewUnavailable
        if isinstance(exc,ChoreYield):
            plan.state[key]['status']='pending'
            plan.state[key]['attempts']=max(0,plan.state[key]['attempts']-1)
            if isinstance(exc,ReadOnlyViewUnavailable):
                plan.state[key]['at']=(now()+timedelta(seconds=10)).isoformat()
                plan.state[key]['deferred_for']='판독 화면 반환 대기'
            plan.commit()
            LOG.info('자동 기능 잠시 양보 · %s · %s',label,'화면 반환 후 재확인' if isinstance(exc,ReadOnlyViewUnavailable) else '서사 대화 후 재개')
        elif isinstance(exc,ResumeWork):
            # A normal route unwind is neither a completed chore nor a failed
            # attempt. Keep the occurrence pending, and let its owner resume.
            plan.state[key]['status']='pending';plan.state[key]['attempts']=max(0,plan.state[key]['attempts']-1);plan.commit()
            LOG.info('자동 기능 양보 · %s · 기존 작업 복귀',label)
        elif context is not None and context.stop.is_set():
            plan.state[key]['status']='pending';plan.state[key]['attempts']-=1;plan.commit()
            LOG.info('자동 기능 보류 · %s · 사용자 중지',label)
        else:
            plan.finish(key,False);LOG.warning('자동 기능 복구 중 · %s · 시간표 실행 오류',label)
        raise
    else:
        decided=classify_outcome(key,adapter,result)
        if decided is not None:
            plan.apply_outcome(key,decided)
            LOG.info('자동 기능 결과 · %s · %s%s',label,decided.kind,' · '+decided.reason if decided.reason else '')
            return result
        ok=(result is not False and not outcome.failed and
            not (key=='gear' and getattr(adapter,'_owner_growth_pending_hold',False)))
        unknown=ok and (result is None or (key=='gear' and not getattr(adapter,'_owner_growth_all_goals_verified',False)) or (key=='growth' and getattr(adapter,'_owner_energy_outcome',None) is not None))
        if key=='inventory':
            energy_outcome=getattr(adapter,'_owner_energy_box_outcome',None)
            if isinstance(energy_outcome,dict):
                if energy_outcome.get('state')=='held':ok=False
                if energy_outcome.get('needs_recheck') is True:unknown=True
        if ok and key=='blessing':
            blessing_outcome=getattr(adapter,'_owner_blessing_policy_outcome',None)
            if isinstance(blessing_outcome,dict) and blessing_outcome.get('state') not in ('disabled','not_run'):
                unknown=True
        if ok and key=='gear':
            style_outcome=getattr(adapter,'_owner_style_growth_outcome',None)
            if isinstance(style_outcome,dict) and style_outcome.get('state') in ('processed_unverified','held'):
                unknown=True
        plan.finish(key,ok,unverified=unknown)
        if ok and key in RECHECK_JOBS:plan.recheck_dungeon(key,outcome.no_time_left,now())
        if key=='inventory' and callable(getattr(plan,'repeat_energy',None)):
            if plan.repeat_energy(getattr(adapter,'_owner_energy_box_outcome',None),now()):
                LOG.info('기운 상자 후속 확인 예약 · %s · 입력 결과 미확인 시 재개봉 없음',plan.state[key]['at'])
            elif callable(getattr(plan,'retry_incomplete',None)):
                plan.retry_incomplete(key,getattr(adapter,'_owner_energy_box_outcome',None),now())
        elif key in ('shop','shop_weekly_verify') and callable(getattr(plan,'retry_incomplete',None)):
            plan.retry_incomplete(key,getattr(adapter,'_owner_shop_outcome',None),now())
        following=key=='inventory' and plan.state[key].get('status')=='pending' and plan.state[key].get('energy_followup')
        incomplete=plan.state[key].get('incomplete_retry') is True
        LOG.info('자동 기능 %s · %s%s','미완료 재확인 대기' if incomplete else ('후속 대기' if following else ('처리 종료' if ok else '부분 처리')),label,' · 결과 미확인' if unknown else '')
        return result
    finally:LOG.removeHandler(outcome);LOCAL.job=previous

def appointment(root,catalog_key,when,values=None):
    key=CATALOG_JOB.get(catalog_key)
    if key=='album':return '사용 불가 · 추후 안내'
    if not key:return None
    data=read(Path(root)/'settings/owner-timetable-state.json',{})
    item=data.get('characters',{}).get(identity(root),{}).get(key)
    if not item:return None
    status=item.get('status')
    if status=='calendar_hold':return '선택 요일 대기 · 다음 초기화 주기 확인'
    if BY_KEY[key].once:
        if status=='confirmed':return '일회성 · 완료 확인 · 반복 없음'
        if status in ('processed','held','failed'):return '일회성 · 탐색 기록 있음 · 미수집·해금 조건 확인'
    if status=='processed':
        if item.get('result_unverified'):return '결과 미확인 · 이번 주기 처리 종료'
        job=BY_KEY[key];next_day=datetime.fromisoformat(item['period']).date()+timedelta(days=7 if job.week else 1)
        cfg=read(Path(root)/'settings/owner-timetable.json',{})
        if selected_days(cfg,job) is not None:return '이번 주기 처리 종료 · 다음 선택 요일에 재계획'
        if job.week and job.weekday is not None:next_day+=timedelta(days=(job.weekday-next_day.weekday())%7)
        clock=cfg.get('jobs',{}).get(key,{}).get('time',job.clock)
        return next_day.strftime('%m/%d')+' '+clock+' 전후 · 다음 초기화 주기'
    if status=='running':return '현재 시간표 작업 진행 중'
    value=parse_at(item['at'])
    prefix=('결과 확인만 ' if item.get('retry_mode')=='reconcile' else '미완료 재확인 ') if item.get('incomplete_retry') is True else ('보스 일정 뒤 ' if item.get('deferred_for') else '예정 ')
    cfg=read(Path(root)/'settings/owner-timetable.json',{})
    if values is not None and status in ('pending','failed'):
        class PreviewPlanner(Planner):
            def commit(self):pass
        try:
            preview=PreviewPlanner.__new__(PreviewPlanner);preview.root=Path(root);preview.values=dict(values)
            preview.values['owner_shop.enabled']=shop_selection_enabled(root)
            preview.identity=identity(root);preview.data=copy.deepcopy(data)
            preview.state=preview.data['characters'][preview.identity]
            preview.build(when,readonly=True)
            projected=preview.state.get(key,item)
            if projected.get('status')=='calendar_hold':return '선택 요일 대기 · 다음 초기화 주기 확인'
            value=parse_at(projected['at'])
            prefix='보스 일정 뒤 ' if projected.get('deferred_for') else '예정 '
        except (ValueError,KeyError,TypeError,OSError):return '보스 또는 시간표 설정 확인 필요 · 일정 보류'
    spread=jitter_range(cfg,BY_KEY[key])
    return (prefix+value.strftime('%m/%d %H:%M:%S') if value>when else '지연 · 현재 작업 종료 후')+(' · 랜덤 ±%d초'%spread if spread else '')

def timed_invoke(adapter,job,context,inputs):
    # A story scene blocks every menu a job would open, so each job after it failed too.
    from owner_mission_controller import finish_scene
    finish_scene(adapter,context,inputs)
    try:return invoke(adapter,job,context,inputs)
    finally:
        # A job that gave up inside its menu (clan, 09:31) made every later job fail too.
        from owner_start_menu import normalize
        from project_adapter.town_services import TownServices
        try:normalize(TownServices(adapter,context,inputs,['버튼_나가기']))
        except RuntimeError as exc:LOG.info('일정 후 메뉴 정리 보류 · %s',exc)

def invoke(adapter,job,context,inputs):
    if job.key in ('shop','shop_weekly_verify'):
        from owner_shop_runtime_candidate import dispatch_configured
        from owner_schedule_priority import LOCAL as priority
        previous=getattr(priority,'feature',None);priority.feature='상점 구매'
        try:
            result=dispatch_configured(adapter,context,inputs)
            return result.get('status') in ('processed','no_selection','no_settings')
        finally:priority.feature=previous
    # Retain the original orchestrator's per-feature recovery/return logic.
    # Only the selected feature flags are exposed; no new UI handler is made.
    import inspect
    selected={job.setting}
    if job.key=='daily24_dungeon':
        # Its native loop can yield to bosses. Keep the user's existing
        # reservations visible for this potentially24-hour operation.
        selected.update(('auto_schedule.field_boss.enabled','auto_schedule.falling_battle.enabled','auto_schedule.artifact_charm.enabled'))
    if job.key=='gear':selected.update(('auto_growth.blessing.enabled','auto_growth.taoist.enabled'))
    old_values=adapter.values
    # Skill presets stay visible: the raid and boss entries read theirs while running.
    adapter.values={key:(value if not key.endswith('.enabled') or key in selected or '.skill_preset.' in key else False) for key,value in old_values.items()}
    due=adapter.get_due_schedules;had_due='get_due_schedules' in vars(adapter)
    adapter.get_due_schedules=due if job.key=='daily24_dungeon' else lambda:[]
    previous=getattr(LOCAL,'native_job',None);LOCAL.native_job=job.key
    old_mode=adapter.mode if job.key in AUTO_MODE_JOBS else None
    if old_mode is not None:adapter.mode='auto_mode'
    try:
        if (job.key=='gear' and adapter.values.get('auto_growth.taoist.enabled') is True
            and not any(adapter.values.get(key) is True for key in ('auto_growth.equipment.enabled','auto_growth.blessing.enabled'))):
            # The native orchestrator does not invoke growth when only the
            # taoist flag is set. Reuse the existing same-worker style path;
            # do not enable equipment or blessing as a side effect.
            from owner_skill_growth_candidate import dispatch_after_native
            return dispatch_after_native(adapter,context,inputs)
        native=inspect.unwrap(type(adapter)._run_auto_features)
        continue_actions=job.key in ('daily_missions','weekly_missions','clan_request','treasure','daily_dungeon','daily24_dungeon','weekly_dungeon','tower','raid')
        from owner_content_entry import invoke as content_entry
        result=content_entry(native,adapter,context,inputs,setting=job.setting,
                             wait_for_hunt=continue_actions,potion_done=True,periodic_wait=False)
        if job.key=='gear' and result is not False and adapter.values.get('auto_growth.taoist.enabled') is True:
            from owner_skill_growth_candidate import dispatch_after_native
            dispatch_after_native(adapter,context,inputs)
        return result
    finally:
        LOCAL.native_job=previous;adapter.values=old_values
        if old_mode is not None:adapter.mode=old_mode
        if had_due:adapter.get_due_schedules=due
        else:del adapter.get_due_schedules

def post_equip_growth(adapter,context,inputs,plan):
    """Dispatch a verified equip's follow-up on the current input worker.

    The durable receipt says only that an attempt was dispatched, not that
    any enhancement succeeded. User-disabled equipment and boss windows win.
    """
    import time as clock
    from owner_hunt_rules_candidate import configured_identity
    from owner_progression import state
    from owner_equipment_upgrade_candidate import Journal,Hold
    from owner_gear_settings_candidate import Store
    if plan.values.get('auto_growth.equipment.enabled') is not True:return False
    if clock.monotonic()<getattr(adapter,'_owner_post_equip_retry_at',0):return False
    root=adapter.project.root
    try:
        profile=configured_identity(root);progress=state(adapter)
        if not profile or not progress.character or not 0<=clock.monotonic()-progress.observed<=180:return False
        character=profile+'|'+progress.character;journal=Journal(root,character)
        if not journal.path.exists():return False
        request=journal.growth_request()
        if not request:return False
        targets=Store(root,profile).read()['grades']
        if targets[request.get('candidate_grade','희귀')].get('enabled') is not True:return False
        current=now();job=BY_KEY['gear']
        if fit(current,admission_budget(job,plan.values),busy_windows(plan.values,current,root=root))>current:return False
    except (Hold,ValueError,KeyError,TypeError,OSError) as exc:
        adapter._owner_post_equip_retry_at=clock.monotonic()+600
        LOG.warning('장착 후 장비 강화 요청 확인 필요 · %s',exc);return False
    old_values=adapter.values;adapter.values=dict(plan.values)
    # The existing gear job normally also admits blessing/style growth. This
    # follow-up requests only equipment and must honor the saved master flag.
    adapter.values['auto_growth.blessing.enabled']=False
    adapter.values['auto_growth.taoist.enabled']=False
    adapter._owner_post_equip_retry_at=clock.monotonic()+600
    try:
        context.checkpoint();adapter.exit_sleep_mode(context,inputs)
        adapter._owner_growth_pending_hold=False
        from owner_chore_transition import ancillary_field_ready
        if not ancillary_field_ready(adapter,context,inputs):return False
        LOG.info('장착 확인 후 장비 강화 점검 시작 · 부위=%s',request['slot'])
        result=invoke(adapter,job,context,inputs)
        context.checkpoint()
        if adapter.mode=='auto_mode' and adapter.run_favorite_hunt(context,inputs) is not True:
            raise RuntimeError('장비 강화 점검 후 사냥터 복귀 확인 필요')
        if result is not False and not getattr(adapter,'_owner_growth_pending_hold',False):
            latest=state(adapter)
            if configured_identity(root)==profile and latest.character==progress.character:
                journal.mark_growth_dispatched(request['growth_request_id'])
                LOG.info('장착 후 강화 작업 호출됨 · 실제 강화 결과 별도 확인 필요')
        return True
    finally:adapter.values=old_values

def idle_once(adapter,context,inputs):
    from owner_task_flow import LOCAL as task
    if getattr(task,'servicing',False):return False
    from owner_schedule_priority import hold_reason,LOCAL as priority_local
    if getattr(LOCAL,'job',None) or getattr(LOCAL,'native_job',None):return False
    if getattr(priority_local,'feature',None) or hold_reason(adapter):return False
    if character_mismatch(adapter):return False
    ui=getattr(adapter,'_owner_mission_ui',None)
    if ui is not None and ui.context is context and ui.inputs is inputs:
        from owner_emote_dispatch import navigation_open
        if navigation_open(ui):return False
    plan=planner(adapter);due=plan.due()
    if not due:return post_equip_growth(adapter,context,inputs,plan)
    job=due[0]
    if job.key=='gear' and plan.state[job.key].get('growth_recheck'):
        from owner_task_flow import LOCAL as task
        import time as clock
        observed=getattr(task,'quest_state',None)
        moving=bool(observed and observed[1]=='auto_move' and 0<=clock.monotonic()-observed[2]<5)
        if adapter.mode!='auto_mode' and not moving:return False
    if plan.reason(job.key):return False
    old_values=adapter.values;adapter.values=dict(plan.values)
    try:
        context.checkpoint();adapter.exit_sleep_mode(context,inputs)
        # The existing guarded wake handler normalizes field sleep first.
        # Black/unknown after wake still means no job begin/resource input.
        from owner_chore_transition import ancillary_field_ready
        if not ancillary_field_ready(adapter,context,inputs):return False
        LOG.info('시간표 실행 · %s · 예약=%s',job.label,plan.state[job.key]['at'])
        try:scheduled_call(lambda:invoke(adapter,job,context,inputs),job.label,(),{},adapter,timed_dispatch=True,run_context=context,run_inputs=inputs)
        except RuntimeError as exc:
            # A story scene opened over the album and the whole run ended (14:22). The job keeps its retry.
            # Only the plain error a job reports: subclasses unwind routes and stops.
            if type(exc) is not RuntimeError:raise
            context.checkpoint()
            LOG.warning('시간표 작업 미완료 · %s · %s · 이어서 진행',job.label,str(exc)[:120])
            from owner_start_menu import normalize
            from project_adapter.town_services import TownServices
            try:normalize(TownServices(adapter,context,inputs,['버튼_나가기']))
            except RuntimeError as closing:LOG.info('일정 후 메뉴 정리 보류 · %s',closing)
            return True
        context.checkpoint()
        if job.key in AUTO_MODE_JOBS and adapter.mode in ('main_quest','sub_quest'):
            # Same unwind as a world-boss return: the route loop reselects the saved quest.
            from owner_work_resume import ResumeWork
            LOG.info('시간표 작업 종료 · 이전 퀘스트로 복귀 · %s · %s',job.label,adapter.mode)
            raise ResumeWork(adapter.mode)
        if adapter.mode=='auto_mode' and adapter.run_favorite_hunt(context,inputs) is not True:
            raise RuntimeError('시간표 작업 후 기존 사냥터 복귀 확인 실패 · 진단이 필요합니다.')
        return True
    finally:adapter.values=old_values

def catch_up_overdue(adapter,context,inputs):
    """Started after a checked job's time: that job goes first, in schedule order.

    Each job still passes its own admission, boss-window and result checks. A job
    that fails here keeps its normal retry and never stops the start.
    """
    from owner_schedule_priority import hold_reason
    from owner_chore_transition import ancillary_field_ready,ChoreYield
    from owner_work_resume import ResumeWork
    if character_mismatch(adapter) or hold_reason(adapter):return []
    plan=planner(adapter);at=now();plan.due(at);ran=[]
    if not plan.cfg.get('enabled',True):return ran
    moved=False
    for job in JOBS:
        item=plan.state.get(job.key,{})
        if not enabled(job,plan.values) or item.get('status')!='pending' or item.get('incomplete_retry') or item.get('dungeon_failures'):continue
        base=preferred_base(job,plan.cfg,at,item['period'])
        if base is not None and base<=at<parse_at(item['at']):item['at']=at.isoformat();moved=True
    if moved:plan.commit()
    while True:
        due=[job for job in plan.due() if job.key not in ran]
        if not due:return ran
        job=due[0];ran.append(job.key)
        if plan.reason(job.key):continue
        context.checkpoint();adapter.exit_sleep_mode(context,inputs)
        if not ancillary_field_ready(adapter,context,inputs):return ran
        LOG.info('시작 일정 우선 처리 · %s · 예약 시간이 지나 먼저 실행',job.label)
        old_values=adapter.values;adapter.values=dict(plan.values)
        try:scheduled_call(lambda:timed_invoke(adapter,job,context,inputs),job.label,(),{},adapter,timed_dispatch=True,run_context=context,run_inputs=inputs)
        except (ResumeWork,ChoreYield):return ran
        except Exception as exc:
            context.checkpoint()
            LOG.warning('시작 일정 우선 처리 미완료 · %s · %s · 이어서 진행',job.label,str(exc)[:120])
        finally:adapter.values=old_values
        context.checkpoint()

def wrap_idle_wait(original_wait):
    @wraps(original_wait)
    def wait(adapter,context,inputs):
        original=context.wait;busy=False;last=0.
        import time as clock
        def tick(seconds):
            nonlocal busy,last
            end=clock.monotonic()+max(0,seconds)
            while True:
                original(min(1,max(0,end-clock.monotonic())))
                if not busy and clock.monotonic()-last>=2 and not getattr(context,'input_depth',0) and not getattr(inputs,'held',()):
                    last=clock.monotonic();context.checkpoint();busy=True
                    try:idle_once(adapter,context,inputs)
                    finally:busy=False
                if clock.monotonic()>=end:break
        try:context.wait=tick
        except (AttributeError,TypeError):
            LOG.warning('시간표 대기 연결 실패 · 자동 재검사가 연결되지 않았습니다. 진단 확인 필요')
            return original_wait(adapter,context,inputs)
        try:return original_wait(adapter,context,inputs)
        finally:context.wait=original
    return wait

def install(gui):
    if getattr(gui,'_owner_timetable_installed',False):return
    from project_adapter._entry import Adapter
    original_run=Adapter.run
    @wraps(original_run)
    def run(adapter,context,inputs):
        adapter._owner_timetable=Planner(adapter.project.root,adapter.values)
        return original_run(adapter,context,inputs)
    Adapter.run=run
    Adapter._wait_for_spirit_training=wrap_idle_wait(Adapter._wait_for_spirit_training);gui._owner_timetable_installed=True
    config(gui.project.root)
    LOG.info('일일·주간 시간표 준비 · 05시/수요일05시 초기화 · 랜덤 ±1분 · 보스 출발 시간 보호 · 같은 입력 스레드')
