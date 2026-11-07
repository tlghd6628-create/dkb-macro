"""A death inside a 비경 ends that visit and holds the 비경 jobs until the power grows 15%.

짱군네 11-07 (power 92K): the overdue 비경탐험 entered at 15:39 and 15:50, and both times the 87K 외눈 파수견 and its
pack killed the character. The native loop never answered the death screen (15:51:16 death, nothing for minutes), and
each restart walked straight back in. The quest rule (a death holds it until +15% power) is used here too.
"""
import logging,math,time

LOG=logging.getLogger('project_gui.DKB')
JOBS=('daily_dungeon','daily24_dungeon','weekly_dungeon')
RATIO=1.15
NO_POWER_HOURS=6
PATH='settings/owner-dungeon-death.json'


class DungeonDied(BaseException):
    """The death screen showed inside a 비경, read in the native loop's own sleeps."""


def _who(adapter):
    from owner_timetable import identity
    return identity(adapter.project.root)


def _power(adapter):
    try:
        from owner_progression import state
        value=state(adapter).power
    except Exception:return None
    return value if type(value) is int and value>0 else None


def _load(adapter):
    from owner_timetable import read
    data=read(adapter.project.root/PATH,{})
    return data if isinstance(data,dict) else {}


def died(adapter,now=None):
    """Record this death at the power known now; returns the record."""
    from owner_timetable import save
    data=_load(adapter);who=_who(adapter);old=data.get(who) if isinstance(data.get(who),dict) else {}
    record=dict(deaths=int(old.get('deaths',0))+1,power=_power(adapter),at=time.time() if now is None else now)
    data[who]=record;save(adapter.project.root/PATH,data)
    return record


def held(adapter,now=None):
    """None when 비경 may run, else the reason it is held."""
    record=_load(adapter).get(_who(adapter))
    if not isinstance(record,dict) or not record.get('deaths'):return None
    base=record.get('power');power=_power(adapter)
    if type(base) is int and base>0:
        need=math.ceil(base*RATIO)
        if type(power) is int and power>=need:return None
        return f'비경 사망 {record["deaths"]}회 · 전투력 {f"{power:,}" if power else "모름"}/{need:,}'
    at=record.get('at') or 0
    if (time.time() if now is None else now)-at>=NO_POWER_HOURS*3600:return None
    return f'비경 사망 {record["deaths"]}회 · 사망 때 전투력 모름 · {NO_POWER_HOURS}시간 뒤 다시'


def gate(adapter,job):
    if job.key not in JOBS:return None
    reason=held(adapter)
    if reason is None:return None
    LOG.info('%s 보류 · %s',job.label,reason)
    return True


def dead_now(frame):
    from owner_real_marks import death_mark
    try:return death_mark(frame) is not None
    except Exception:return False


def recover(flow):
    """Press 나가기 on the death screen, record it, and bring the growth checks forward."""
    from owner_death_real import recover as real_death
    from owner_mission_ui import MissionUI
    adapter=flow.adapter
    pressed=real_death(MissionUI(adapter,flow.context,flow.inputs))
    record=died(adapter)
    LOG.warning('비경 사망 · 나가기 %s · 전투력 %s · 15%% 오를 때까지 비경 보류',
                '누름' if pressed else '확인 못 함',f'{record["power"]:,}' if record['power'] else '모름')
    try:
        from owner_job_timing import after_death
        after_death(adapter)
    except Exception as exc:LOG.info('비경 사망 후 성장 앞당김 보류 · %s',str(exc)[:80])
    return pressed
