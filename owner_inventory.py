"""Explicit early-gear allowlist. No automatic general selection-box use."""
ALLOWED_ITEMS=(
    '버튼_인벤토리_희귀무기상자',
    '버튼_인벤토리_희귀방어구상자',
    '버튼_희귀_장신구상자',
)


def install(gui):
    if getattr(gui,'_owner_inventory',False):return
    from project_adapter import market_inventory
    # Native routine iterates this module global and preserves its existing
    # high-confidence item match, normal->rare choice and equip confirmations.
    market_inventory.INVENTORY_USE_ITEMS=list(ALLOWED_ITEMS)
    market_inventory.RARE_ACCESSORY_PRIORITY=['팔찌','반지']
    if not getattr(market_inventory.run_inventory_use,'_owner_inventory_cooldown',False):
        from functools import wraps
        import time
        ordinary=market_inventory.run_inventory_use
        @wraps(ordinary)
        def use(adapter,context,inputs):
            if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return False
            from owner_progression import state
            interval=300 if state(adapter).level==50 else 45
            if not getattr(adapter,'_owner_preparing_gears',False) and time.monotonic()-getattr(adapter,'_owner_inventory_completed',-1e30)<interval:
                return True
            result=ordinary(adapter,context,inputs)
            if result is not False:adapter._owner_inventory_completed=time.monotonic()
            return result
        use._owner_inventory_cooldown=True;market_inventory.run_inventory_use=use
    gui._owner_inventory=True
    gui.logger.debug('상자 정책 · 희귀 장비와 없는 팔찌·반지만 사용 · 노란 선택상자·기운재료·전리품·전설재료 보관')
