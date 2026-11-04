"""Only known routes with sufficient combat power; unknown routes stay queued."""
from functools import wraps
import logging,time
from owner_progression import state
LOG=logging.getLogger('project_gui.DKB')


def allowed_points(power,recent_death=False):
    points=['포인트_보물찾기_타바로1']  # Town route: no combat-power requirement.
    # The full second route reaches an 85,050 requirement. 50% headroom is a
    # conservative local policy, not a guarantee that every build survives.
    if isinstance(power,int) and power>=127575 and not recent_death:points.append('포인트_보물찾기_타바로2')
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
        LOG.info('보물찾기 안전 조건 · 전투력=%s · 허용 경로=%s · 미확인 고위험 경로 보류',power,','.join(selected))
        treasure_entry.REGIONS['타바로지방']=(original[0],original[1],selected)
        try:return ordinary(adapter,context,inputs)
        finally:treasure_entry.REGIONS['타바로지방']=original
    run._owner_treasure_gate=True;Adapter.run_treasure_region_entry=run;gui._owner_treasure_gate=True
