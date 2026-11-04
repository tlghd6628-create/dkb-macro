"""One real run of a dungeon, boss or training feature from its settings row.

Each TEST reaches the same native entry as normal play on the ordinary Session,
and nothing here clicks. The raid stops at the match button so no ticket is spent.
No timetable receipt is written and settings on disk stay as saved.
"""
import inspect,logging,re,threading

LOG=logging.getLogger('project_gui.DKB')
DISPATCH,DIRECT,RAID='dispatch','direct','raid'
GROWTH,STYLE,ALBUM,BLESSING,PRESET='growth','style','album','blessing','preset'
TARGETS={
 'auto_schedule.boss_raid.skill_preset.enabled':('레이드 단일 덱 구성',PRESET),
 'auto_rewards.blessing.enabled':('가호 보상·장착',BLESSING),
 'auto_growth.equipment.enabled':('장비 성장',GROWTH),
 'auto_growth.blessing.enabled':('가호 성장',GROWTH),
 'auto_growth.energy.enabled':('기운 발현',GROWTH),
 'auto_growth.taoist.enabled':('도술 성장',STYLE),
 'auto_rewards.album.enabled':('화첩',ALBUM),
 'auto_schedule.daily_quest.enabled':('일일 퀘스트',DISPATCH),
 'auto_schedule.weekly_quest.enabled':('주간 퀘스트',DISPATCH),
 'auto_challenge.ascension_tower.enabled':('승천의 탑',DISPATCH),
 'auto_schedule.field_boss.enabled':('월드보스',DIRECT),
 'auto_schedule.falling_battle.enabled':('낙화의 전장',DISPATCH),
 'auto_schedule.folktale.enabled':('전래동화 임무',DISPATCH),
 'auto_schedule.artifact_charm.enabled':('신기/매혹',DIRECT),
 'auto_schedule.boss_raid.enabled':('보스 레이드',RAID),
 'auto_challenge.secret_exploration.enabled':('비경탐험',DISPATCH),
 'auto_challenge.secret_exploration_always.enabled':('일일 24시간 비경',DISPATCH),
 'auto_challenge.secret_folktale_5h.enabled':('전래동화 비경 5시간',DISPATCH),
 'auto_challenge.secret_folktale.enabled':('전래동화 비경 24시간',DISPATCH),
 'auto_growth.spirit_training.enabled':('영기수련',DISPATCH),
}
# Log text that says the native run ended without doing its work.
NOT_DONE=re.compile('건너뜀|보류|미완료|진입 불가|티켓 없음|생략|실패|미감지|미확인')

def visible(message,*args):
    text=message%args if args else message
    LOG.info(text,extra={'gui_message':text,'state_transition':True})

class Reasons(logging.Handler):
    """The last native line on this worker that explains an unfinished run."""
    def __init__(self):super().__init__();self.thread=threading.get_ident();self.last=None
    def emit(self,record):
        if record.thread!=self.thread:return
        text=record.getMessage()
        if record.levelno>=logging.INFO and NOT_DONE.search(text) and not text.startswith('실전 TEST'):self.last=text

def only(values,key):
    """Just this switch. Skill presets stay, because their entries read them."""
    shown={k:(v if not k.endswith('.enabled') or '.skill_preset.' in k else False) for k,v in values.items()}
    shown[key]=True
    return shown

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
    # Combat effects can spoil one frame while hunting, so look again briefly.
    # Two matching field frames are still what allows the entry.
    kinds=[]
    for index in range(12):
        context.checkpoint();service.check()
        kinds.append(scene(service.detector,service.capture()))
        if len(kinds)>=2 and kinds[-1]==kinds[-2]:
            if kinds[-1] in ('field','inventory'):return
            # A loot banner while hunting reads as a receipt for a few seconds.
            if kinds[-1] not in ('unknown','treasure_receipt'):break
        context.wait(.25)
    raise RuntimeError('필드에서 눌러 주세요 · 비경·보스 안에서는 새로 입장하지 않습니다 · 판독 '+','.join(dict.fromkeys(kinds)))

class AtMatchButton(BaseException):pass

def preview_flow(raid):
    blocked=frozenset((raid.MATCH,raid.CONFIRM,raid.CONFIRM2,raid.BULK,raid.BULK2))
    class Preview(raid.RaidFlow):
        """The native menu walk; the first commit button ends it unpressed."""
        def press(self,name,seconds=3,post=1,*,alternatives=()):
            if name in blocked or blocked.intersection(alternatives):
                self.detect(name,seconds,alternatives=alternatives)
                raise AtMatchButton()
            return super().press(name,seconds,post,alternatives=alternatives)
        def click(self,name,hit):
            if name in blocked:raise AtMatchButton()
            return super().click(name,hit)
    return Preview

def raid_preview(adapter,context,inputs):
    import project_adapter.boss_raid as raid
    match=re.fullmatch(r'([1-5])단계',str(adapter.values.get('auto_schedule.boss_raid.stage','')))
    if not match:raise RuntimeError('보스 레이드 단계 설정 확인 필요')
    flow=preview_flow(raid)(adapter,context,inputs)
    try:flow.entry(int(match[1]))
    except AtMatchButton:
        flow.leave()
        return '입장 직전 확인 · 매칭 안 누름'
    except raid.RaidPending as exc:
        # Such as no ticket: nothing to enter, but the raid menu is still open.
        flow.leave()
        raise RuntimeError(str(exc)) from exc
    flow.leave()
    return None

def raid_real(adapter,context,inputs):
    """A real entry at the saved stage, always once, whatever the saved entry count."""
    import project_adapter.boss_raid as raid
    match=re.fullmatch(r'([1-5])단계',str(adapter.values.get('auto_schedule.boss_raid.stage','')))
    if not match:raise RuntimeError('보스 레이드 단계 설정 확인 필요')
    flow=raid.RaidFlow(adapter,context,inputs);flow._owner_one_entry=True
    try:return flow.run(int(match[1]),False)
    except raid.RaidPending as exc:raise RuntimeError(str(exc)) from exc

def dispatch(adapter,context,inputs,key):
    """The native dispatcher, as a timed job runs it; it reads these switches only in auto_mode."""
    native=inspect.unwrap(type(adapter)._run_auto_features)
    old=adapter.get_due_schedules;had='get_due_schedules' in vars(adapter)
    adapter.get_due_schedules=lambda:[];mode=adapter.mode;adapter.mode='auto_mode'
    try:
        from owner_content_entry import invoke
        return invoke(native,adapter,context,inputs,setting=key,wait_for_hunt=True,potion_done=True,periodic_wait=False)
    finally:
        adapter.mode=mode
        if had:adapter.get_due_schedules=old
        else:del adapter.get_due_schedules

def direct(adapter,context,inputs,key):
    """These two run by the clock in normal play, not from the dispatcher."""
    if key=='auto_schedule.field_boss.enabled':return adapter.run_field_boss_entry(context,inputs)
    import project_adapter.clan_boss_request as clan
    return clan.run_clan_boss_request(adapter,context,inputs,combat=True)

def growth(adapter,context,inputs,key):
    """The native growth steps, as a timed job runs them, spending up to the saved goals."""
    kind=TARGETS[key][1]
    if kind==ALBUM:
        # A running macro has already read who is playing; this TEST has not.
        from owner_quest_preflight import read_power
        read_power(adapter,context,inputs)
        return adapter.run_album_rewards(context,inputs)
    if kind==PRESET:
        from owner_quest_preflight import read_power
        from owner_single_preset import configure
        read_power(adapter,context,inputs)
        return configure(adapter,context,inputs)
    if kind==BLESSING:
        # The priority equip runs inside the reward job, so this is the one way to see it.
        from owner_quest_preflight import read_power
        read_power(adapter,context,inputs)
        result=adapter.run_blessing_rewards(context,inputs)
        state=getattr(adapter,'_owner_blessing_policy_outcome',None)
        visible('가호 장착 결과 · %s',state)
        return result
    if kind==STYLE:
        # The native dispatcher does not reach style growth on this switch alone.
        from owner_skill_growth_candidate import dispatch_after_native
        result=dispatch_after_native(adapter,context,inputs)
        state=(getattr(adapter,'_owner_style_growth_outcome',None) or {})
        if state.get('state')=='held':return '보류 · '+str(state.get('reason'))
        if state.get('statuses') is not None:return '처리 · '+' / '.join(str(row) for row in state['statuses'])[:200]
        return result
    adapter._owner_growth_pending_hold=False;adapter._owner_energy_outcome=None
    native=inspect.unwrap(type(adapter)._run_auto_features)
    old=adapter.get_due_schedules;had='get_due_schedules' in vars(adapter)
    adapter.get_due_schedules=lambda:[]
    try:result=native(adapter,context,inputs,wait_for_hunt=False,potion_done=True,periodic_wait=False)
    finally:
        if had:adapter.get_due_schedules=old
        else:del adapter.get_due_schedules
    if key=='auto_growth.equipment.enabled':
        # The growth list leaves out finished worn items, so the table is filled from their tooltips.
        from owner_worn_stats import inspect_equipped,FULL_SECONDS
        adapter._owner_worn_resume=None
        inspect_equipped(adapter,context,inputs,max_seconds=FULL_SECONDS)
    if getattr(adapter,'_owner_growth_pending_hold',False):return '보류 · 실행 로그 확인'
    return result

def execute(adapter,context,inputs,key):
    from owner_timetable import LOCAL
    from owner_work_resume import ResumeWork
    kind=TARGETS[key][1];before=adapter.values;adapter.values=only(before,key)
    previous=getattr(LOCAL,'native_job',None);LOCAL.native_job=key
    try:
        if kind==RAID:return raid_real(adapter,context,inputs)
        if kind in (GROWTH,STYLE,ALBUM,BLESSING,PRESET):return growth(adapter,context,inputs,key)
        return dispatch(adapter,context,inputs,key) if kind==DISPATCH else direct(adapter,context,inputs,key)
    except ResumeWork:return None  # a boss return to the selected work; a TEST just ends here
    finally:LOCAL.native_job=previous;adapter.values=before

def outcome_text(result,reason):
    if isinstance(result,str):return result
    if result is False:return '실패 · '+(reason or '실행 로그 확인')
    return '종료 · '+reason if reason else '처리 종료 · 실행 로그 확인'

class OneRun:
    """An adapter delegate, owned and closed by the ordinary Session worker."""
    def __init__(self,adapter,key,ready,events):
        self.adapter,self.key,self.ready,self.events=adapter,key,ready,events
    def __getattr__(self,name):return getattr(self.adapter,name)
    def close(self):return self.adapter.close()
    def run(self,context,inputs):
        label=TARGETS[self.key][0];reasons=Reasons();LOG.addHandler(reasons)
        try:
            if self.ready is not None:self.ready.wait(context)
            context.checkpoint()
            visible('실전 TEST 시작 · %s',label)
            from owner_scene_archive import capture_scope
            with capture_scope(self.adapter,context,source='challenge_test'):
                prepare(self.adapter,context,inputs)
                result=execute(self.adapter,context,inputs,self.key)
            # A native return alone proves neither a clear nor a full hunt.
            text=outcome_text(result,reasons.last)
            visible('실전 TEST 결과 · %s · %s',label,text)
            self.events.put((text,None))
        except BaseException as exc:
            from biol_base.session import Cancelled
            text='중지됨' if isinstance(exc,Cancelled) else '실패 · '+str(exc)
            visible('실전 TEST 결과 · %s · %s',label,text)
            self.events.put((text,str(exc)))
            raise
        finally:LOG.removeHandler(reasons)

def start(gui,key,result):
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
            from owner_content_entry import prepare_test_window
            prepare_test_window(gui)
            factory=session.adapter_factory
            ready=getattr(gui,'_owner_ocr_readiness',None)
            runner.active=True
            def one_adapter():
                outer=factory()
                if not isinstance(outer,PolicyAdapter):
                    outer.close()
                    raise RuntimeError('기존 실행 정책 연결 확인 필요 · 입력 없음')
                outer.adapter=OneRun(outer.adapter,key,ready,runner.events)
                return outer
            session.adapter_factory=one_adapter
            try:session.start()
            finally:session.adapter_factory=factory
        result.set('실행 중');gui.root.after(100,lambda:runner.poll(result))
        return True
    except Exception as exc:
        runner.active=False;result.set(str(exc));visible('실전 TEST 준비 실패 · %s',exc);return False
