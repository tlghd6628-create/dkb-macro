"""Candidate-only bridge to the existing SkillUI; not installed automatically.

The current catalog explicitly withholds live icon verification. The bridge
therefore returns Pending before any UI operation unless genuine validation is
completed by a future capture-based verifier. Does not fetch data or create
threads and does not modify either the original or candidate SkillUI module.
"""
import hashlib, inspect
from pathlib import Path
from owner_aoe_preset_candidate import configure_aoe, Hold, SLOTS, ORDER


def attempt_live_candidate(module,ui,ledger,*,character,checkpoint):
    """AOE preset 1 only; caller owns the original worker, cancellation and cleanup.

    Fresh chain proof is performed inside the current SkillUI.find_skill(59),
    not supplied as a caller-supplied claim. Never changes preset 2. The game
    variant has saved-frame checks on one PC only, not broad live verification.
    """
    from owner_skill_goal import Pending
    try:
        if not isinstance(character,str) or not character.strip() or getattr(ledger,'character',None)!=character:
            raise Hold('현재 캐릭터·도술 기록 일치 확인 필요')
        catalog=module.catalog();checked_backend(module,ui,catalog)
        # Refuse a stale or unpatched UI implementation rather than accepting
        # a synthetic flag as actual two-frame recognition.
        if not callable(getattr(module,'chain59_game_icon',None)) or not callable(getattr(ui,'_click_chain59_paired',None)):
            raise Hold('연쇄 번개 두 화면 판독 경로 없음')
        module.chain59_game_icon()
        row=catalog['presets']['aoe']
        slots=tuple(s['id'] for s in row['slots'])
        order=[s['id'] for s in row['order']]
        order.insert(row['ultimate_at'],row['ultimate']['id'])
        if row.get('preset')!=1 or slots!=SLOTS or tuple(order)!=ORDER:
            raise Hold('요청한 광역 프리셋 구성 불일치')
        checkpoint();owned=ui.scan_owned();checkpoint()
        if not isinstance(owned,set) or not set(SLOTS).issubset(owned):
            raise Hold('광역 도술 학습 확인 필요')
        ui.select_preset(1);checkpoint()
        unlocked=ui.unlocked()
        if unlocked!=set(range(8)):raise Hold('도술 8칸 개방 상태 확인 필요')
        # Always perform the real paired name/icon check even if the desired
        # skill happens to already be equipped and equip() would early-return.
        ui.find_skill(59);checkpoint()
        for i,sid in enumerate(slots):
            checkpoint();ui.equip(sid,i);checkpoint()
        ui.set_order(order);checkpoint()
        if ui.current_slots(set(range(8)))!=list(slots):raise Hold('광역 슬롯 최종 확인 실패')
        ledger.preset_receipt('aoe',list(slots),order,missing=())
        return True
    except (Hold,KeyError,TypeError,ValueError,OSError) as exc:
        raise Pending(str(exc)) from exc

def checked_backend(module,ui,catalog):
    if module.catalog()!=catalog or getattr(ui,'public',None)!=catalog:
        raise Hold('사용 중인 도술 화면과 후보 카탈로그 불일치')
    icon=getattr(module,'icon',None)
    if not callable(icon) or getattr(inspect.unwrap(icon),'__globals__',{}).get('catalog') is not module.catalog:
        raise Hold('기존 도술 아이콘 판독 경로 확인 필요')
    root=Path(module.__file__).resolve().parent
    for skill_id,entry in catalog.get('skills',{}).items():
        try:
            target=(root/entry['icon']).resolve()
            target.relative_to(root)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
        except (OSError,KeyError,ValueError,TypeError) as exc:
            raise Hold('도술 이미지 경로 확인 필요: '+str(skill_id)) from exc
        if digest!=entry.get('icon_sha256'):
            raise Hold('도술 이미지 해시 확인 필요: '+str(skill_id))
        # Existing cached icon data must still match the current catalog file.
        try:
            import cv2, numpy as np
            from PIL import Image
            with Image.open(target) as source:
                expected=cv2.resize(np.asarray(source.convert('RGB')),(32,32),interpolation=cv2.INTER_AREA)
            expected=expected[6:-6,6:-6]
            if not np.array_equal(icon(int(skill_id),32),expected):
                raise Hold('도술 이미지 캐시 확인 필요: '+str(skill_id))
        except Hold:raise
        except Exception as exc:raise Hold('도술 이미지 판독 확인 필요: '+str(skill_id)) from exc
    return True

def attempt(module,ui,ledger,*,character,read_icon_evidence,clock,checkpoint):
    """Caller owns UI, cancel checks, cleanup and exclusive game input.

    `read_icon_evidence` must return an independently verified two-frame proof
    from the current game session. No such verifier is supplied at present.
    """
    from owner_skill_goal import Pending
    try:
        catalog=module.catalog()
        notes=catalog.get('candidate_notes',{})
        if notes.get('icon_59_game_match_verified') is not True:
            raise Hold('연쇄 번개 실제 이미지 대조 미완료')
        if not callable(read_icon_evidence):raise Hold('연쇄 번개 화면 확인기 없음')
        checked_backend(module,ui,catalog)
        checkpoint()
        # Existing owned-only visual scan has its own guarded input checks;
        # do not infer ownership from an old ledger or a previous character.
        owned=ui.scan_owned();checkpoint()
        if not isinstance(owned,set):raise Hold('현재 배운 도술 확인 필요')
        return configure_aoe(ui,ledger,catalog,character=character,owned_verified=owned,
            read_icon_evidence=read_icon_evidence,backend_verified=True,clock=clock,checkpoint=checkpoint)
    except Hold as exc:
        raise Pending(str(exc)) from exc
