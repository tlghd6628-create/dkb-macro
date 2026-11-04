"""Separate an unimplemented check from an observed recognition failure.

A row may carry an explicit (stage, finding) pair produced by the checker. The
stage is the exact point where the feature is blocked, so the report no longer
falls back to a generic "확인 필요". Legacy detail-based heuristics stay as a
fallback for rows written by older builds.
"""
STAGE_LABELS={
 ('action_ready','no_eligible_item'):'등록 가능한 장비 없음',
 ('action_ready','enhancement_required'):'강화 50 필요',
 ('action_ready','game_limit'):'게임 상한 도달',
 ('unsupported','manual_only'):'수동 항목',
 ('unsupported','no_documented_diagnostic'):'점검 미연결',
 ('action_ready','config_only'):'설정 확인·동작 미시험',
 ('action_ready','anchor_unverified'):'설정 확인·화면 미검증',
 ('action_ready','projection_only'):'설정 확인·동작 미시험',
 ('action_ready','scheduled'):'예약 기록 확인',
 ('action_ready','schedule_unproven'):'실행 기록 없음',
 ('action_ready','runtime_connected'):'코드 연결 확인·동작 미시험',
 ('values','rules_unreadable'):'사냥터 설정 판독 실패',
 ('config','goal_missing'):'목표 설정 없음',
 ('config','goal_invalid'):'목표 설정 오류',
 ('action_ready','goal_reached'):'목표 도달',
 ('action_ready','goal_missing'):'목표 설정 없음',
 ('action_ready','goal_invalid'):'목표 설정 오류',
 ('config','goal_off'):'목표 꺼짐',
 ('config','breakthrough_disabled'):'돌파 자동 사용 안 함',
 ('values','materials_unreadable'):'재료 판독 실패',
 ('action_ready','ready'):'실행 준비 확인',
 ('values','materials_short'):'재료 부족',
 ('config','settings_off'):'설정 꺼짐',
 ('config','settings_missing'):'설정 누락',
 ('contract','contract_error'):'구성 오류',
 ('menu','field_not_proven'):'화면 상태 확인',
 ('menu','menu_unrecognized'):'메뉴 인식 실패',
 ('menu','probe_error'):'점검 중 오류',
 ('values','values_unreadable'):'수치 판독 실패',
 ('action_ready','decision_not_probed'):'실행 판정 미연결',
 ('action_ready','schedule_preview'):'예약 계산 확인',
 ('unsupported','disabled'):'사용 불가',
 ('unsupported','no_probe_path'):'점검 미연결',
 ('unsupported','not_implemented'):'기능 미구현',
 ('skipped','navigation_stopped'):'앞 항목 미확인으로 중단',
}
STAGE_NAMES={'config':'설정','contract':'구성','menu':'메뉴 진입','values':'수치 판독',
             'action_ready':'실행 직전','unsupported':'미연결','skipped':'중단'}


def stage_label(row):
    key=(row.get('stage'),row.get('finding'))
    if key in STAGE_LABELS:return STAGE_LABELS[key]
    return STAGE_NAMES.get(row.get('stage'),'—')


def stage_name(row):
    return STAGE_NAMES.get(row.get('stage'),'—')


LEVELS={'L0':'설정·파일 연결','L1':'메뉴 진입·화면 확인','L2':'현재값 판독','L3':'실행 조건 판정',
        'L4':'실제 입력 1회·결과 확인','L5':'재시작·중단·복귀 포함 반복'}


NEXT_STEPS={**{key:'실제 게임에서 1회 실행해 결과 확인' for key in ('decision_not_probed','projection_only','config_only','scheduled','schedule_unproven','runtime_connected')},
 'anchor_unverified':'메뉴 도달을 증명할 화면 이미지 확보',
 'navigation_stopped':'앞 항목의 복귀 실패를 해결한 뒤 재점검',
 'cancelled':'다시 점검',
 'field_not_proven':'일반 필드에서 다시 점검',
 'probe_error':'저장 화면으로 버튼 이미지와 기준 확인',
 'menu_unrecognized':'저장 화면으로 메뉴 확인 이미지와 기준 확인',
 'values_unreadable':'비교 화면과 실패 단계로 판독 확인',
 'materials_unreadable':'저장 화면으로 재료·버튼 판독 확인',
 'rules_unreadable':'사냥터 설정 파일 확인',
 'contract_error':'누락된 파일·함수 복구',
 'settings_missing':'설정 파일 항목 확인',
 'goal_invalid':'목표 설정값 확인'}


def verification(row):
    """How far this row was actually proven, over which targets, and what is left.

    The checker sends no resource input, so it can never report L4 or L5.
    """
    level=None
    if row.get('contract_ok') is True:level='L0'
    if row.get('screen_verified') is True:level='L1'
    if row.get('screen_verified') is True and row.get('values_verified') is True:level='L2'
    if level=='L2' and row.get('finding') in ('ready','goal_reached','game_limit','materials_short','enhancement_required'):level='L3'
    if row.get('screen_verified') is True and row.get('decision_verified') is True:level='L3'
    targets=row.get('targets') if isinstance(row.get('targets'),dict) else None
    result={'level':level,'level_name':LEVELS.get(level,'검증 없음'),'targets':targets,'gameplay_executed':False}
    outcome=assessment(row)['outcome']
    if outcome=='unverified':result['unverified_reason']=STAGE_LABELS.get((row.get('stage'),row.get('finding')),'판정 근거 부족')
    if outcome in ('unverified','error'):result['next_step']=NEXT_STEPS.get(row.get('finding'),'저장된 화면과 로그로 원인 확인')
    return result


def level_counts(rows):
    counts={}
    for row in rows:
        name=verification(row)['level'] or 'none';counts[name]=counts.get(name,0)+1
    return counts


def scope_text(row):
    targets=row.get('targets') if isinstance(row.get('targets'),dict) else None
    if not targets or type(targets.get('read')) is not int or type(targets.get('total')) is not int:return ''
    return f" · {targets.get('unit','대상')} {targets['read']}/{targets['total']}"


def assessment(row):
    """Diagnostic health, with the target range a verdict actually covers."""
    result=_assessment(row)
    if result['outcome'] in ('normal','waiting'):result=dict(result,label=result['label']+scope_text(row))
    return result


def _assessment(row):
    """Diagnostic health is separate from a game's waiting/disabled state."""
    finding=row.get('finding');key=(row.get('stage'),finding)
    if finding in ('settings_off','goal_off','disabled','manual_only','breakthrough_disabled'):
        return {'outcome':'excluded','label':'제외 · '+STAGE_LABELS.get(key,'설정 꺼짐'),'scope':'설정'}
    if row.get('result')=='중지' or finding in ('cancelled','navigation_stopped'):
        return {'outcome':'unverified','label':'미검증 · 중단','scope':'미실행'}
    if finding in ('field_not_proven',):
        return {'outcome':'unverified','label':'미검증 · 현재 환경','scope':'메뉴 진입 전'}
    if row.get('result')=='오류' or finding in ('contract_error','settings_missing','goal_invalid','menu_unrecognized',
          'probe_error','values_unreadable','materials_unreadable','rules_unreadable'):
        return {'outcome':'error','label':'오류 · '+STAGE_LABELS.get(key,'점검 오류'),'scope':STAGE_NAMES.get(row.get('stage'),'구성')}
    if row.get('screen_verified') is True and row.get('values_verified') is True:
        if finding=='ready':return {'outcome':'normal','label':'정상 · 실행 준비','scope':'실행 직전 조건'}
        if finding in ('goal_reached','game_limit','materials_short','enhancement_required'):
            return {'outcome':'waiting','label':'정상 대기 · '+STAGE_LABELS[key],'scope':'현재값·조건'}
    if row.get('id')=='schedule' and finding=='schedule_preview' and row.get('result')=='정상':
        return {'outcome':'normal','label':'정상 · 예약 계산','scope':'예약 계산'}
    if row.get('screen_verified') is True and row.get('decision_verified') is True:
        if finding=='no_eligible_item':return {'outcome':'waiting','label':'정상 대기 · 등록 대상 없음','scope':'등록 대상 유무; 단계 미확인'}
        return {'outcome':'normal','label':'정상','scope':'실행 직전 조건'}
    if row.get('stage')=='contract' and row.get('contract_ok') is True:
        return {'outcome':'unverified','label':'미검증 · 화면 미점검','scope':'구성'}
    return {'outcome':'unverified','label':'미검증 · '+STAGE_LABELS.get(key,'판정 근거 부족'),
            'scope':'설정·기록' if row.get('diagnostic') else '화면' if row.get('screen_verified') else '구성'}


def summarize(rows):
    counts={name:0 for name in ('normal','waiting','excluded','error','unverified')}
    for row in rows:counts[assessment(row)['outcome']]+=1
    return counts


def status(row):
    checked=row.get('assessment')
    if isinstance(checked,dict) and checked.get('outcome') in ('normal','waiting','excluded','error','unverified'):
        return checked['label']
    result=row.get('result')
    if result=='중지':return result
    if result=='정상':
        return ('정상' if (row.get('id')=='schedule' and row.get('screen')=='예약 계산')
                or (row.get('screen_verified') is True and row.get('decision_verified') is True) else '미검증')
    if result=='오류':return '점검기 오류' if row.get('contract_ok') else '구성 오류'
    key=(row.get('stage'),row.get('finding'))
    if key in STAGE_LABELS:return STAGE_LABELS[key]
    if row.get('stage')=='contract' and row.get('contract_ok'):return '화면 미점검'
    # Legacy rows (older reports, or a probe that only set detail text).
    reason=row.get('finding');detail=str(row.get('detail',''))
    if reason=='disabled' or row.get('settings')=='사용 불가':return '사용 불가'
    if reason=='unsupported' or '해당 메뉴 판독 연결 필요' in detail:return '점검 미연결'
    if reason=='recognition_failed' or any(t in detail for t in ('버튼 미감지','메뉴 화면 두 번 확인 실패','전체 메뉴 두 화면 인식')):return '메뉴 인식 실패'
    if reason=='context' or '현재 화면을 유지' in detail:return '화면 상태 확인'
    if reason=='value_failed' or any(t in detail for t in ('장비 화면 불일치','장비 동일성','강화 수치 판독 필요','강화 수치 또는 화면','장착 장비와 등급')):return '수치 판독 실패'
    if row.get('screen_verified') is True:return '세부 점검 미완료'
    if '설정 항목 확인 필요' in detail:return '설정 확인'
    return '미검증'
