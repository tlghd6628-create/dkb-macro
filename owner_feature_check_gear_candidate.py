"""Read-only pre-action diagnosis for one equipped gear item.

Reuses the existing enhancement reader and the per-character goal document.
It never sends an action, never selects another item beyond the reader's own
documented behaviour, and reports materials as unread rather than guessing.
"""
from pathlib import Path


def goals(root, character):
    """Per-character goal document, or None when it cannot be attributed."""
    if not isinstance(character, str) or not character.strip():return None
    from owner_gear_settings_candidate import Store
    try:document,state=Store(Path(root),character).snapshot()
    except (OSError,ValueError):return None
    if not isinstance(document,dict):return None
    return document


def goal_for(document, grade):
    grades=document.get('grades') if isinstance(document,dict) else None
    if not isinstance(grades,dict) or not isinstance(grade,str):return None
    row=grades.get({'흰':'일반','파랑':'희귀','보라':'영웅'}.get(grade,grade))
    return row if isinstance(row,dict) else None


DETAIL={'goal_missing':'{grade} {level}강 판독 · 이 등급의 목표 설정 없음 · 실행 없음',
        'goal_off':'{grade} {level}강 판독 · 목표 사용 안 함(꺼짐) · 실행 없음',
        'goal_invalid':'{grade} {level}강 판독 · 목표 값 확인 필요 · 실행 없음',
        'goal_reached':'{grade} {level}강 · 목표 {goal}강 도달 · 실행 없음',
        'ready':'{grade} {level}강 · 목표 {goal}강 · 같은 장비·현재 수치·재료·활성 버튼 두 화면 확인 · 실행 없음',
        'materials_short':'{grade} {level}강 · 목표 {goal}강 · 재료 부족 · 실행 없음',
        'materials_unreadable':'{grade} {level}강 · 목표 {goal}강 · {reason} · 실행 없음'}
STEP={'goal_missing':('decision','goal_missing'),'goal_off':('decision','off'),'goal_invalid':('decision','invalid'),
      'goal_reached':('decision','goal_reached'),'materials_short':('materials','insufficient'),
      'materials_unreadable':('decision','materials_unreadable')}


MAX_SECONDS=40


def _one(reading, root, character):
    from owner_growth_reading import enhance_decision
    if not isinstance(reading,dict) or reading.get('verified') is not True or type(reading.get('enhancement')) is not int:
        detail=str((reading or {}).get('detail') or '강화 수치 판독 실패')
        return {'stage':'values','finding':'values_unreadable','values_verified':False,
                'detail':detail+' · 실행 없음','steps':[{'stage':'values','status':'unreadable'}]}
    grade=reading.get('grade');level=reading['enhancement']
    target=goal_for(goals(root,character),grade)
    stage,finding=enhance_decision(target,level,ready=reading.get('native_ready'),materials=reading.get('materials'))
    detail=DETAIL[finding].format(grade=grade or '선택 장비',level=level,goal=(target or {}).get('enhance'),
                                  reason=reading.get('hold_reason') or '재료 수량 판독 미연결')
    steps=[{'stage':'values','status':'read'}]
    if finding=='ready':steps+=[{'stage':'materials','status':'ready'},{'stage':'decision','status':'ready'}]
    else:steps.append(dict(zip(('stage','status'),STEP[finding])))
    return {'values_verified':True,'grade':grade,'level':level,'stage':stage,'finding':finding,'detail':detail,
            'steps':steps,'targets':reading.get('targets')}


def diagnose(service, context, root, character):
    """Every worn item within a time limit, never a resource action."""
    import time
    from owner_feature_check_growth_candidate import read_enhancement
    from owner_growth_reading import worst_row
    rows=[];done=set();deadline=time.monotonic()+MAX_SECONDS;total=1
    while True:
        reading=read_enhancement(service,context,done=tuple(done))
        if isinstance(reading,dict) and reading.get('exhausted'):break
        rows.append(_one(reading,root,character))
        index=reading.get('index') if isinstance(reading,dict) else None
        total=max(total,((reading or {}).get('targets') or {}).get('total',1)) if isinstance(reading,dict) else total
        if rows[-1].get('values_verified') is not True or type(index) is not int or time.monotonic()>=deadline:break
        done.add(index)
    result=dict(worst_row(rows))
    if len(rows)>1 or total>1:result['targets']={'read':len(rows),'total':total,'unit':'장비'}
    if len(rows)>1:result['detail']=str(result['detail'])+f' · 장착 장비 {len(rows)}/{total} 확인'
    return result
