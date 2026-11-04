"""Non-committing diagnostics for features without a live menu path.

Import performs no game input, no filesystem mutation and no network. Every
entry point is a pure projection over settings/state files or over frames the
caller already captured. Navigation is returned as a **request list** only; the
existing single-worker MenuProbe owns the allowlist, the fresh-screen proof and
the cancel guard, and must not press entry/matching/claim/purchase/upgrade or
confirm buttons on our behalf.

Stages follow the checker vocabulary: config / contract / menu / values /
action_ready / unsupported / skipped.
"""
from pathlib import Path
import hashlib, json

# Catalog features with no product implementation behind them today.
PRODUCT_ABSENT = ('mangwi', 'offline', 'falling_elite', 'season')
# Automatic purchases chosen per item in the shop settings; same owner_timetable jobs.
SHOP_JOBS = {'daily_shop': 'shop', 'weekly_shop': 'shop_weekly_verify'}
# Connected in code; a screen probe would have to run real work to prove more.
RUNTIME_ONLY = {'box_choice': '상자 개봉·선택', 'gear_swap': '장비 착용', 'skill_learn': '도술 구매·학습',
                'work_resume': '작업 전환', 'reconnect': '재접속', 'user_controls': 'F1·F2·F3 입력',
                'telegram': '실제 봇 왕복', 'auto_update': '실제 배포본 수신'}
EXTRA_IDS=frozenset(('achievement','clan_artifact','clan_garden','coupon','daily_restart','daily_shop',
 'disassembly','falling','falling_elite','field_boss','hunt','inner_path','mangwi','market','offline','potion',
 'raid','season','tower','training_log','treasure','weekly_shop','shop',*RUNTIME_ONLY))
# Catalog features whose runtime reader is not connected yet (checker gap).
NO_DIAGNOSTIC = ()

# Timetable jobs: enable flag plus planner state give a real projection.
JOBS = ('tower', 'raid', 'treasure', 'training_log', 'clan_request', 'shop')

FLAGS = {
    'achievement': 'auto_rewards.achievement.enabled',
    'coupon': 'main_quest.first_coupon.enabled',
    'inner_path': 'inner_path.enabled',
    'market': 'auto_register.market.enabled',
    'disassembly': 'auto_register.equipment_disassembly.enabled',
    'clan_artifact': 'auto_schedule.artifact_charm.enabled',
    'clan_garden': 'auto_schedule.artifact_charm.enabled',
    'falling': 'auto_schedule.falling_battle.enabled',
    'field_boss': 'auto_schedule.field_boss.enabled',
    'daily_restart': 'common.daily_restart.enabled',
}

# Verified existing buttons only. A None anchor means the screen itself cannot
# be proved yet, so the caller is told that explicitly instead of guessing.
NAVIGATION = {
    'achievement': (('버튼_전체매뉴', '전체 메뉴'), ('버튼_전체매뉴_업적', '업적')),
    'coupon': (('버튼_전체매뉴', '전체 메뉴'), ('버튼_전체매뉴_설정', '설정'),
               ('버튼_전체매뉴_설정_쿠폰등록', '쿠폰 등록')),
    'inner_path': (('버튼_전체매뉴', '전체 메뉴'), ('버튼_전체매뉴_내면의길', '내면의 길')),
}
ANCHORS = {'achievement': '범위_업적받기', 'coupon': None, 'inner_path': None}
READINESS = ('main', 'story', 'daily', 'weekly', 'inventory', 'energy')


def app_root(root):
    base = Path(root)
    if (base / 'profiles/DKB').is_dir():
        return base
    candidate = base / 'vendor/DKB_Auto'
    if (candidate / 'profiles/DKB').is_dir():
        return candidate
    raise ValueError('프로그램 프로필을 찾지 못했습니다.')


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def _record(item, stage, finding, detail, *, steps=None, observed=None, unknown=None, navigate=None):
    return {'id': item, 'stage': stage, 'finding': finding, 'detail': detail,
            'steps': steps or [], 'observed': observed or {}, 'unknown': unknown or [],
            'navigate': [{'name': name, 'label': label} for name, label in (navigate or ())],
            'anchor': ANCHORS.get(item), 'committed': False}


def _job_state(root, key):
    data = _json(Path(root) / 'settings/owner-timetable-state.json') or {}
    characters = data.get('characters') if isinstance(data, dict) else None
    from owner_timetable import identity
    ident=identity(root)
    if ident==' / ' or not isinstance(characters,dict):return None
    rows=characters.get(ident)
    row=rows.get(key) if isinstance(rows,dict) else None
    return row if isinstance(row,dict) else None


def _job(item, root, values):
    from owner_timetable import BY_KEY
    key = SHOP_JOBS.get(item, item)
    job = BY_KEY.get(key)
    if job is None:
        return _record(item, 'unsupported', 'product_absent', '시간표 작업 정의가 없습니다')
    enabled = values.get(job.setting) if isinstance(values, dict) else None
    if key in ('shop', 'shop_weekly_verify'):
        # The planner derives this flag from the per-character shop selections.
        from owner_timetable import shop_selection_enabled
        enabled = shop_selection_enabled(root)
    state = _job_state(root, key)
    observed = {'enabled_key': job.setting, 'enabled': enabled,
                'state': None if state is None else {'at': state.get('at'), 'status': state.get('status'),
                                                     'attempts': state.get('attempts')}}
    steps = [{'stage': 'settings', 'status': 'on' if enabled is True else 'off' if enabled is False else 'unknown'}]
    if type(enabled) is not bool:
        return _record(item,'config','settings_missing','예약 사용 설정을 읽지 못했습니다',observed=observed)
    if enabled is not True:
        return _record(item, 'config', 'settings_off', '예약 기능이 꺼져 있습니다 · 실행 없음',
                       steps=steps, observed=observed)
    if state is None:
        return _record(item, 'action_ready', 'schedule_unproven',
                       '설정은 켜짐 · 실행 기록이 없어 예약 계산만 가능 · 실행 없음',
                       steps=steps + [{'stage': 'schedule', 'status': 'unproven'}], observed=observed,
                       unknown=['예약 계산', '실제 실행 결과'])
    return _record(item, 'action_ready', 'scheduled',
                   f"설정 켜짐 · 기록 {state.get('at')} · 상태 {state.get('status')} · 실행 없음",
                   steps=steps + [{'stage': 'schedule', 'status': 'recorded'}], observed=observed,
                   unknown=['실제 실행 결과'])


def _hunt(item, root, values):
    values = values if isinstance(values, dict) else {}
    observed = {'enabled': values.get('common.potion_and_favorite.enabled'),
                'native_source': values.get('common.potion_and_favorite.source'),
                'native_slot': values.get('common.potion_and_favorite.slot')}
    try:
        from owner_hunt_rules_candidate import ConfiguredHuntRules
        rules = ConfiguredHuntRules(Path(root))
        rows = rules.read()
        observed.update(rules=len(rows), slots=[row.get('slot') for row in rows],
                        stationary=rules.stationary())
    except (OSError, ValueError, TypeError) as exc:
        observed['rules_error'] = str(exc)[:120]
    steps = [{'stage': 'settings', 'status': 'on' if observed['enabled'] is True else 'off' if observed['enabled'] is False else 'unknown'}]
    if type(observed['enabled']) is not bool:
        return _record(item,'config','settings_missing','사냥 사용 설정을 읽지 못했습니다',observed=observed)
    if observed['enabled'] is not True:
        return _record(item, 'config', 'settings_off', '자동사냥·사냥터가 꺼져 있습니다 · 실행 없음',
                       steps=steps, observed=observed)
    if 'rules_error' in observed:
        return _record(item, 'values', 'rules_unreadable',
                       '설정 켜짐 · 사냥터 규칙 파일 판독 실패 · 실행 없음',
                       steps=steps + [{'stage': 'values', 'status': 'unreadable'}], observed=observed)
    document=_json(Path(root)/'settings/auto-settings.json') or {}
    if document.get('mode')=='auto_mode' and not observed.get('stationary'):
        return _record(item, 'config', 'goal_missing',
                       '제자리 사냥 모드의 저장 위치가 없습니다 · 실행 없음',
                       steps=steps + [{'stage': 'decision', 'status': 'goal_missing'}], observed=observed)
    return _record(item, 'action_ready', 'projection_only',
                   f"규칙 {observed.get('rules')}개 · 제자리 {observed.get('stationary')} · "
                   '현재 전투력에서 어느 규칙이 선택되는지는 미검증 · 실행 없음',
                   steps=steps + [{'stage': 'values', 'status': 'projected'},
                                  {'stage': 'decision', 'status': 'runtime_route_unknown'}],
                   observed=observed, unknown=['실행 시 선택 규칙', '실제 이동 결과'])


def _shop(item, root, character):
    if not isinstance(character, str) or not character.strip():
        return _record(item, 'values', 'character_unknown',
                       '캐릭터가 확인되지 않아 상점 목표를 특정할 수 없습니다 · 실행 없음')
    ident = hashlib.sha256(character.strip().encode('utf-8')).hexdigest()[:24]
    document = _json(Path(root) / 'settings' / ('owner-shop-settings-' + ident + '.json'))
    if not isinstance(document, dict):
        return _record(item, 'config', 'goal_missing',
                       '상점 구매 목표 파일이 없습니다(설정 화면에서 저장 필요) · 실행 없음',
                       steps=[{'stage': 'settings', 'status': 'missing'}])
    rows = document.get('items') or document.get('rows') or []
    enabled = [row for row in rows if isinstance(row, dict) and row.get('enabled') is True]
    observed = {'character': character, 'rows': len(rows), 'enabled': len(enabled),
                'coin_reserve': document.get('coin_reserve')}
    if not enabled:
        return _record(item, 'config', 'goal_missing', '상점 목표가 모두 꺼져 있습니다 · 실행 없음',
                       steps=[{'stage': 'settings', 'status': 'off'}], observed=observed)
    return _record(item, 'action_ready', 'projection_only',
                   f"구매 목표 {len(enabled)}개 · 잔액 여유 {document.get('coin_reserve')} · 구매 실행 없음",
                   steps=[{'stage': 'settings', 'status': 'on'},
                          {'stage': 'decision', 'status': 'availability_unknown'}],
                   observed=observed, unknown=['가격/재고', '실제 구매 결과'])


def _potion(root,values):
    enabled=values.get('common.potion_and_favorite.enabled')
    if type(enabled) is not bool:return _record('potion','config','settings_missing','물약 보충 사용 설정 미확인')
    if not enabled:return _record('potion','config','settings_off','물약 보충 사용 안 함')
    tier=values.get('common.potion_and_favorite.potion_tier')
    if tier not in ('1단물약','2단물약','3단물약'):
        return _record('potion','config','goal_invalid','물약 단계 설정을 확인해 주세요',observed={'tier':tier})
    # Potion replenishment is independent of optional weekly shop item goals.
    from owner_membership import paid
    remote=paid(root)
    return _record('potion','action_ready','projection_only',f'{tier} · '+('멤버십 원격 상점' if remote else '일반 잡화상점')+' · 실제 재고·구매 미시험',
                   observed={'tier':tier,'membership':remote},unknown=['현재 재고','실제 보충 결과'])


def _flag(item, values):
    key = FLAGS.get(item)
    if key is None:
        return _record(item, 'unsupported', 'no_documented_diagnostic',
                       '이 기능의 판정 근거가 아직 연결되지 않았습니다')
    enabled = values.get(key) if isinstance(values, dict) else None
    steps = [{'stage': 'settings', 'status': 'on' if enabled is True else 'off' if enabled is False else 'unknown'}]
    observed = {'enabled_key': key, 'enabled': enabled}
    navigation = NAVIGATION.get(item, ())
    if type(enabled) is not bool:
        return _record(item,'config','settings_missing','사용 설정을 읽지 못했습니다',observed=observed)
    if enabled is not True:
        return _record(item, 'config', 'settings_off', '설정이 꺼져 있습니다 · 실행 없음',
                       steps=steps, observed=observed)
    if item in NAVIGATION and ANCHORS.get(item) is None:
        return _record(item, 'action_ready', 'anchor_unverified',
                       '설정 켜짐 · 화면 앵커가 확인되지 않아 이동만 요청합니다 · 실행 없음',
                       steps=steps + [{'stage': 'menu', 'status': 'anchor_unverified'}],
                       observed=observed, navigate=navigation, unknown=['화면 도달 증거'])
    return _record(item, 'action_ready', 'config_only',
                   '설정 켜짐 · 실행 결과를 판독할 연결이 없습니다 · 실행 없음',
                   steps=steps + [{'stage': 'decision', 'status': 'not_connected'}],
                   observed=observed, navigate=navigation, unknown=['런타임 실행'])


def diagnose(item_id, root=None, values=None, character=None):
    """Projection-only diagnosis. No input, no writes, no navigation performed."""
    if item_id in PRODUCT_ABSENT:
        return _record(item_id, 'unsupported', 'manual_only',
                       '현재 목록의 수동 항목 · 자동 처리 경로가 등록되어 있지 않음 · 게임 실행 미시험')
    if item_id in RUNTIME_ONLY:
        return _record(item_id, 'action_ready', 'runtime_connected',
                       f'코드 연결 확인 · {RUNTIME_ONLY[item_id]} 동작은 점검에서 실행하지 않음',
                       steps=[{'stage': 'decision', 'status': 'not_connected'}],
                       unknown=[RUNTIME_ONLY[item_id]])
    if item_id in NO_DIAGNOSTIC:
        return _record(item_id, 'unsupported', 'no_documented_diagnostic',
                       '판독 근거가 아직 연결되지 않았습니다(제품 기능 여부 미확인)')
    if root is None:
        return _record(item_id, 'unsupported', 'root_missing', '프로그램 경로가 없습니다')
    base = app_root(root)
    if values is None:
        document = _json(base / 'settings/auto-settings.json') or {}
        values = _flatten(document.get('values')) if isinstance(document.get('values'), dict) else {}
    if item_id in JOBS or item_id in SHOP_JOBS:
        return _job(item_id, base, values)
    if item_id == 'hunt':
        return _hunt(item_id, base, values)
    if item_id == 'potion':
        return _potion(base, values)
    if item_id in FLAGS:
        return _flag(item_id, values)
    return _record(item_id, 'unsupported', 'no_documented_diagnostic',
                   '이 기능의 판정 근거가 아직 연결되지 않았습니다')


def _flatten(value, prefix=''):
    out = {}
    for key, item in value.items():
        name = prefix + '.' + key if prefix else key
        if isinstance(item, dict):
            out.update(_flatten(item, name))
        else:
            out[name] = item
    return out


def readiness(item_id, frames, detector=None):
    """Evidence from two frames the caller already captured. Never sends input."""
    if item_id not in READINESS:
        return _record(item_id, 'unsupported', 'no_documented_diagnostic', '준비 판독 대상이 아닙니다')
    if not isinstance(frames, (tuple, list)) or len(frames) != 2 or any(not hasattr(frame, 'shape') for frame in frames):
        return _record(item_id, 'menu', 'frame_missing', '같은 상태의 두 화면이 필요합니다')
    first, second = frames
    if item_id == 'inventory':
        from owner_progression import inventory_parts
        ok = inventory_parts(first) == inventory_parts(second) == (True, True)
        return _record(item_id, 'action_ready' if ok else 'menu',
                       'inventory_ready' if ok else 'inventory_not_proved',
                       '인벤토리 좌우 패널 두 화면 확인 · 실행 없음' if ok else '인벤토리 패널 미확인',
                       steps=[{'stage': 'menu', 'status': 'opened' if ok else 'not_proved'}])
    if item_id in ('main', 'story', 'daily', 'weekly'):
        from owner_skill_ui import quest_screen
        ok = bool(quest_screen(first) and quest_screen(second))
        return _record(item_id, 'action_ready' if ok else 'menu',
                       'quest_tab_ready' if ok else 'quest_tab_not_proved',
                       '임무 화면 두 번 확인(수락/선택은 하지 않음)' if ok else '임무 화면 미확인',
                       steps=[{'stage': 'menu', 'status': 'opened' if ok else 'not_proved'}])
    if detector is None:
        return _record(item_id, 'menu', 'parser_missing', '기운 발현 판독기에 검출기가 필요합니다')
    ok = all(detector.find('체크_기운발현_기운발현', frame, threshold=.96) for frame in (first, second))
    return _record(item_id, 'action_ready' if ok else 'menu',
                   'energy_ready' if ok else 'energy_not_proved',
                   '기운 발현 화면 두 번 확인 · 실행 없음' if ok else '기운 발현 화면 미확인',
                   steps=[{'stage': 'menu', 'status': 'opened' if ok else 'not_proved'}])
