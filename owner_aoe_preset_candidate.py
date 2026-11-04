"""Offline candidate: one AoE preset, never select or edit preset 2.

No integration is installed here. Live use requires a separately implemented
candidate-aware image backend and fresh, independently verified observations.
In particular the shipped candidate catalog explicitly marks icon 59 unproved.
"""
import math

class Hold(RuntimeError):
    pass

SLOTS=(68,84,59,55,63,89,25,64)
ORDER=(68,84,65,89,59,25,55,63,64)

def _fresh_pair(evidence, expected, now, max_age):
    if type(now) not in (int,float) or not math.isfinite(now):raise Hold('화면 시각 확인 필요')
    if not isinstance(evidence,dict) or evidence.get('character')!=expected:
        raise Hold('캐릭터별 연쇄 번개 증거 필요')
    if evidence.get('source')!='game-screen' or evidence.get('skill_id')!=59 or evidence.get('name')!='연쇄 번개':
        raise Hold('연쇄 번개 실제 화면 대조 필요')
    frames=evidence.get('frames')
    if not isinstance(frames,list) or len(frames)!=2:raise Hold('연쇄 번개 두 화면 필요')
    ids=[]
    for f in frames:
        if not isinstance(f,dict) or f.get('name_verified') is not True or f.get('icon_verified') is not True:
            raise Hold('연쇄 번개 이름·아이콘 이중 확인 필요')
        t=f.get('captured_monotonic');ident=f.get('id')
        if (type(t) not in (int,float) or not math.isfinite(t) or t>now or now-t>max_age
                or not isinstance(ident,str) or not ident.strip()):
            raise Hold('신선한 실제 화면 확인 필요')
        ids.append(ident)
    if ids[0]==ids[1]:raise Hold('서로 다른 실제 화면 필요')

def configure_aoe(ui,ledger,catalog,*,character,owned_verified,read_icon_evidence,
                  backend_verified,clock,max_age=3.0,checkpoint=lambda:None):
    """Use existing guarded UI methods. Caller must be the sole input owner.

    `backend_verified` is an integration precondition, not proof produced by
    this module: original SkillUI.icon reads a different global catalog. Only a
    real candidate-aware backend may set it true. Fake tests must be labeled.
    """
    if not isinstance(character,str) or not character.strip():raise Hold('캐릭터 확인 필요')
    now=clock()
    if (type(now) not in (int,float) or not math.isfinite(now) or
        type(max_age) not in (int,float) or not math.isfinite(max_age) or max_age<=0):
        raise Hold('화면 시각 확인 필요')
    notes=catalog.get('candidate_notes',{})
    if backend_verified is not True or notes.get('icon_59_game_match_verified') is not True:
        raise Hold('연쇄 번개 후보 이미지·인식 백엔드 미검증')
    evidence=read_icon_evidence();_fresh_pair(evidence,character,clock(),max_age)
    row=catalog.get('presets',{}).get('aoe',{})
    try:
        slots=tuple(s['id'] for s in row['slots'])
        order=[s['id'] for s in row['order']]
        order.insert(row['ultimate_at'],row['ultimate']['id'])
    except (KeyError,TypeError,IndexError):raise Hold('광역 설정 데이터 확인 필요')
    if slots!=SLOTS or tuple(order)!=ORDER or row.get('preset')!=1:
        raise Hold('사용자 광역 구성 불일치')
    if not isinstance(owned_verified,(set,frozenset)) or not set(SLOTS).issubset(owned_verified):
        raise Hold('모든 광역 도술의 학습 여부 확인 필요')
    checkpoint();ui.select_preset(1);checkpoint()
    unlocked=ui.unlocked()
    if not isinstance(unlocked,(set,frozenset)) or unlocked!=set(range(8)):
        raise Hold('추가 도술 슬롯 미개방 또는 상태 미확인')
    for index,sid in enumerate(slots):
        checkpoint()
        if sid==59:
            evidence=read_icon_evidence();_fresh_pair(evidence,character,clock(),max_age)
        ui.equip(sid,index);checkpoint()
    # Existing set_order reopens the dialog and verifies the saved order.
    ui.set_order(order);checkpoint()
    if ui.current_slots(set(range(8)))!=list(slots):
        raise Hold('광역 프리셋 최종 슬롯 불일치')
    ledger.preset_receipt('aoe',list(slots),order,missing=())
    return True
