"""Read-only schedule projection and durable receipts, never a game scheduler."""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone,time as daytime
from pathlib import Path
import hashlib,json,re,sqlite3,html,unicodedata
KST=timezone(timedelta(hours=9))

@dataclass(frozen=True)
class Item:
    key:str
    name:str
    group:str
    period:str
    setting:str=''
    execution:str='manual'
    calendar:str=''

ITEMS=(
 Item('events','출석·이벤트·무료 패스 보상','일일','day','auto_rewards.event.enabled','flow'),
 Item('mail','우편 보상','일일','day','auto_rewards.mail.enabled','flow'),
 Item('guide','길라잡이 보상','일일','day','auto_rewards.guide.enabled','flow'),
 Item('daily_quest','일일 임무 5개','일일','day','auto_schedule.daily_quest.enabled','flow'),
 Item('daily_dungeon','비경 기본시간 1시간','일일','day','auto_challenge.secret_exploration.enabled','flow'),
 Item('mangwi','만귀비경','일일','day',calendar='게임에서 입장 가능 여부·입장권 확인'),
 Item('raid','레이드·보상 티켓','일일','day','auto_schedule.boss_raid.enabled','flow'),
 Item('spirit','영기 수련','일일','day','auto_growth.spirit_training.enabled','interval'),
 Item('clan_training','문파 협력수련','일일','day','auto_growth.clan_cooperative_training.enabled','interval'),
 Item('daily_shop','잡화상점 설정 구매','일일','day',execution='flow'),
 Item('offline','종료 전 오프라인 사냥·물약','일일','day'),
 Item('weekly_quest','주간 임무 5개','주간','week','auto_schedule.weekly_quest.enabled','flow'),
 Item('weekly_dungeon','전래동화 비경 기본시간 5시간','주간','week','auto_challenge.secret_folktale_5h.enabled','flow'),
 Item('tower','승천의 탑','주간','week','auto_challenge.ascension_tower.enabled','flow'),
 Item('training_log','도사 수행록 보상','주간','week','auto_rewards.training_log.enabled','flow'),
 Item('yosin','문파 요신 토벌령','주간','week','auto_schedule.clan_boss_request.enabled','application'),
 Item('defense','문파 결계지 방어','주간','week','auto_schedule.clan_boss_request.enabled','application'),
 Item('weekly_shop','주간 교환·문파·낙화 상점','주간','week'),
 Item('weekly_shop_verify','설정한 주간 상품 최종 확인','주간','week',execution='flow'),
 Item('field_boss','월드보스','시간제','day','auto_schedule.field_boss.enabled','reservation','매일 21:00 / 입장 조건 확인'),
 Item('falling','낙화의 전장·요화선녀','시간제','day','auto_schedule.falling_battle.enabled','reservation','입장 조건 확인 · 요화선녀 22:00'),
 Item('falling_elite','낙화 암영 무도가','시간제','day',calendar='매일 22:30~23:30 / 성장 후 선택'),
 Item('artifact','금요일 신기 쟁탈전','시간제','week','auto_schedule.artifact_charm.enabled','reservation','금 14시 또는 20시 시간대 / 당일 08시 신청 마감'),
 Item('garden','토요일 미혹의 정원','시간제','week','auto_schedule.artifact_charm.enabled','reservation','토 14시 또는 20시 시간대 / 당일 08시 신청 마감'),
 Item('main','메인퀘스트','상시·성장','ongoing',execution='quest'),
 Item('sub','서사퀘스트','상시·성장','ongoing',execution='quest'),
 Item('hunt','일반 자동사냥','상시·성장','ongoing','common.potion_and_favorite.enabled','flow'),
 Item('folktale','전래동화 임무·진행 보상','상시·성장','ongoing','auto_schedule.folktale.enabled','flow'),
 Item('treasure','미수집 보물찾기','상시·성장','ongoing','auto_challenge.treasure_hunt.enabled','flow'),
 Item('album','화첩 보상','상시·성장','ongoing','auto_rewards.album.enabled','flow'),
 Item('achievement','업적 보상','상시·성장','ongoing','auto_rewards.achievement.enabled','flow'),
 Item('inventory','인벤토리 사용','상시·성장','ongoing','auto_rewards.inventory_use.enabled','flow'),
 Item('blessing','가호 소환','상시·성장','ongoing','auto_rewards.blessing.enabled','flow'),
 Item('gear','장비·가호·도술 강화 점검','상시·성장','ongoing','auto_growth.equipment.enabled','flow'),
 Item('growth','기운 발현·내면의 길','상시·성장','ongoing','auto_growth.energy.enabled','flow'),
 Item('season','시즌·기간한정 보상·교환','상시·성장','ongoing'),
 Item('daily24_dungeon','일일 비경·24시간','일일','day','auto_challenge.secret_exploration_always.enabled','flow'),
)
BY_KEY={i.key:i for i in ITEMS}
ALIASES={
 '이벤트':('events',),'우편':('mail',),'일일 임무':('daily_quest',),'주간 임무':('weekly_quest',),
 '비경탐험':('daily_dungeon',),'비경탐험(일일-24시간)':('daily24_dungeon',),'전래동화 비경':('weekly_dungeon',),'전래동화 비경(5시간)':('weekly_dungeon',),
 '보스 레이드':('raid',),'영기 수련':('spirit',),'문파 협력수련':('clan_training',),
 '승천의 탑':('tower',),'도사 수행록':('training_log',),'필드 보스':('field_boss',),
 '낙화의전장':('falling',),'낙화의 전장':('falling',),'신기/매혹':('artifact','garden'),
 '전래동화':('folktale',),'보물찾기':('treasure',),'화첩':('album',),'업적':('achievement',),
 '길라잡이':('guide',),'인벤토리 사용':('inventory',),'가호':('blessing',),
 '성장 장비·가호':('gear',),'기운 발현':('growth',),'내면의 길':('growth',),'사냥터 이동':('hunt',),
 '잡화상점 구매':('daily_shop',),
 '주간 상점 구매 확인':('weekly_shop_verify',),
 '문파 보스 신청':('yosin','defense','artifact','garden')}
NEGATIVE=re.compile(r'미입장|미완료|실패|미확인|확인 필요|결과 불명|재료 부족|미감지|찾지 못|시간 초과|시간초과|입력 생략|미등록|클릭 생략|상태 불명확')
LINE=re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?:,(\d{3}))?\s+(?:INFO|WARNING|ERROR)\s+(.*)$')

def now_kst():return datetime.now(KST)
def as_kst(value):return value.replace(tzinfo=KST) if value.tzinfo is None else value.astimezone(KST)
def iso(value):return as_kst(value).isoformat(timespec='milliseconds')
def game_day(value):return (as_kst(value)-timedelta(hours=5)).date()
def period_key(item,value):
    day=game_day(value)
    if item.period=='week':day-=timedelta(days=(day.weekday()-2)%7)
    return 'all' if item.period=='ongoing' else day.isoformat()

def parse_line(line):
    m=LINE.match(line)
    if not m:return None
    at=datetime.strptime(m[1],'%Y-%m-%d %H:%M:%S').replace(tzinfo=KST,microsecond=int(m[2] or 0)*1000)
    return at,m[3]

def events_for(at,message):
    """Generic native 'complete' is processed, never a game-clear receipt."""
    result=[]
    m=re.match(r'자동 기능 (시작|완료|처리 종료|부분 완료|부분 처리|미완료 재확인 대기|후속 대기|건너뜀|복구 중|보류) · (.*)',message)
    if m:
        phase,label=m.groups();ids=next((v for k,v in sorted(ALIASES.items(),key=lambda x:-len(x[0])) if label==k or label.startswith(k+' ·')),())
        kind={'시작':'attempt','완료':'processed','처리 종료':'processed','부분 완료':'partial','부분 처리':'partial',
              '미완료 재확인 대기':'partial','후속 대기':'partial','건너뜀':'skipped','복구 중':'failed','보류':'held'}[phase]
        if NEGATIVE.search(label):kind='partial'
        result.extend((key,kind,message) for key in ids)
    specific=[
      ('field_boss',r'필드.?보스.*(?:미입장|미완료|미감지|실패|시간.?초과)','failed'),
      ('tower',r'승천.*(?:미완료|입장 절차 미확인)','failed'),
      ('treasure',r'보물찾기.*(?:획득.*시간|부분 완료|미확인|수령.*실패)','partial'),
      ('clan_training',r'문파협력 예약 · (\d+)분\s*(\d+)초 후','plan'),
      ('spirit',r'영기 수련 일일 실행 (\d+)/(\d+)','progress'),
      ('spirit',r'^영기 수련 종료$','unit'),
      ('main',r'퀘스트 상태판정: mode=main_quest','attempt'),
      ('sub',r'퀘스트 상태판정: mode=sub_quest','attempt'),
      ('main',r'퀘스트 전투 보류 저장 · 모드=main_quest','held'),
      ('sub',r'퀘스트 전투 보류 저장 · 모드=sub_quest','held'),
      ('hunt',r'^사냥터 이동 및 절전 진입 완료','processed'),
    ]
    for key,pattern,kind in specific:
        if re.search(pattern,message):result.append((key,kind,message))
    for label,key in (('요신토벌령','yosin'),('결계지방어','defense'),('신기쟁탈전','artifact'),('미혹의정원','garden')):
        if message.startswith('문파 신청 · '+label):result.append((key,'partial',message))
    # Only explicit quota/boss reward receipts can assert a whole chore done.
    for key,pattern in (
        ('daily_quest',r'^일일 임무 남은 완료 가능 횟수 0\s*/\s*5 확인 · 전체 완료 확인$'),
        ('weekly_quest',r'^주간 임무 남은 완료 가능 횟수 0\s*/\s*5 확인 · 전체 완료 확인$'),
        ('daily_dungeon',r'^비경.*일일.*(?:기본시간 소진 확인|잔여시간 0초 확인)'),
        ('weekly_dungeon',r'^전래동화 비경.*주간.*(?:기본시간 소진 확인|잔여시간 0초 확인)'),
        ('field_boss',r'^필드 보스.*보상 수령 완료'),
        ('mangwi',r'^만귀비경.*보상 수령 완료')):
        if re.search(pattern,message) and not NEGATIVE.search(message):result.append((key,'confirmed',message))
    return list(dict.fromkeys(result))


class Book:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path),timeout=2)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=NORMAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS receipts (identity TEXT,item TEXT,period TEXT,event TEXT,at TEXT,kind TEXT,note TEXT,source TEXT,PRIMARY KEY(identity,item,event))')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (identity TEXT,item TEXT,period TEXT,body TEXT,PRIMARY KEY(identity,item,period))')
        # Earlier logs mistook remaining quota 5/5 for five completions.
        # Retain evidence and manual confirmations; invalidate only that
        # obsolete automatic interpretation so replay cannot restore it.
        bad=self.db.execute("SELECT DISTINCT identity,item,period FROM receipts WHERE item IN ('daily_quest','weekly_quest') AND kind='confirmed' AND note LIKE '%5/5%'").fetchall()
        for identity,item,period in bad:
            row=self.db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity,item,period)).fetchone()
            if row:
                body=json.loads(row[0]);body.pop('confirmed_at',None);body.pop('confirmed_source',None)
                if body.get('kind')=='confirmed':body['kind']='partial'
                body['quota_interpretation_corrected']=True
                self.db.execute('UPDATE state SET body=? WHERE identity=? AND item=? AND period=?',(json.dumps(body,ensure_ascii=False),identity,item,period))
            self.db.execute("UPDATE receipts SET kind='unverified_quota' WHERE identity=? AND item=? AND period=? AND kind='confirmed' AND note LIKE '%5/5%'",(identity,item,period))
        self.db.commit();self.dirty=False

    def get(self,identity,key,at):
        period=period_key(BY_KEY[key],at)
        if key=='album':
            # Keep the historical mixed album/achievement row untouched.
            current=self.db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity,'album-v2',period)).fetchone()
            old=self.db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity,'album',period)).fetchone()
            from legacy_album_projection import album_view
            old_receipts=self.db.execute("SELECT at,kind,note,source FROM receipts WHERE identity=? AND item=? AND period=? AND note LIKE '자동 기능 % · 화첩%' ORDER BY at",(identity,'album',period)).fetchall()
            raw=json.loads(old[0]) if old else {}
            if old_receipts:
                raw=dict(raw);raw['history']=[{'at':at,'kind':kind,'note':note,'source':source} for at,kind,note,source in old_receipts]
            legacy,warning=album_view(raw) if raw else ({},'')
            state=json.loads(current[0]) if current else legacy
            if warning:state['legacy_warning']=warning
            if legacy.get('legacy_manual_at'):state['legacy_manual_at']=legacy['legacy_manual_at']
            return state
        row=self.db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity,key,period)).fetchone()
        return json.loads(row[0]) if row else {}

    def apply(self,identity,key,kind,at,note='',source='실행 로그'):
        if key not in BY_KEY:return
        stamp=iso(at);period=period_key(BY_KEY[key],at);storage_key='album-v2' if key=='album' else key
        event=hashlib.sha256((stamp+'|'+kind+'|'+note).encode()).hexdigest()
        # Replaying a receipt already stored under the legacy combined key
        # must not create a second physical receipt. Legacy projection reads
        # that exact album evidence in place without changing it.
        if key=='album' and source.startswith('기존 PC 로그') and self.db.execute('SELECT 1 FROM receipts WHERE identity=? AND item=? AND event=?',(identity,'album',event)).fetchone():return
        inserted=self.db.execute('INSERT OR IGNORE INTO receipts VALUES (?,?,?,?,?,?,?,?)',(identity,storage_key,period,event,stamp,kind,note[:350],source)).rowcount
        if not inserted:return
        self.dirty=True
        if key=='album':
            row=self.db.execute('SELECT body FROM state WHERE identity=? AND item=? AND period=?',(identity,storage_key,period)).fetchone()
            state=json.loads(row[0]) if row else {}
        else:state=self.get(identity,key,at)
        if state.get('last_at','')>stamp:return
        old_kind=state.get('kind')
        if kind=='attempt':state['attempt_at']=stamp;state['veto']=False;state.pop('hold_note',None)
        if kind in ('failed','partial','held'):state['veto']=True;state['hold_note']=note[:350]
        if kind=='processed':state['processed_at']=stamp
        if kind=='unit':state['unit_at']=stamp
        if kind=='confirmed':state['confirmed_at']=stamp;state['confirmed_source']=source
        if kind=='manual':state['manual_at']=stamp
        if kind=='unmark':state.pop('manual_at',None)
        if kind=='progress':
            m=re.search(r'실행 (\d+)/(\d+)',note)
            if m:state['progress']=[int(m[1]),int(m[2])]
        if kind=='plan':
            m=re.search(r'(\d+)분\s*(\d+)초 후',note)
            if m:state['planned_at']=iso(at+timedelta(minutes=int(m[1]),seconds=int(m[2])))
        # A later generic end must not hide an earlier failed admission.
        effective=((old_kind if old_kind in ('held','failed') else 'partial') if state.get('veto') and kind in ('processed','unit') else kind)
        if kind in ('progress','plan'):effective=old_kind or kind
        state.update(last_at=stamp,kind=effective,note=note[:350],source=source)
        state['history']=(state.get('history',[])+[{'at':stamp,'kind':kind,'note':note[:240],'source':source}])[-6:]
        self.db.execute('INSERT OR REPLACE INTO state VALUES (?,?,?,?)',(identity,storage_key,period,json.dumps(state,ensure_ascii=False)))
        self.dirty=True

    def ingest(self,identity,at,message,source='실행 로그'):
        for key,kind,note in events_for(at,message):self.apply(identity,key,kind,at,note,source)

    def flush(self):
        if self.dirty:self.db.commit();self.dirty=False
    def close(self):self.flush();self.db.close()


STATUS={'attempt':'진행 시도','processed':'처리 종료·완료 미확인','partial':'부분 처리·확인 필요',
        'failed':'실패·확인 필요','skipped':'건너뜀','held':'보류','progress':'진행 기록 있음','unit':'수련 회차 종료',
        'manual':'완료·사용자 확인','confirmed':'완료 확인','plan':'예약 기록 있음','unmark':'미확인',
        'legacy_mission_ambiguous':'과거 일일·주간 통합 기록·개별 처리 미확인'}

def project_legacy_mission(key,state):
    """Project old ambiguous generic records only; never rewrite the ledger."""
    if key not in ('daily_quest','weekly_quest'):return state
    if state.get('kind') not in ('attempt','processed','partial','skipped','failed','held'):return state
    if not re.match(r'^자동 기능 (?:시작|완료|부분 완료|건너뜀|복구 중|보류) · 일일·주간 임무(?:$| ·)',state.get('note','')):return state
    view=dict(state)
    view['kind']='legacy_mission_ambiguous'
    view['legacy_warning']='과거 통합 로그로 어느 임무가 실제 처리됐는지 확인할 수 없음'
    if view.get('processed_at')==view.get('last_at'):view.pop('processed_at',None)
    return view

def state_label(state):
    kind=state.get('kind');label=STATUS.get(kind,'기록 없음·미확인')
    if kind not in ('held','failed','partial'):return label,state.get('note','')
    reason=state.get('hold_note','')
    if not reason:
        reason=next((h.get('note','') for h in reversed(state.get('history',[])) if h.get('kind') in ('held','failed','partial')),state.get('note',''))
    if kind=='held':
        if '시간표 처리 종료' in reason:label='이번 주기 처리됨'
        elif '시간표' in reason or '예약' in reason:label='예약 대기'
        else:label='조건 확인 필요'
    return label,reason

def display_time(stamp,at):
    if not stamp:return '—'
    value=datetime.fromisoformat(stamp)
    return value.strftime('%H:%M:%S') if value.date()==as_kst(at).date() else value.strftime('%m/%d %H:%M')

def scheduled_time(item,root,when):
    if item.key in ('artifact','garden'):
        # The six possible slots are not the clan's selected appointment.
        # Reuse upstream's complete record validator, never invent20:20.
        try:
            from project_adapter.clan_boss_request import CombatSchedule
            data=json.loads((Path(root)/'settings/clan-combat-schedule.json').read_text(encoding='utf-8-sig'))
            CombatSchedule.valid(data)
            value=data['events'].get('신기쟁탈전' if item.key=='artifact' else '미혹의정원',{})
            at=datetime.fromisoformat(value['start_at'])
            if value.get('status')=='pending' and at>=as_kst(when):return ('at',at,None)
        except (OSError,ValueError,KeyError,TypeError,ImportError):pass
        return None
    mapping={'field_boss':'auto_schedule.field_boss','falling':'auto_schedule.falling_battle','artifact':'auto_schedule.artifact_charm','garden':'auto_schedule.artifact_charm'}
    try:
        schedules=json.loads((Path(root)/'profiles/DKB/config/server-schedule.json').read_text(encoding='utf-8'))['schedules']
        spec=next(x for x in schedules if x['id']==mapping[item.key])
        time_text=spec.get('window_start') or spec.get('time')
        if not time_text:return None
        clock=daytime.fromisoformat(time_text)
        day=as_kst(when).date()
        wanted=(4,) if item.key=='artifact' else (5,) if item.key=='garden' else spec.get('weekdays',range(7))
        for n in range(8):
            candidate=datetime.combine(day+timedelta(days=n),clock,tzinfo=KST)
            if candidate.weekday() not in wanted:continue
            if item.key=='field_boss':
                try:delay=json.loads((Path(root)/'settings/field-boss-entry-state.json').read_text(encoding='utf-8'))['delays'].get(candidate.date().isoformat())
                except (OSError,ValueError,KeyError):delay=None
                if delay is not None:candidate+=timedelta(seconds=int(delay))
                else:
                    end=spec.get('window_end')
                    if candidate<as_kst(when) and (not end or datetime.combine(candidate.date(),daytime.fromisoformat(end),tzinfo=KST)<as_kst(when)):continue
                    return ('window',candidate,end)
            if candidate>=as_kst(when):return ('at',candidate,None)
        return None
    except (OSError,ValueError,KeyError,TypeError,StopIteration):return None

def next_plan(item,state,values,status,root,when,selected_mode,priority=None):
    if item.key in ('daily_shop','weekly_shop_verify'):
        from owner_timetable import shop_selection_enabled
        if not shop_selection_enabled(root):return '상점 구매 미선택 또는 설정 확인 필요'
    if item.key=='gear':
        from owner_timetable import enabled,BY_KEY as TIME_JOBS
        if not enabled(TIME_JOBS['gear'],values):return '사용 안 함'
    elif item.setting and not values.get(item.setting,False):return '사용 안 함'
    if item.execution=='manual':return '직접 진행 필요·자동 예정 없음'
    if item.execution=='application':
        from owner_timetable import appointment
        value=appointment(root,item.key,when,values=values)
        return (value+' · 신청만 자동·실제 전투는 문파 일정') if value else '신청만 자동 지원·실제 참여는 문파 일정 확인'
    if item.execution=='quest':return '선택 모드 재개 후 판단' if selected_mode in ('main_quest','sub_quest') else '현재 자동모드·퀘스트 실행 예정 없음'
    if item.execution=='reservation':
        plan=scheduled_time(item,root,when)
        if not plan:return '문파 전투 시간 미확인 · 신청 후 판독 대기' if item.key in ('artifact','garden') else '게임 일정 확인·프로그램 예약 시각 없음'
        tag,at,end=plan
        text=display_time(iso(at),when)
        text=(f'프로그램 예약창 {text}~{end}' if tag=='window' else '프로그램 예약 '+text)
        if status!='running':text+=' · 실행/재개 필요'
        if item.key in ('artifact','garden'):text+=' · 문파 선택 시간과 대조 필요'
        return text
    if state.get('manual_at') or state.get('confirmed_at'):
        if item.key=='treasure':return '일회성 · 완료 확인 · 반복 없음'
        if item.period=='ongoing':return '다음 성장·새 보상 때 확인'
        reset=game_day(when)+timedelta(days=1)
        if item.period=='week':reset=datetime.fromisoformat(period_key(item,when)).date()+timedelta(days=7)
        return reset.strftime('%m/%d')+' 05:00 초기화 이후 자동 순환'
    if status!='running':return '재개 후 자동 순서 대기' if status=='paused' else '시작 후 자동 순서 대기'
    if priority:return priority+' · 종료 후 다음 자동 순환'
    from owner_timetable import appointment
    value=appointment(root,item.key,when,values=values)
    if value:return value
    if item.execution=='interval':
        if state.get('planned_at'):
            at=datetime.fromisoformat(state['planned_at'])
            if at>=as_kst(when):return '예약 '+display_time(state['planned_at'],when)
        if item.key=='spirit' and state.get('unit_at'):
            try:minutes=int(values.get('auto_growth.spirit_training.interval_minutes',10))
            except (ValueError,TypeError):minutes=10
            at=datetime.fromisoformat(state['unit_at'])+timedelta(minutes=minutes)
            if at>=as_kst(when):return '예상 '+display_time(iso(at),when)+' · 설정 주기 기준'
        return '다음 수련 주기 · 게임 내 사용 가능 조건 확인'
    cooldown={'events':300,'mail':180,'album':300}.get(item.key)
    if cooldown and state.get('processed_at'):
        eligible=datetime.fromisoformat(state['processed_at'])+timedelta(seconds=cooldown)
        if eligible>as_kst(when):return '최소 '+display_time(iso(eligible),when)+' 이후 · 다음 자동 순환'
    if item.key=='gear':return '다음 이동·사냥 틈 · 메인은 20/30/40/45레벨 점검'
    if state.get('attempt_at'):return '다음 자동 순환 때 재확인'
    return '현재 작업 종료 후 자동 순서'

def project(book,identity,root,model,status,when=None):
    when=as_kst(when or now_kst());values=model.get('values',{});rows=[]
    from owner_schedule_priority import reservation_hold
    priority=reservation_hold(root,values,when)
    task=model.get('runtime_task','')
    if status=='running' and any(label in task for label in ('필드 보스','월드보스','보스 레이드','낙화','승천의 탑')) and '대기' not in task:
        priority='보스·특수 전투 진행 중'
    for item in ITEMS:
        from owner_reward_context import JOBS as reward_jobs
        if item.key in reward_jobs:continue
        state=project_legacy_mission(item.key,book.get(identity,item.key,when))
        manual=state.get('manual_at');verified=state.get('confirmed_at')
        outcome,reason=state_label(state)
        if verified:outcome='완료 확인'
        if manual:outcome='완료·사용자 확인'
        if item.key=='spirit' and state.get('progress') and not manual:
            outcome+=' · 실행 %d/%d'%tuple(state['progress'])
        rows.append({'id':item.key,'name':item.name,'group':item.group,'period':period_key(item,when),
            'status':outcome,'last_at':display_time(state.get('last_at'),when),
            'completed_at':display_time(manual or verified,when),
            'unit_at':display_time(state.get('unit_at'),when),
            'next':next_plan(item,state,values,status,root,when,model.get('mode','auto_mode'),priority),
            'calendar':item.calendar,'note':((reason or state.get('note','기록 없음'))+(' · '+state['legacy_warning'] if state.get('legacy_warning') else '')),
            'source':state.get('source',''),'history':state.get('history',[]),
            'verified':bool(manual or verified)})
    return {'generated_at':iso(when),'day':game_day(when).isoformat(),
            'week':period_key(BY_KEY['weekly_quest'],when),'identity':identity,'status':status,'rows':rows,
            'notice':'완료 확인과 처리 종료는 다릅니다. 사용자 확인 시각은 실제 완료 시각과 다를 수 있습니다. 기존 로그 복원은 현재 설정 캐릭터의 실제 플레이였는지 미검증입니다.'}

SHORT_NAMES={
    'events':'출석·이벤트','mail':'우편','guide':'길라잡이','daily_quest':'일일 임무',
    'daily_dungeon':'일일 비경','mangwi':'만귀비경','raid':'레이드','spirit':'영기 수련',
    'clan_training':'문파 수련','daily_shop':'일일 상점','offline':'오프라인',
    'weekly_quest':'주간 임무','weekly_dungeon':'주간 비경','tower':'승천의 탑',
    'training_log':'수행록','yosin':'요신 토벌','defense':'결계 방어','weekly_shop':'주간 상점','weekly_shop_verify':'주간 구매 확인',
    'field_boss':'월드보스','falling':'낙화 전장','falling_elite':'암영 무도가',
    'artifact':'신기 쟁탈','garden':'미혹 정원','main':'메인퀘','sub':'서사퀘',
    'hunt':'자동사냥','folktale':'전래동화','treasure':'보물찾기','album':'화첩',
    'achievement':'업적','inventory':'인벤토리','blessing':'가호 소환',
    'gear':'장비·가호·도술','growth':'기운·내면','season':'시즌 보상','daily24_dungeon':'24h 비경',
}

class TelegramTable(str):
    telegram_html=True

def cell(value,width):
    text='';used=0
    for ch in str(value):
        size=2 if unicodedata.east_asian_width(ch) in 'WF' else 1
        if used+size>width:break
        text+=ch;used+=size
    return text+' '*(width-used)

def short_status(row):
    if row['verified']:return '완료'
    label=row['status']
    for needle,short in (('실패','실패'),('부분','부분'),('보류','보류'),('건너뜀','건너뜀'),('처리 종료','처리*'),('진행 시도','시도'),('수련 회차','회차'),('기록 없음','미확인')):
        if needle in label:return short
    return '확인중'

def short_next(row):
    text=row['next']
    if text=='사용 안 함':return '꺼짐'
    if '직접 진행' in text:return '직접 진행'
    if text.startswith('일회성'):return '일회성'
    if '예약 보호' in text or '진행 중 · 종료' in text:return '보스 뒤'
    if '재개 후' in text or '시작 후' in text or '실행/재개' in text:return '재개 후'
    dated=re.search(r'\d\d/\d\d \d\d:\d\d',text)
    if dated:return dated[0]
    if '초기화' in text:return '초기화 후'
    if '최소 ' in text:return re.search(r'\d\d:\d\d',text)[0]+'~'
    if text.startswith(('예상 ','예정 ','예약 ','프로그램 예약')):
        times=re.search(r'(\d\d/\d\d )?\d\d:\d\d',text)
        if times:return times[0] if len(times[0])<=10 else times[0][:5]+' 예약'
        return '예약 확인'
    if '지연' in text:return '앞 일정 뒤'
    if '시간표 작업 진행' in text:return '진행 중'
    if '신청만' in text:return '문파 일정'
    if '퀘스트 실행 예정 없음' in text:return '모드 꺼짐'
    if '레벨 점검' in text:return '레벨 조건'
    if '사용 가능 조건' in text:return '사용 가능시'
    if '다음 성장' in text:return '성장 후'
    return '다음 순환'

def telegram_pages(snapshot,group='전체'):
    """Narrow mobile tables, one group per message. HTML only for our output."""
    pages=[]
    for section in ('일일','주간','시간제','상시·성장'):
        if group not in ('전체',section):continue
        rows=[r for r in snapshot['rows'] if r['group']==section]
        if not rows:continue
        status={'running':'실행 중','paused':'일시정지','stopped':'중지','error':'오류'}.get(snapshot['status'],snapshot['status'])
        title='DKB · %s 일정\n%s · %s\n'%(section,snapshot['day'],status)
        lines=[cell('콘텐츠',12)+' '+cell('상태',6)+' '+cell('시각',5)+' '+cell('다음',12),'─'*38]
        notes=[]
        for row in rows:
            stamp=row['completed_at'] if row['verified'] else row['last_at']
            stamp=stamp[:5]
            lines.append(cell(SHORT_NAMES[row['id']],12)+' '+cell(short_status(row),6)+' '+cell(stamp,5)+' '+cell(short_next(row),12))
            if ('최소 ' in row['next'] or '예약' in row['next'] or '초기화' in row['next']) and '보호' not in row['next']:
                notes.append(SHORT_NAMES[row['id']]+': '+row['next'])
        footer='\n시각: 완료 확인 / 미완료는 최근 진행 (이전 날은 월/일)\n처리*: 처리 종료, 완료 여부는 미확인\n다음 순환: 현재 작업 종료 후 순서대로 재확인'
        if section=='일일':footer+='\n~: 재확인 가능한 최소 시각, 보스 중에는 연기'
        if notes:footer+='\n'+'\n'.join(dict.fromkeys(notes))
        if snapshot.get('issue'):footer+='\n주의: '+snapshot['issue']
        if snapshot.get('dropped'):footer+='\n수집 누락: '+str(snapshot['dropped'])+'건'
        pages.append(TelegramTable(html.escape(title)+'<pre>'+html.escape('\n'.join(lines))+'</pre>'+html.escape(footer)))
    return pages
