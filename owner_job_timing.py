"""When a side job may run during a quest (user 11-06).

While the character walks or fights in a main or story quest, only short jobs run: rewards, the shop, the summon, the
album. Long ones (growth, higher-grade equip, disassembly, boxes, missions, the clan request that teleports home) wait
for a quest's end (the quest loop's boundary, after a reward or a death), or for the hunt when no quest can run.
pc1 14:02: a disassembly started on the walk and failed when the arrival dialogue opened.

After a death the equip and growth checks are brought forward, so the retry has whatever the bag and the materials
allow (pc2: 4 better armour pieces sat unworn through 4 deaths).
"""
import logging,threading
from datetime import datetime

LOG=logging.getLogger('project_gui.DKB')
LONG_TIMETABLE=frozenset(('gear','growth','gear_equip','blessing_equip','inventory','daily_missions','weekly_missions','clan_request'))
LONG_REWARDS=frozenset(('auto_register.equipment_disassembly.enabled','auto_register.market.enabled'))
QUEST_MODES=('main_quest','sub_quest')
LOCAL=threading.local()


def special_area():
    """In a dungeon, raid, world boss or another instance (user 11-06: there too only short jobs)."""
    from owner_schedule_priority import LOCAL as priority
    from owner_timetable import LOCAL as timetable
    return bool(getattr(priority,'combat',None) or getattr(timetable,'job',None) or getattr(timetable,'native_job',None))


def long_ok(adapter):
    """Long jobs: outside quests and special areas, in the hunt, or at a quest's boundary."""
    if special_area():return False
    return getattr(adapter,'mode',None) not in QUEST_MODES or getattr(LOCAL,'boundary',False)


class boundary:
    """The quest loop's own boundary: long jobs may run inside it."""
    def __enter__(self):self.previous=getattr(LOCAL,'boundary',False);LOCAL.boundary=True
    def __exit__(self,*exc):LOCAL.boundary=self.previous


def pick(adapter,due):
    """The first due job this moment allows; long ones stay due for the next boundary or hunt."""
    for job in due:
        if job.key not in LONG_TIMETABLE or long_ok(adapter):return job
    return None


def after_death(adapter):
    """Bring the equip and growth checks forward to now, once per death. Only jobs the user switched on."""
    try:
        from owner_timetable import planner,EQUIP_JOBS,BY_KEY,enabled
        plan=planner(adapter);now=datetime.now();moved=[]
        for key in ('gear_equip','blessing_equip','gear'):
            job=BY_KEY.get(key);item=plan.state.get(key)
            if job is None or item is None or not enabled(job,plan.values):continue
            flag='equip_recheck' if key in EQUIP_JOBS else 'growth_recheck'
            item.update(status='pending',at=now.isoformat(),attempts=0,**{flag:True})
            moved.append(job.label)
        if moved:
            plan.commit();LOG.info('사망 후 재도전 전 · %s 먼저 확인',' · '.join(moved))
        return moved
    except Exception as exc:
        LOG.info('사망 후 성장 앞당김 보류 · %s',exc);return []


ARROW_EVERY=180.
BAG_AREA=(1068,150,237,590)   # real: the bag's tiles


def green_arrows(real):
    """Green arrow pixels over the bag: the game marks a spare better than what is worn (an empty part included)."""
    import numpy as np
    x,y,w,h=BAG_AREA;t=np.asarray(real)[y:y+h,x:x+w].astype(np.int32)
    return int(((t[...,1]>t[...,0]+50)&(t[...,1]>t[...,2]+50)&(t[...,1]>120)).sum())


def arrow_check(adapter,context,inputs):
    """At a quest's boundary, a look at the bag's equipment for the green arrow, at most every ARROW_EVERY seconds.
    A marked spare brings the higher-grade equip forward. True when it did."""
    import time
    if not long_ok(adapter) or time.monotonic()<getattr(adapter,'_owner_arrow_check_at',0):return False
    adapter._owner_arrow_check_at=time.monotonic()+ARROW_EVERY
    try:
        from owner_timetable import planner,BY_KEY,enabled
        plan=planner(adapter);job=BY_KEY.get('gear_equip');item=plan.state.get('gear_equip')
        if job is None or item is None or not enabled(job,plan.values):return False
        from project_adapter.town_services import TownServices
        from project_adapter import market_inventory
        from owner_progression import open_inventory_by_key,inventory_parts
        import owner_hd as hd,owner_upgrade_equip as up,owner_worn_stats as worn
        service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES);service.context=context
        if getattr(service.capture(),'hi',None) is None:return False
        if open_inventory_by_key(service) is False or inventory_parts(service.capture())[1] is not True:return False
        try:
            service.click_hit(hd.real_hit(*up.BAG_FILTER));context.wait(1.)
            count=green_arrows(service.capture().hi)
        finally:worn.close_bag(service,context)
        if count<25:return False
        item.update(status='pending',at=datetime.now().isoformat(),attempts=0,equip_recheck=True);plan.commit()
        LOG.info('임무 경계 · 가방에 더 좋은 장비 표시 · 높은 등급 장착 앞당김');return True
    except Exception as exc:
        LOG.info('임무 경계 가방 확인 보류 · %s',exc);return False
