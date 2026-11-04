"""Threshold-based hunt routing candidate; not installed into the product."""
from owner_growth_policy_candidate import choose_hunt_rule
from contextlib import contextmanager

@contextmanager
def hunt_scope(adapter,progress,rules,guide_hunt,slots_module,*,guard=None):
    original=adapter.run_favorite_hunt; had='run_favorite_hunt' in vars(adapter)
    def resume(context,inputs):
        if guard is not None:guard()
        return route_hunt(adapter,context,inputs,progress.power,rules,guide_hunt,slots_module,hunt=original)
    adapter.run_favorite_hunt=resume
    try:yield resume
    finally:
        if had:adapter.run_favorite_hunt=original
        else:del adapter.run_favorite_hunt

def route_hunt(adapter,context,inputs,power,rules,guide_hunt,slots_module,*,hunt=None):
    if type(power) is not int or power<0:raise ValueError('현재 전투력 확인 필요')
    target=choose_hunt_rule(power,rules)
    if target is None:return guide_hunt(adapter,context,inputs)
    from owner_hunt_memory import blocked_saved,set_route,saved_key
    if blocked_saved(adapter,target,power):
        return guide_hunt(adapter,context,inputs)
    original_values=adapter.values
    original_slots=slots_module.available_slots
    chosen=target['slot']
    import logging
    logging.getLogger('project_gui.DKB').info('사냥터 선택 · 전투력 %s · 기준 %s 이상 → 저장 위치 %d번',format(power,','),format(target['power'],','),chosen)
    def checked_slots(*args,**kwargs):
        from owner_town_return import MissingFavorite
        try:slots=original_slots(*args,**kwargs)
        except MissingFavorite as exc:raise RuntimeError('설정한 저장 위치를 확인할 수 없습니다') from exc
        # Native available_slots returns zero-based indexes (UI 2번 -> 1).
        if chosen-1 not in slots:raise RuntimeError('설정한 저장 위치를 확인할 수 없습니다')
        return [chosen-1]
    try:
        adapter.values=dict(original_values,**{'common.potion_and_favorite.enabled':True,'common.potion_and_favorite.source':'저장위치','common.potion_and_favorite.slot':str(chosen)+'번'})
        slots_module.available_slots=checked_slots
        context.checkpoint()
        result=(hunt or adapter.run_favorite_hunt)(context,inputs)
        if result is True or result in ('HUNTING_RESUMED','HUNTING_STARTED'):
            set_route(adapter,saved_key(target),'저장 위치 '+str(chosen))
        return result
    finally:
        slots_module.available_slots=original_slots
        adapter.values=original_values
