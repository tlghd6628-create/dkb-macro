"""Opt-in isolation for native reward processing; no execution on import.

The original protection helpers see unmodified rows. Only this thread while
the original blessing reward routine is active hides non-worn rows from the
native automatic-equip selection. Other workers and normal equipment scans
see unmodified results. Installation is explicit and not yet live verified.
"""
from functools import wraps
import threading

_local=threading.local()

def _protected(original):
    @wraps(original)
    def wrapped(*args,**kwargs):
        depth=getattr(_local,'protection_depth',0);_local.protection_depth=depth+1
        try:return original(*args,**kwargs)
        finally:_local.protection_depth=depth
    wrapped._owner_blessing_protection_fence=True
    return wrapped

def _inspect(original):
    @wraps(original)
    def wrapped(*args,**kwargs):
        rows=original(*args,**kwargs)
        if not (getattr(_local,'reward_scope',False) and not getattr(_local,'protection_depth',0) and kwargs.get('reward_slots') is True):return rows
        if not isinstance(rows,list):raise RuntimeError('가호 장착 후보 확인 필요')
        return [row for row in rows if isinstance(row,dict) and row.get('equipped') is True]
    wrapped._owner_blessing_inspect_fence=True
    return wrapped

def _reward(original,should_fence):
    @wraps(original)
    def wrapped(adapter,context,inputs,*args,**kwargs):
        if should_fence(adapter) is not True:return original(adapter,context,inputs,*args,**kwargs)
        previous=getattr(_local,'reward_scope',False);_local.reward_scope=True
        try:return original(adapter,context,inputs,*args,**kwargs)
        finally:_local.reward_scope=previous
    wrapped._owner_blessing_reward_fence=True
    return wrapped

def _bound(original):
    """On a real frame the owner's rule answers: any blessing without 귀속 stops 일괄 획득. The tile colours it replaces do not survive 1366."""
    @wraps(original)
    def wrapped(*args,**kwargs):
        service=args[0] if args else None
        capture=getattr(service,'capture',None)
        if callable(capture) and getattr(capture(),'hi',None) is not None:
            from owner_blessing_bound import skip_reason
            return skip_reason(service)
        return original(*args,**kwargs)
    wrapped._owner_blessing_protection_fence=True
    return wrapped

def install(reward_module,market_module,*,should_fence,alias_modules=()):
    if not callable(should_fence):raise ValueError('가호 정책 확인기가 필요합니다')
    from owner_gear_native_install_candidate import _rebind_aliases
    old=market_module.inspect_growth_equipment
    if not getattr(old,'_owner_blessing_inspect_fence',False):
        replacement=_inspect(old);market_module.inspect_growth_equipment=replacement
        _rebind_aliases(alias_modules,old,replacement)
    for name in ('_blessing_tradeable_candidates','_blessing_bulk_skip_reason'):
        old=getattr(reward_module,name)
        if not getattr(old,'_owner_blessing_protection_fence',False):
            setattr(reward_module,name,_bound(_protected(old)) if name=='_blessing_bulk_skip_reason' else _protected(old))
    old=reward_module.run_blessing_rewards
    if not getattr(old,'_owner_blessing_reward_fence',False):
        replacement=_reward(old,should_fence);reward_module.run_blessing_rewards=replacement
        _rebind_aliases(alias_modules,old,replacement)

def real_screen(adapter,context,inputs):
    """Is the game window at 1366x768, where frames carry their real pixels? Sends nothing; False when it cannot tell."""
    try:
        from project_adapter.town_services import TownServices
        from project_adapter import market_inventory
        return getattr(TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES).capture(),'hi',None) is not None
    except (OSError,ValueError,TypeError,RuntimeError,AttributeError,ImportError):return False

def install_runtime(reward_module,market_module,identity_resolver,*,alias_modules=(),runner=None):
    """Run native rewards under the fence, then the separately guarded policy.

    This function installs wrappers only when explicitly called by the owner
    runtime. A native failure is propagated; an unknown identity skips the
    new policy while keeping the original auto-equip fenced.
    """
    if not callable(identity_resolver):raise ValueError('가호 캐릭터 확인기가 필요합니다')
    from owner_gear_native_install_candidate import _rebind_aliases
    from owner_gear_settings_candidate import Store
    install(reward_module,market_module,should_fence=lambda adapter:True,alias_modules=alias_modules)
    old=reward_module.run_blessing_rewards
    if getattr(old,'_owner_blessing_policy_runtime',False):return
    @wraps(old)
    def combined(adapter,context,inputs,*args,**kwargs):
        adapter._owner_blessing_policy_outcome={'state':'not_run'}
        result=old(adapter,context,inputs,*args,**kwargs)
        # A false reward result is not proof that the equipment policy cannot
        # run. Its own entry point independently requires the ordinary field.
        # Preserve the native result and propagate actual native exceptions.
        if result is not True and not callable(getattr(context,'checkpoint',None)):
            adapter._owner_blessing_policy_outcome={'state':'native_unconfirmed'}
            return result
        context.checkpoint()
        identity=identity_resolver(adapter)
        if not isinstance(identity,str) or not identity.strip():
            adapter._owner_blessing_policy_outcome={'state':'hold_identity'};return result
        try:document,revision=Store(adapter.project.root,identity).snapshot()
        except (ValueError,OSError,TypeError,KeyError,AttributeError):
            adapter._owner_blessing_policy_outcome={'state':'hold_settings'};return result
        if revision=='missing':
            adapter._owner_blessing_policy_outcome={'state':'hold_settings'};return result
        setting=document['blessing_equip']
        if setting.get('enabled') is not True:
            adapter._owner_blessing_policy_outcome={'state':'disabled'};return result
        if real_screen(adapter,context,inputs):
            # Its screens are found by pictures cut at 897x479, and at 1366x768 it stopped the whole job (가호 메뉴 확인 필요).
            # Nothing is equipped until it reads the real screen; the job itself goes on.
            import logging
            logging.getLogger('project_gui.DKB').info('가호 높은 등급 우선 장착 건너뜀 · 1366 화면 판독 준비 전 · 장착 변경 없음')
            adapter._owner_blessing_policy_outcome={'state':'skipped_real_screen'};return result
        def current():return Store(adapter.project.root,identity).revision()==revision and identity_resolver(adapter)==identity
        if callable(runner):execute=runner
        else:
            from owner_blessing_navigation_candidate import run_blessing_equipment
            execute=run_blessing_equipment
        adapter._owner_blessing_policy_outcome=execute(adapter,context,inputs,identity,setting['priorities'],settings_check=current)
        if isinstance(adapter._owner_blessing_policy_outcome,dict):
            adapter._owner_blessing_policy_outcome['native_rewards_confirmed']=result is True
        return result
    combined._owner_blessing_policy_runtime=True
    reward_module.run_blessing_rewards=combined
    _rebind_aliases(alias_modules,old,combined)
