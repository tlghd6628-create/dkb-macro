"""Specific special-environment evidence before generic dungeon/field HUDs.

Recognition is separate from continuation. Active-combat continuations omit new
entry/matching. Selection menus follow the user's existing enabled activity.
"""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
# key, label, phase, all required templates, one-of templates
RULES=(
 ('raid_rejected','보스 레이드','입장 투표 부결',('체크_레이드_투표부결','버튼_X_레이드부결'),()),
 ('raid_admit','보스 레이드','입장 확인 대기',('체크_레이드_매칭입장',),('버튼_레이드_매칭입장확인','버튼_레이드_매칭입장확인2')),
 ('raid_matching','보스 레이드','기존 매칭 대기',('체크_레이드_매칭중',),()),
 ('raid_complete','보스 레이드','토벌 완료',('체크_레이드_토벌완료',),()),
 ('tower_failure','승천의 탑','실패 결과',('버튼_나가기_승천실패',),()),
 ('tower_next','승천의 탑','다음 단계 대기',('버튼_승천_다음단계',),()),
 ('falling_combat','낙화의 전장','진행 중인 전투',(),('체크_낙화_입장완료','체크_낙화_진입완료')),
 ('folktale_progress','전래동화','진행 중인 임무',('버튼_전래동화_진행중','버튼_전체매뉴'),()),
 ('boss_complete','보스전','완료 결과',(),('체크_보스_완료','체크_보스_완료2')),
 ('treasure_receipt','보물찾기','발견 보상 확인',('체크_보물찾기_아이템획득',),()),
 ('treasure_found','보물찾기','발견 지점 수령',(),('버튼_보물찾기_찾음','버튼_보물찾기_찾음2','버튼_보물찾기_찾음3')),
 ('treasure_map','보물찾기','진행 지도',('체크_보물찾기',),('체크_보물찾기_현위치아이콘','체크_보물찾기_현위치아이콘2','체크_보물찾기_타바로_현위치')),
 ('spirit_dialog','영기수련','수련창',('체크_영기수련',),()),
 ('clan_training_dialog','문파 협력수련','수련창',('버튼_협력수련_닫기',),('버튼_협력수련_사용','버튼_협력수련')),
 ('clan_activity_dialog','문파 활동','신청·결과창',('체크_문파',),('체크_문파_요신토벌령','체크_문파_결계지방어','체크_문파_미혹의정원','체크_문파_신기쟁탈전','체크_문파_분신완료','체크_문파_참가완료')),
 ('raid_menu','보스 레이드','단계 선택창',('체크_보스토벌','버튼_보스_레이드탭'),('체크_레이드_1단계','체크_레이드_2단계','체크_레이드_3단계','체크_레이드_4단계','체크_레이드_5단계')),
 ('world_boss_menu','월드보스','필드보스 선택창',('체크_보스토벌','버튼_보스_필드보스탭'),()),
 ('falling_menu','낙화의 전장','입장 선택창',('체크_낙화_입장구역선택','버튼_낙화_입장'),()),
 ('folktale_menu','전래동화','임무 선택창',('체크_임무','버튼_임무_전래동화탭'),()),
 ('secret_folktale_5h_menu','전래동화 비경(5시간)','입장 선택창',('체크_비경',),('체크_비경_전래동화_원님5','체크_비경_전래동화_팥쥐5')),
 ('secret_folktale_24h_menu','전래동화 비경(24시간)','입장 선택창',('체크_비경',),('체크_비경_전래동화_원님24','체크_비경_전래동화_팥쥐24')),
 ('daily24_menu','일일 비경(24시간)','입장 선택창',('체크_비경',),('체크_비경_상시고독마을','체크_비경_상시고독귀지')),
 ('exploration_menu','비경 탐험','입장 선택창',('체크_비경',),('체크_비경_단계선택','버튼_비경_입장')),
)
LABELS={key:label for key,label,*_ in RULES}
PHASES={key:phase for key,_,phase,*_ in RULES}
LABELS['boss_combat']='보스 전투';PHASES['boss_combat']='진행 중인 보스전'
LABELS['raid_combat']='보스 레이드';PHASES['raid_combat']='진행 중인 레이드 전투'
LABELS['world_boss']='월드보스';PHASES['world_boss']='진행 중인 월드보스'
LABELS['tower_combat']='승천의 탑';PHASES['tower_combat']='진행 중인 탑 전투'
NAMES=tuple(dict.fromkeys((*(n for rule in RULES for n in (*rule[3],*rule[4])),'체크_던전진행중','버튼_던전_나가기')))
# The game shows the same "아이템 획득" banner for any drop. Actual saved frames:
# 8 treasure receipts without dungeon markers, 1 ordinary dungeon drop with them.
FIELD_ONLY=frozenset(('treasure_receipt',))
MENU_HANDLERS={
 'raid_menu':('auto_schedule.boss_raid.enabled','boss_raid','run_boss_raid'),
 'falling_menu':('auto_schedule.falling_battle.enabled','falling_battle','run_falling_battle'),
 'folktale_menu':('auto_schedule.folktale.enabled','folktale','run_folktale'),
 'exploration_menu':('auto_challenge.secret_exploration.enabled','secret_exploration','run_secret_exploration'),
 'clan_activity_dialog':('auto_schedule.clan_boss_request.enabled','clan_boss_request','run_clan_boss_request'),
 'treasure_map':('auto_challenge.treasure_hunt.enabled',None,'run_treasure_region_entry'),
 'world_boss_menu':('auto_schedule.field_boss.enabled',None,'run_field_boss_entry'),
 'spirit_dialog':('auto_growth.spirit_training.enabled',None,'run_spirit_training'),
 'clan_training_dialog':('auto_growth.clan_cooperative_training.enabled','clan_cooperative_training','run_clan_cooperative_training'),
 'secret_folktale_5h_menu':('auto_challenge.secret_folktale_5h.enabled','secret_folktale','run_folktale_exploration'),
 'secret_folktale_24h_menu':('auto_challenge.secret_folktale.enabled','secret_folktale','run_folktale_exploration'),
 'daily24_menu':('auto_challenge.secret_exploration_always.enabled','secret_exploration','run_secret_exploration'),
}

def find(detector,name,frame):
    if name not in detector.templates:return None
    return detector.find(name,frame,threshold=.95)

def classify(detector,frame,hint=None):
    if getattr(frame,'shape',None)!=(479,897,3):return None
    cache={}
    def hit(n):
        if n not in cache:cache[n]=find(detector,n,frame)
        return cache[n]
    for key,label,phase,required,alternatives in RULES:
        if all(hit(n) for n in required) and (not alternatives or any(hit(n) for n in alternatives)):
            if key in FIELD_ONLY:
                from owner_dungeon_map import inside
                if inside(detector,frame):continue
            return key
    # The raid/world-boss portal is shared with ordinary dungeons. A portal
    # alone NEVER identifies a raid. A validated current-game context is needed.
    if hint in ('raid_combat','world_boss') and (hit('체크_던전진행중') or hit('체크_보스진입')):
        return hint
    return None

def native_resume(kind,adapter,context,inputs):
    """Resume only the combat portion of an already-entered native activity."""
    if kind in ('raid_combat','raid_complete'):
        from project_adapter.boss_raid import RaidFlow
        return RaidFlow(adapter,context,inputs).combat(wait_for_exit=True)
    if kind=='falling_combat':
        from project_adapter.falling_battle import FallingBattle,DailyBudget
        budget=DailyBudget(adapter,standalone=False)
        budget.start()
        try:return FallingBattle(adapter,context,inputs,budget).battle()
        finally:budget.pause()
    if kind=='folktale_progress':
        from project_adapter.folktale import FolktaleRunner,dependencies
        from project_adapter.main_quest import StateROIs
        slots=StateROIs(adapter.project.root/'profiles'/adapter.project.code,mode='folktale')
        from owner_native_contract import runner_kwargs
        return FolktaleRunner(slots,**runner_kwargs(dependencies(adapter,context,inputs))).run_main_quest()
    raise ValueError('No entry-free native continuation for '+kind)

def scene_words(frame):
    """넘기기 (with ESC) at the top right: a story scene is showing."""
    if getattr(frame,'hi',None) is None:return False
    from owner_text import read,clean
    from owner_worn_stats import SKIP_WORD
    return any('넘기기' in clean(r['text']) for r in read(None,frame,SKIP_WORD,scale=2,minimum=.6))


def continue_special(gui,adapter,context,inputs,service,kind,publish,scene,recheck):
    from project_adapter.main_quest import StateROIs,BoundedMainQuestRunner,dependencies
    from project_adapter.secret_exploration import ensure_auto_active
    family=LABELS.get(kind,kind);deadline=time.monotonic()+1800
    LOG.info('특수환경 이어가기 · %s · %s · 새 입장·매칭·티켓 소모 생략',family,PHASES.get(kind,''))
    publish(gui,adapter,kind,PHASES.get(kind,'현재 진행 이어가기'))
    if kind in ('raid_combat','raid_complete','falling_combat','folktale_progress'):
        native_resume(kind,adapter,context,inputs)
        raise recheck()
    if kind in MENU_HANDLERS:
        import importlib
        setting,module,function=MENU_HANDLERS[kind]
        if adapter.values.get(setting) is True:
            LOG.info('%s 선택창 확인 · 사용자가 켠 해당 자동 기능으로 연결',family)
            if module is None:getattr(adapter,function)(context,inputs)
            else:
                kwargs={'kind':'5h' if kind=='secret_folktale_5h_menu' else '24h'} if kind.startswith('secret_folktale_') else {}
                if kind=='daily24_menu':kwargs={'variant':'daily24h'}
                getattr(importlib.import_module('project_adapter.'+module),function)(adapter,context,inputs,**kwargs)
        else:
            LOG.info('%s 자동 기능 꺼짐 · 선택창만 닫고 기존 모드 재확인',family)
            service.button('버튼_나가기',wait_before_click=.2,required=False)
        raise recheck()
    slots=StateROIs(adapter.project.root/'profiles'/adapter.project.code,mode='sub_quest')
    runner=None;outside=0;sent=False;death_at=None;next_auto=0;next_scene=0
    while True:
        context.checkpoint();frame=service.capture();current=scene(service.detector,frame)
        if current=='unknown':
            from owner_scene_archive import unknown_observed
            unknown_observed(gui,adapter,context,frame,'special_environment_unrecognized')
        death=slots.match('death',frame)
        if not death.get('hit') and getattr(frame,'hi',None) is not None:
            # At 1366 the death picture does not match (pc1 13:54: the death screen was taken for a running boss
            # fight). Its own words count, and 나가기 is pressed.
            from owner_death_real import recover as real_death
            from types import SimpleNamespace
            if real_death(SimpleNamespace(frame=service.capture,context=context,service=service)):death_at=None;continue
        if death.get('hit'):
            if death_at is None:death_at=time.monotonic()
            if time.monotonic()-death_at>60:raise RuntimeError(f'{family} 사망 복구를 60초간 확인하지 못했습니다.')
            if runner is None:
                from owner_native_contract import runner_kwargs
                runner=BoundedMainQuestRunner(slots,**runner_kwargs(dependencies(adapter,context,inputs,notifications=False)))
            runner.handle_death(slots.by_key['death'],death,frame);context.wait(.25);continue
        death_at=None
        if kind in ('boss_combat','boss_complete') and current!=kind and time.monotonic()>=next_scene:
            # A won boss ends in a story scene (넘기기 at the top right). This loop saw neither a field nor a boss and
            # waited out its 30 minutes (pc1 01:23-01:51); the quest runner owns scenes, so it takes over.
            next_scene=time.monotonic()+5
            if scene_words(frame):
                LOG.info('%s 종료 후 대화 장면 · 퀘스트 진행으로 넘김',family);raise recheck()
        if current=='field':
            outside+=1
            if outside>=3:publish(gui,adapter,'field','특수환경 종료 확인 · 선택 모드 재개');return
        else:outside=0
        if current not in (kind,'field','unknown','dungeon'):
            raise recheck()
        # A one-step screen has closed onto an ongoing dungeon. Waiting here for
        # a field frame would time out while the dungeon keeps running.
        if sent and current=='dungeon':raise recheck()
        if kind=='raid_matching':
            # Existing matchmaking waits for admission/rejection/combat. No
            # new matching request or ticket action is ever sent here.
            if time.monotonic()>deadline-1620:raise RuntimeError('레이드 기존 매칭 대기 180초 초과 · 현재 화면 확인이 필요합니다.')
        elif not sent and kind in ('raid_admit','raid_rejected','tower_next','tower_failure','treasure_found','treasure_receipt','spirit_dialog','clan_training_dialog'):
            targets={
              'raid_admit':('버튼_레이드_매칭입장확인','버튼_레이드_매칭입장확인2'),
              'raid_rejected':('버튼_X_레이드부결',),'tower_next':('버튼_승천_다음단계',),
              'tower_failure':('버튼_나가기_승천실패',),
              'treasure_found':('버튼_보물찾기_찾음','버튼_보물찾기_찾음2','버튼_보물찾기_찾음3'),
              'clan_training_dialog':('버튼_협력수련_닫기',),'spirit_dialog':('버튼_나가기',)}
            if kind=='treasure_receipt':
                if find(service.detector,'체크_보물찾기_아이템획득',service.capture()):service.point('포인트_공백_인벤토리')
            else:
                name=next((n for n in targets[kind] if find(service.detector,n,frame)),None)
                if name:
                    if kind=='raid_admit':adapter._owner_activity_hint={'kind':'raid_combat','context':context,'epoch':gui._owner_stage_epoch}
                    service.button(name,wait_before_click=.2)
            sent=True;deadline=min(deadline,time.monotonic()+30)
        elif kind=='tower_combat':
            if current=='tower_combat' and time.monotonic()>=next_auto:
                def check_tower(f):
                    if scene(service.detector,f)!='tower_combat':raise recheck()
                    return True
                ensure_auto_active(service,context,LOG,frame=frame,post_click_wait=1,poll_seconds=.5,deadline=time.monotonic()+8,frame_check=check_tower)
                next_auto=time.monotonic()+10
        elif kind=='boss_combat':
            match=slots.match('boss',frame)
            if match.get('hit'):
                if runner is None:
                    from owner_native_contract import runner_kwargs
                    runner=BoundedMainQuestRunner(slots,**runner_kwargs(dependencies(adapter,context,inputs,notifications=False)))
                runner.handle_boss(slots.by_key['boss'],match,frame)
        elif kind in ('boss_complete','world_boss') and not sent:
            # Existing field-boss result handler, strictly resume_monitor;
            # preparing or recovering a fresh entry is forbidden.
            from project_adapter import field_boss
            from project_adapter.town_services import TownServices
            boss_service=TownServices(adapter,context,inputs,field_boss.NAMES)
            def no_entry(*a,**k):raise RuntimeError('이미 진행 중인 보스 처리에서 새 입장이 요청되어 중단했습니다.')
            # At 1366 the result handler only rechecked every minute and never left (21:05-21:07); the exit is
            # pressed by its words once it has waited 90 s (owner_boss_exit).
            from owner_boss_exit import Leaving
            context_for_boss=Leaving(context,boss_service)
            field_boss.run_field_boss_entry(detector=boss_service.detector,capture=boss_service.capture,inputs=inputs,context=context_for_boss,status=adapter.status,
                user_log=lambda s:LOG.info('%s',s),adapter=adapter,prepare_entry=no_entry,recover_entry=no_entry,resume_monitor=True)
            raise recheck()
        if time.monotonic()>deadline:raise RuntimeError(f'{family} 현재 단계 처리 시간 초과 · 진행 위치를 저장했습니다.')
        context.wait(.5)
