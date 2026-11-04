"""Local coupon receipt label, independent from remote management/auth."""
from functools import wraps
_identity_provider=None

def identity_values():return _identity_provider() if _identity_provider else {}


class CouponIdentity:
    def __init__(self,store):self.store=store
    def snapshot(self):
        values=self.store.snapshot()
        if not values.get('pc_alias'):values=dict(values,pc_alias='0000')
        return values


def install(gui):
    global _identity_provider
    _identity_provider=gui.identity_store.snapshot
    from project_adapter import coupon_registration as coupons
    if getattr(coupons.coupon_batch,'_owner_local_receipts',False):return
    ordinary=coupons.coupon_batch
    @wraps(ordinary)
    def batch(env):
        store=env.gui.identity_store
        if store.snapshot().get('pc_alias'):return ordinary(env)
        env.gui.identity_store=CouponIdentity(store)
        try:
            env.gui.logger.info('쿠폰 등록 · 로컬 기록 사용 · 원격관제 PC번호 입력 생략')
            return ordinary(env)
        finally:env.gui.identity_store=store
    batch._owner_local_receipts=True;coupons.coupon_batch=batch
    gui._owner_local_coupons=True
