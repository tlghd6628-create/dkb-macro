"""Single native input under custom gear targets; not installed automatically.

Integration must provide an independently verified frame reader and a final
    same-item/resource/button verifier. Unknown evidence never falls back to native
bulk growth. Existing bulk path is returned only if all custom grades are off.
"""
from pathlib import Path
from owner_gear_settings_candidate import Store
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_step_guard_candidate import Guard


class FinalUnverified(RuntimeError):pass


def configured_targets(root,character):
    return Store(root,character).read()['grades']


def run_configured_step(service,context,root,character,kind,read_pair,verify_final,*,clock=None,settings_check=None):
    """Perform <=1 native click when proof exists; otherwise return a hold.

    read_pair must use fresh same-worker frames and the existing per-item native
    readers, including independent same-item evidence. verify_final(frame,
    previous_pair,kind) must validate selection, values, active tab/button,
    target and the allowed resource/button state on the immediate pre-input capture.
    Neither producer is yet supplied by the application.
    """
    if not isinstance(character,str) or not character.strip():return 'hold_identity'
    try:targets=configured_targets(root,character)
    except (OSError,ValueError,TypeError):return 'hold_settings'
    if not any(row.get('enabled') is True for row in targets.values()):return 'use_original'
    if not callable(read_pair) or not callable(verify_final):return 'hold_missing_observer'
    if kind not in ('enhance','breakthrough','awaken'):return 'hold_unknown_action'
    from project_adapter import market_inventory, growth_equipment_extra
    names={'enhance':market_inventory.GROWTH_EXEC_BUTTONS[0],
           'breakthrough':growth_equipment_extra.BREAK_BUTTON,
           'awaken':growth_equipment_extra.AWAKE_BUTTON}
    # This path is per verified character; unknown identity never aliases users.
    path=Store(root,character).path.with_name(Store(root,character).path.stem+'-intent.json')
    options={} if clock is None else {'clock':clock}
    guard=Guard(context,IntentStore(path),read_pair,**options)
    def one_native_input(latest,mark_sent):
        context.checkpoint();service.check()
        frame=service.capture()
        if verify_final(frame,latest,kind) is not True:raise FinalUnverified('최종 화면 확인 필요')
        name=names[kind]
        if kind=='enhance' and latest.get('button_name') is not None:
            name=latest['button_name']
            if name not in market_inventory.GROWTH_EXEC_BUTTONS:raise FinalUnverified('강화 실행 버튼 확인 필요')
        hit=service.detector.find(name,frame,threshold=.95)
        if not hit:raise FinalUnverified('해당 실행 버튼 확인 필요')
        context.checkpoint();service.check()
        if callable(settings_check) and settings_check() is not True:raise FinalUnverified('설정 또는 캐릭터 변경')
        # This is one native input call, not the original batch loop.
        mark_sent()
        context.checkpoint();service.check()
        if callable(settings_check) and settings_check() is not True:raise RuntimeError('설정 또는 캐릭터 변경 · 입력 보류')
        service.click_hit(hit)
    try:return guard.run_one(kind,targets,one_native_input)
    except FinalUnverified:return 'hold_final_preinput'


def reconcile_configured_step(context,root,character,read_pair,*,clock=None,before_complete=None):
    if not isinstance(character,str) or not character.strip():return 'hold_identity'
    if not callable(read_pair):return 'hold_missing_observer'
    path=Store(root,character).path.with_name(Store(root,character).path.stem+'-intent.json')
    options={} if clock is None else {'clock':clock}
    return Guard(context,IntentStore(path),read_pair,**options).reconcile(before_complete=before_complete)
