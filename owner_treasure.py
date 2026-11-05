"""Only known routes with sufficient combat power; unknown routes stay queued."""
from functools import wraps
import logging,time
from owner_progression import state
LOG=logging.getLogger('project_gui.DKB')
# The native entry itself only has maps for this region (ENABLED_REGIONS); the
# other two return "해당 지방 준비 중" before any input. Nothing here changes that.
REGION_SETTING='auto_challenge.treasure_hunt.region'
# Native point 2 (영험한 청산, 5 maps, 21 chests), 3 (안개 기슭 지하, 4) and 4
# (산신의 영역 지하, 4) all take the same walk: the native card check still
# requires the green (sufficient) power digits before it clicks 진입.
POWER_ROUTES=('포인트_보물찾기_타바로2','포인트_보물찾기_타바로3','포인트_보물찾기_타바로4')


def allowed_points(power,recent_death=False):
    points=['포인트_보물찾기_타바로1']  # Town route: no combat-power requirement.
    # The full second route reaches an 85,050 requirement. 50% headroom is a
    # conservative local policy, not a guarantee that every build survives.
    if isinstance(power,int) and power>=127575 and not recent_death:points.extend(POWER_ROUTES)
    return points


def install(gui):
    from project_adapter._entry import Adapter
    from project_adapter import treasure_entry
    if getattr(Adapter.run_treasure_region_entry,'_owner_treasure_gate',False):return
    ordinary=Adapter.run_treasure_region_entry
    @wraps(ordinary)
    def run(adapter,context,inputs):
        context.checkpoint();progress=state(adapter)
        power=progress.power if time.monotonic()-progress.observed<=300 else None
        allowed=allowed_points(power,time.monotonic()-progress.last_death<600)
        original=treasure_entry.REGIONS['타바로지방']
        selected=[p for p in original[2] if p in allowed]
        region=adapter.values.get(REGION_SETTING) if isinstance(getattr(adapter,'values',None),dict) else None
        LOG.info('보물찾기 안전 조건 · 지방=%s · 전투력=%s · 허용 경로=%s · 미확인 고위험 경로 보류',region,power,','.join(selected))
        if power is None:LOG.info('보물찾기 전투력 미확인 · 5분 내 판독 없음 · 타바로1만 허용')
        treasure_entry.REGIONS['타바로지방']=(original[0],original[1],selected)
        try:return ordinary(adapter,context,inputs)
        finally:treasure_entry.REGIONS['타바로지방']=original
    run._owner_treasure_gate=True;Adapter.run_treasure_region_entry=run;gui._owner_treasure_gate=True
