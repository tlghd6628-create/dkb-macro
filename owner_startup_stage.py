"""Start/resume from the observed scene on the existing input-owning worker."""
from functools import wraps
from pathlib import Path
import json,logging,re,sys,threading,time
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
DUNGEON='체크_던전진행중';EXIT='버튼_던전_나가기';MENU='버튼_전체매뉴'

class RecheckStage(BaseException):pass

def parse_timer(pages):
    found=set()
    for p in pages:
        for text,score in zip(p.get('rec_texts',()),p.get('rec_scores',())):
            m=re.fullmatch(r'\s*(\d{2}):(\d{2}):(\d{2})\s*',str(text))
            if m and float(score)>=.94:
                h,n,s=map(int,m.groups())
                if h<=24 and n<60 and s<60 and (h<24 or n==s==0):found.add(h*3600+n*60+s)
    return next(iter(found)) if len(found)==1 else None

SLEEP='체크_절전모드중'

def known_dialog(slots,first,second):
    # The top-right skip button stays visible behind the confirm dialog, so confirm is checked first.
    return next((key for key in ('skip_confirm','skip_confirm2','skip') if slots.match(key,first).get('hit') and slots.match(key,second).get('hit')),None)

def press_dialog(adapter,context,inputs,service,slots,key,frame):
    """The one place that answers a scene's skip controls, at the start and before reading power."""
    from project_adapter.main_quest import BoundedMainQuestRunner,dependencies
    _,deps=dependencies(adapter,context,inputs)
    runner=BoundedMainQuestRunner(slots,**deps);hit=slots.match(key,service.capture())
    if not hit.get('hit'):return False
    LOG.info('시작 화면 · 알려진 대화 넘기기 처리 · %s',key)
    if key=='skip':runner.handle_skip(slots.by_key[key],hit,frame)
    elif key=='skip_confirm2':runner.handle_skip_confirm2(slots.by_key[key],hit,frame)
    else:runner.input_one(key,hit,frame)
    return True

SLEEP_WORDS=(450,115,470,45)  # real pixels: 화면 중앙을 밀어서 절전 해제

def sleep_screen(service,adapter,frame):
    """The sleep screen says so. Its small icon scores under the old line once scaled down (16:38)."""
    if getattr(frame,'hi',None) is None:return bool(service.detector.find(SLEEP,frame,threshold=.95))
    from owner_text import find,read
    return bool(find(read(adapter.project.root,frame,SLEEP_WORDS,bright=True),'절전 해제'))

def slide_awake(adapter,context,inputs):
    """Middle of the screen to the upper right, which is what wakes the game at 1366x768 (tried by hand, 16:40)."""
    from owner_skill_ui import SkillUI
    SkillUI(adapter,context,inputs).drag((448,240),(790,75),lambda f:True);context.wait(2)

def guide_visible(adapter,first,second):
    from tutorial_highlight import load_config,detect_tutorial_highlight
    config=load_config(adapter.project.root/'profiles'/adapter.project.code)
    return detect_tutorial_highlight(first,config).tutorial_detected and detect_tutorial_highlight(second,config).tutorial_detected

def guide_handler(adapter,context,inputs,service):
    from tutorial_highlight import load_config,TutorialHandler
    config=load_config(adapter.project.root/'profiles'/adapter.project.code)
    return TutorialHandler(config,capture=service.capture,inputs=inputs,context=context,execution_gate=service.check,user_log=LOG.info,logger=LOG)

def scene(detector,frame):
    if getattr(frame,'shape',None)!=(479,897,3):return 'unknown'
    from owner_special_contexts import classify
    specific=classify(detector,frame,hint=getattr(detector,'_owner_activity_hint',None))
    if specific:return specific
    from owner_movement import tower_combat
    if tower_combat(frame):return 'tower_combat'
    # Shared portal/timer icons cannot distinguish a raid, quest instance or
    # exploration. The original boss shape guard determines common boss combat.
    slots=getattr(detector,'_owner_boss_slots',None)
    if slots is None:
        from project_adapter.main_quest import StateROIs
        slots=StateROIs(detector.profile,mode='sub_quest');detector._owner_boss_slots=slots
    if slots.match('boss',frame).get('hit'):return 'boss_combat'
    from owner_dungeon_map import inside
    if inside(detector,frame):return 'dungeon'
    # The translucent markers dip under .95 inside a dungeon, and the menu/AUTO
    # pair is on screen there too. A real field frame scores near zero on both.
    def outside():
        from owner_movement import choice,hud_dimmed
        # A window open over the field dims the HUD, yet menu and AUTO still match.
        if hud_dimmed(frame) or choice(frame):return 'unknown'
        return 'unknown' if detector.find(DUNGEON,frame,threshold=.5) or detector.find(EXIT,frame,threshold=.5) else 'field'
    from project_adapter.secret_exploration import AUTO_NAMES
    # The menu and AUTO stay on screen behind the bag, which then passed for the field.
    from owner_progression import inventory_parts
    if all(inventory_parts(frame)):return 'inventory'
    if detector.find(MENU,frame,threshold=.95) and any(detector.find(n,frame,threshold=.95) for n in AUTO_NAMES):return outside()
    from owner_movement import field_hud,hud_anchor
    if field_hud(frame):return outside()
    from owner_progression import inventory_parts
    if any(inventory_parts(frame)):return 'inventory'
    # A notification dot breaks the menu match and a bright backdrop breaks the settings icon, both in
    # town. With no panel open, the Home icon and AUTO still prove the bare field.
    if hud_anchor(frame,'home-hud',(662,441,25,29)) and any(detector.find(n,frame,threshold=.95) for n in AUTO_NAMES):return outside()
    from owner_text import shows_field_words,level_and_name
    if shows_field_words(frame):return outside()
    # The bag's own check is a fixed place. Its title names the character, which nothing else shows there.
    if level_and_name(frame)[0] is not None:return 'inventory'
    return 'unknown'

def timer_pair(service):
    """The same paired duration reader as entry/rewards; not exit authority."""
    from owner_reward_context import read_remaining
    return read_remaining(service)

def publish(gui,adapter,kind,phase,remaining=None):
    from owner_special_contexts import LABELS
    if kind=='field':adapter._owner_reward_dungeon_clock=None
    names={'dungeon':'특수 던전','field':'일반 필드','inventory':'인벤토리','unknown':'위치 확인 중',**LABELS}
    snapshot={'location':kind,'location_label':names[kind],'phase':phase,'remaining_seconds':remaining,
              'selected_mode':adapter.mode,'observed_at':time.strftime('%Y-%m-%dT%H:%M:%S')}
    gui._owner_stage_snapshot=snapshot
    status=getattr(adapter,'status',None)
    if status is not None:status.set_current_task(names[kind]+' · '+phase)
    path=adapter.project.root/'settings/owner-startup-stage.json'
    try:
        path.parent.mkdir(exist_ok=True);temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    except OSError:LOG.warning('시작 위치 기록 저장 실패')

FIELD_REVIVE='버튼_보스_거점이동부활'
def press_field_revive(service,context,adapter,frame):
    """A raid's death screen offers only this button, which the quest death handler does not know.
    22:12 real run: a resumed raid sat dead for 60 seconds, then stopped the whole macro."""
    from roi_runtime import RoiDetector
    detector=getattr(adapter,'_owner_field_revive_reader',None)
    if detector is None:
        detector=RoiDetector(adapter.project.root/'profiles'/adapter.project.code,[FIELD_REVIVE]);adapter._owner_field_revive_reader=detector
    hit=detector.find(FIELD_REVIVE,frame,threshold=.9)
    if not hit:return False
    context.checkpoint();service.click_hit(hit);LOG.info('특수 던전 사망 · 거점 이동 후 부활 입력')
    context.wait(1.5);return True

def resume_dungeon(gui,adapter,context,inputs,service):
    from owner_schedule_priority import activity_scope
    from owner_dungeon_reentry import resume_goal,preserve_resume_goal
    goal=resume_goal(adapter)
    try:
        with activity_scope('비경·던전'):
            return _resume_dungeon(gui,adapter,context,inputs,service,goal=goal)
    finally:preserve_resume_goal(adapter,goal)

def _resume_dungeon(gui,adapter,context,inputs,service,*,goal=None):
    from owner_camera import zoom_once
    zoom_once(adapter,context,inputs)
    from owner_dungeon_reentry import dungeon_range
    dungeon_range(adapter,context,inputs)
    from project_adapter.secret_exploration import ensure_auto_active
    from project_adapter.main_quest import StateROIs,BoundedMainQuestRunner,dependencies
    slots=StateROIs(adapter.project.root/'profiles'/adapter.project.code,mode='sub_quest')
    timer=timer_pair(service)
    publish(gui,adapter,'dungeon','기존 자동전투 이어가기',timer)
    LOG.info('시작 위치 확인 · 특수 던전 진행 중 · 잔여시간=%s초 · 현재 모드=%s · 입장·우편·상자 준비를 미루고 기존 전투 유지',timer,adapter.mode)
    # A countdown read cannot end an ongoing map, nor impose the previous
    # two-hour cap on the existing 5/24-hour content. Location/death still gate
    # every action; retain a finite bound for the longest supported content.
    deadline=time.monotonic()+86400+120
    next_auto=0.;next_timer=time.monotonic()+30;outside=0;unknown_at=None;death_runner=None;death_at=None;zero_logged=False
    while True:
        context.checkpoint();frame=service.capture();kind=scene(service.detector,frame)
        death=slots.match('death',frame)
        if death.get('hit'):
            if death_at is None:death_at=time.monotonic()
            if time.monotonic()-death_at>60:raise RuntimeError('특수 던전 사망 복구를 60초간 확인하지 못했습니다.')
            publish(gui,adapter,'dungeon','사망 복구 확인')
            if press_field_revive(service,context,adapter,frame):
                context.wait(.25);continue
            if death_runner is None:
                from owner_native_contract import runner_kwargs
                death_runner=BoundedMainQuestRunner(slots,**runner_kwargs(dependencies(adapter,context,inputs,notifications=False)))
            death_runner.handle_death(slots.by_key['death'],death,frame)
            context.wait(.25);continue
        death_at=None
        if kind not in ('field','dungeon','unknown'):
            LOG.info('비경·던전 중 화면 변경 · %s · 현재 위치 다시 판독',kind)
            raise RecheckStage()
        if kind=='field':
            outside+=1
            if outside>=3:
                LOG.info('비경 지도 이탈 확인 · 기본 화면 3회 대조 · 즉시 기존 입장 경로로 시간 재확인')
                publish(gui,adapter,'field','비경 입장 시간 즉시 재확인')
                from owner_dungeon_reentry import after_exit,save_record,completed
                if goal is not None:
                    if goal.left()<=0:
                        goal.done=True;save_record(adapter,goal.kind,'goal_complete',budget=0);completed(adapter,goal.kind,'goal_complete')
                        LOG.info('24시간 비경 설정 시간 완료 · 재입장 없음');return
                    save_record(adapter,goal.kind,'exit_pending',budget=goal.left());goal.handed_off=True
                return after_exit(adapter,context,inputs)
        elif kind=='dungeon':
            outside=0;unknown_at=None;now=time.monotonic()
            if goal is not None and goal.left()<=0 and not goal.leave_requested:
                from owner_dungeon_reentry import request_goal_leave
                LOG.info('24시간 비경 이어가기 목표 시간 완료 · 기존 정상 퇴장 경로 실행')
                request_goal_leave(adapter,context,inputs,goal)
                context.wait(.3);continue
            if goal is not None and goal.leave_requested:
                if now-goal.leave_at>30:raise RuntimeError('24시간 비경 목표 완료 후 퇴장 확인 필요')
                context.wait(.3);continue
            if now>=next_auto:
                if not any(service.detector.find(n,frame,threshold=.95) for n in ('버튼_AUTO_활성','버튼_AUTO_활성2')):
                    def check_frame(f):
                        if scene(service.detector,f)!='dungeon':raise RecheckStage()
                        return True
                    ensure_auto_active(service,context,LOG,frame=frame,post_click_wait=1,poll_seconds=.5,deadline=now+8,frame_check=check_frame)
                    LOG.info('비경·던전 기존 위치 · 자동전투 활성 재확인')
                next_auto=time.monotonic()+10
            if now>=next_timer:
                timer=timer_pair(service);next_timer=time.monotonic()+30
                publish(gui,adapter,'dungeon','기존 자동전투 이어가기',timer)
                if timer==0 and not zero_logged:
                    LOG.info('비경 시간 0초 판독 · 비경 지도 표시 유지 중 · 강제 퇴장 없이 실제 이탈 대기')
                    zero_logged=True
        else:
            outside=0
            from owner_scene_archive import unknown_observed
            unknown_observed(gui,adapter,context,frame,'dungeon_unrecognized')
            if unknown_at is None:unknown_at=time.monotonic()
            # A raid's death screen stays unnamed through its revive countdown, which ended this at 20 (11-05 14:28).
            if time.monotonic()-unknown_at>45:raise RuntimeError('비경 복귀 중 현재 화면을 45초간 확인하지 못했습니다. 진단 확인이 필요합니다.')
        if time.monotonic()>deadline:raise RuntimeError('비경 기존 진행 이어가기 제한시간 초과 · 새 입장 없이 중단합니다.')
        context.wait(.5)

def install(gui):
    from project_adapter._entry import Adapter
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    import runtime_capture
    if getattr(gui,'_owner_startup_stage',False):return
    gui._owner_stage_epoch=0
    for method in ('start','resume'):
        ordinary=getattr(gui.session,method)
        def request(*a,_ordinary=ordinary,**k):
            with gui.session.lock:
                before=gui._owner_stage_epoch
                if gui.session.snapshot()['status']=='paused':gui._owner_stage_epoch+=1
                try:return _ordinary(*a,**k)
                except BaseException:gui._owner_stage_epoch=before;raise
        setattr(gui.session,method,request)
    ordinary_capture=runtime_capture.capture
    @wraps(ordinary_capture)
    def capture(*a,**k):
        frame=ordinary_capture(*a,**k);owner=getattr(LOCAL,'owner',None)
        if owner and not getattr(LOCAL,'monitoring',False):
            g,context,inputs,epoch=owner
            if g._owner_stage_epoch!=epoch and not context.stop.is_set() and not context.pause.is_set() and not context.input_depth and not getattr(inputs,'held',()):raise RecheckStage()
        return frame
    runtime_capture.capture=capture
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                if value is ordinary_capture:setattr(module,key,capture)
    ordinary_run=Adapter.run
    @wraps(ordinary_run)
    def run(adapter,context,inputs):
        if getattr(LOCAL,'owner',None):return ordinary_run(adapter,context,inputs)
        stage_attempts={};tutorial_handler=None;tutorial_deadline=None;unknown_since=None
        try:
            while True:
                context.checkpoint();LOCAL.owner=(gui,context,inputs,gui._owner_stage_epoch);LOCAL.monitoring=True
                from owner_special_contexts import NAMES as SPECIAL_NAMES
                names=list(dict.fromkeys([DUNGEON,EXIT,MENU,SLEEP,'체크_사망상태','버튼_넘기기_확인','버튼_나가기',
                    '체크_레이드진입','체크_보스진입','포인트_공백_인벤토리',*AUTO_NAMES,*SPECIAL_NAMES]))
                service=TownServices(adapter,context,inputs,names)
                hint=getattr(adapter,'_owner_activity_hint',None)
                if hint and hint['context'] is context and hint['epoch']==gui._owner_stage_epoch:service.detector._owner_activity_hint=hint['kind']
                first=service.capture();initial=scene(service.detector,first)
                context.wait(.15);second_frame=service.capture();second=scene(service.detector,second_frame)
                # Reuse startup's two frames; unrelated field/dungeon/title/
                # transitional screens continue through the existing router.
                from owner_quest_emote_candidate import normalize_after_stop
                if normalize_after_stop(adapter,context,inputs,frames=(first,second_frame),field_confirmed=initial==second=='field'):
                    continue
                # F2/F1 pressed on the sleep screen: nothing else names that screen, so the
                # stop below fired after 40 seconds (23:32 real log). Wake, then read again.
                if initial==second=='unknown' and sleep_screen(service,adapter,first) and sleep_screen(service,adapter,second_frame):
                    sleep_key=(gui._owner_stage_epoch,'sleep')
                    stage_attempts[sleep_key]=stage_attempts.get(sleep_key,0)+1
                    if stage_attempts[sleep_key]>3:raise RuntimeError('절전 해제가 3회 반복되어 확인이 필요합니다.')
                    LOG.info('시작 화면 · 절전 화면 확인 · 해제 후 위치 재확인')
                    LOCAL.monitoring=False
                    try:
                        adapter.exit_sleep_mode(context,inputs)
                        context.wait(.5)
                        if sleep_screen(service,adapter,service.capture()):slide_awake(adapter,context,inputs)
                    finally:LOCAL.monitoring=True
                    continue
                if initial==second=='unknown':
                    from owner_start_menu import game_start_word
                    start_at=game_start_word(second_frame)
                    if start_at and game_start_word(first):
                        start_key=(gui._owner_stage_epoch,'game-start')
                        stage_attempts[start_key]=stage_attempts.get(start_key,0)+1
                        if stage_attempts[start_key]>3:raise RuntimeError('게임 시작을 3회 눌러도 들어가지 못했습니다.')
                        LOG.info('시작 화면 · 접속이 끊겨 게임 시작 입력')
                        LOCAL.monitoring=False
                        try:
                            x,y=start_at;service.click_hit((x,y,(x-5,y-5,x+6,y+6)));context.wait(20)
                        finally:LOCAL.monitoring=True
                        unknown_since=None
                        continue
                if initial==second=='unknown':
                    # A guide can open a known full-screen menu after the start check already ran.
                    from owner_start_menu import kind as menu_kind,menu_panel,normalize as leave_menu
                    if (menu_kind(first) and menu_kind(first)==menu_kind(second_frame)) or (menu_panel(first) and menu_panel(second_frame)):
                        leave_menu(TownServices(adapter,context,inputs,['버튼_나가기']))
                        continue
                    if guide_visible(adapter,first,second_frame):
                        if tutorial_deadline is None:tutorial_deadline=time.monotonic()+60
                        if time.monotonic()>tutorial_deadline:raise RuntimeError('시작 튜토리얼 처리가 60초를 넘어 진단 확인이 필요합니다.')
                        if tutorial_handler is None:tutorial_handler=guide_handler(adapter,context,inputs,service)
                        LOG.info('시작 화면 · 연속 튜토리얼 안내 확인 · 기존 강조 영역 처리기로 정상화')
                        result=tutorial_handler.handle_tutorial_if_present()
                        if result in ('FAILED','DETECTED_BUT_UNSAFE'):raise RuntimeError('시작 튜토리얼 입력을 확인하지 못했습니다: '+result)
                        context.wait(.15)
                        continue
                tutorial_deadline=None
                from owner_movement import choice,confirm_choice,story_guide
                if initial==second=='unknown' and story_guide(first) and story_guide(second_frame):
                    guide_key=(gui._owner_stage_epoch,'story-guide')
                    stage_attempts[guide_key]=stage_attempts.get(guide_key,0)+1
                    if stage_attempts[guide_key]>3:raise RuntimeError('서사 이어가기 안내 처리가 3회 반복되어 확인이 필요합니다.')
                    from owner_skill_ui import SkillUI
                    ui=SkillUI(adapter,context,inputs)
                    LOG.info('시작 화면 · 서사 이어가기 안내 확인 · 강조된 임무 안내 닫기')
                    ui.click(790,69,story_guide)
                    ui.wait(lambda f:not story_guide(f),seconds=5)
                    continue
                if initial==second=='unknown' and choice(first) and choice(second_frame):
                    choice_key=(gui._owner_stage_epoch,'movement-choice')
                    stage_attempts[choice_key]=stage_attempts.get(choice_key,0)+1
                    if stage_attempts[choice_key]>3:raise RuntimeError('축지술 선택창 정리가 3회 반복되어 확인이 필요합니다.')
                    from owner_skill_ui import SkillUI
                    LOG.info('시작 화면 · 축지술 이동 방법 선택창 확인 · 정상화 후 위치 재확인')
                    confirm_choice(SkillUI(adapter,context,inputs))
                    continue
                if initial==second=='unknown':
                    from project_adapter.main_quest import StateROIs
                    slots=StateROIs(adapter.project.root/'profiles/DKB',mode=adapter.mode)
                    # Dead in a raid with the boss over the screen: the place cannot be read, but the
                    # death title can. This stopped the run after 40 seconds (11-05 14:45).
                    if slots.match('death',second_frame).get('hit'):
                        death_key=(gui._owner_stage_epoch,'start-death')
                        stage_attempts[death_key]=stage_attempts.get(death_key,0)+1
                        if stage_attempts[death_key]>240:raise RuntimeError('시작 화면 사망 복구를 확인하지 못했습니다.')
                        LOCAL.monitoring=False
                        try:
                            if not press_field_revive(service,context,adapter,second_frame):context.wait(.25)
                        finally:LOCAL.monitoring=True
                        unknown_since=None
                        continue
                    dialog_key=known_dialog(slots,first,second_frame)
                    if dialog_key:
                        attempts_key=(gui._owner_stage_epoch,'start-dialog-'+dialog_key)
                        total_key=(gui._owner_stage_epoch,'start-dialog-total')
                        stage_attempts[attempts_key]=stage_attempts.get(attempts_key,0)+1
                        stage_attempts[total_key]=stage_attempts.get(total_key,0)+1
                        if stage_attempts[attempts_key]>6 or stage_attempts[total_key]>60:raise RuntimeError('시작 대화 넘기기 확인이 6회 반복되어 진단 확인이 필요합니다.')
                        # Moving between skip and confirm is progress: a level-1 opening has many scenes in a row.
                        for other in ('skip','skip_confirm','skip_confirm2'):
                            if other!=dialog_key:stage_attempts.pop((gui._owner_stage_epoch,'start-dialog-'+other),None)
                        press_dialog(adapter,context,inputs,service,slots,dialog_key,second_frame)
                        continue
                if LOCAL.owner[3]!=gui._owner_stage_epoch:
                    # Resume arrived during read-only preflight. Discard both
                    # observations before any stage action is selected.
                    continue
                kind=initial if initial==second else 'unknown'
                if kind=='unknown':
                    from owner_scene_archive import unknown_observed
                    unknown_observed(gui,adapter,context,second_frame,'startup_unrecognized_or_transition')
                    if unknown_since is None:
                        unknown_since=time.monotonic()
                        LOG.info('시작 화면 전환 대기 · 알려진 위치 확인 후 임무 준비 · 최대 40초')
                    if time.monotonic()-unknown_since>=40:
                        raise RuntimeError('시작 화면을 40초간 확인하지 못했습니다. 임무 준비 입력 없이 진단을 저장합니다.')
                    context.wait(.35)
                    continue
                unknown_since=None
                key=(gui._owner_stage_epoch,kind)
                stage_attempts[key]=stage_attempts.get(key,0)+1
                if kind not in ('field','inventory','unknown') and stage_attempts[key]>3:
                    raise RuntimeError('같은 특수환경 재개가 3회 반복되어 확인이 필요합니다. 현재 화면 진단을 저장합니다.')
                publish(gui,adapter,kind,'시작 화면 재확인')
                LOG.info('자동 진행 시작 위치 · %s · 선택 모드=%s',gui._owner_stage_snapshot['location_label'],adapter.mode)
                entered=time.monotonic()
                try:
                    # Every continuation, including long native combat loops,
                    # unwinds at its next safe capture after a Resume request.
                    LOCAL.monitoring=False
                    if kind=='dungeon':resume_dungeon(gui,adapter,context,inputs,service)
                    elif kind not in ('field','inventory','unknown'):
                        from owner_special_contexts import continue_special,LABELS
                        from owner_schedule_priority import activity_scope
                        with activity_scope(LABELS.get(kind,kind)):
                            continue_special(gui,adapter,context,inputs,service,kind,publish,scene,RecheckStage)
                    LOCAL.monitoring=False
                    if kind=='field':
                        from owner_game_settings import ensure_once
                        ensure_once(adapter,context,inputs)
                    if kind in ('field','dungeon'):
                        from owner_camera import zoom_out
                        zoom_out(adapter,context,inputs)
                    if kind=='field':
                        from owner_single_preset import resume as preset_return
                        preset_return(adapter,context,inputs)
                        # An open boss range record is restored by the hunt itself once at the saved spot (owner_hunt).
                    if kind in ('field','dungeon'):
                        from owner_timetable import catch_up_overdue
                        catch_up_overdue(adapter,context,inputs)
                    return ordinary_run(adapter,context,inputs)
                except RecheckStage:
                    # Raised by a Resume request or by the continuation seeing a
                    # different screen. Only a rapid repeat counts as a loop.
                    if time.monotonic()-entered>=60:stage_attempts.pop(key,None)
                    LOG.info('이전 작업을 정리하고 현재 위치 다시 판독')
                finally:LOCAL.monitoring=False
        finally:LOCAL.owner=None;LOCAL.monitoring=False
    Adapter.run=run;gui._owner_startup_stage=True
