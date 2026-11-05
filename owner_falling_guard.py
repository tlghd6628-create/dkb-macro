"""Stop the falling battle for the day after repeated deaths, since other players can kill there.

The native route goes home and enters again, up to 20 deaths. Here a death soon after entering counts as in a
row, and at the saved count the next entry is refused, so the normal routine carries on until the next game day.
"""
import copy,json,logging,re,time
from functools import wraps
from pathlib import Path

LOG=logging.getLogger('project_gui.DKB')
SWITCH='auto_schedule.falling_battle.enabled'
LIMIT_KEY='auto_schedule.falling_battle.death_limit'
LIMIT_MAX=10;DEFAULT='3회'
SURVIVED=300  # seconds alive in one entry that end a run of deaths
STOP_FILE='settings/owner-falling-stop.json'
DEATH=re.compile(r'^낙화 사망 확인')


def add_fields(schema):
    """Under the switch, in the same field shape as the raid entry count."""
    groups=[g for t in schema['tabs'] for g in t['groups']]
    entries={f['id']:(g,f) for g in groups for f in g['fields']}
    if SWITCH not in entries or LIMIT_KEY in entries or 'auto_schedule.boss_raid.entry_count' not in entries:return schema
    group,switch=entries[SWITCH]
    made=copy.deepcopy(entries['auto_schedule.boss_raid.entry_count'][1])
    made.update(id=LIMIT_KEY,label='연속 사망 시 중단',choices=['%d회'%n for n in range(1,LIMIT_MAX+1)],
                default=DEFAULT,existing_default=DEFAULT,settings_only=True,capability=switch.get('capability',made.get('capability')))
    group['fields'].insert(group['fields'].index(switch)+1,made)
    return schema


def limit_of(values):
    found=re.fullmatch(r'(\d{1,2})회',str((values or {}).get(LIMIT_KEY,DEFAULT)))
    number=int(found[1]) if found else 3
    return number if 1<=number<=LIMIT_MAX else 3


class Deaths:
    """Deaths in a row. Surviving long enough in one entry starts the count over."""
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.count=0;self.entered=None
    def entering(self):self.entered=self.clock()
    def died(self):
        survived=self.entered is not None and self.clock()-self.entered>=SURVIVED
        self.count=1 if survived else self.count+1


class Counter(logging.Filter):
    """The native route says when it confirmed a death; this only listens."""
    def __init__(self,deaths):
        super().__init__();self.deaths=deaths
    def filter(self,record):
        if DEATH.match(str(record.msg)):self.deaths.died()
        return True


def game_day():
    from owner_timetable import day_at,now
    return day_at(now()).isoformat()


def stopped_today(root,day):
    try:return json.loads((Path(root)/STOP_FILE).read_text(encoding='utf-8')).get('day')==day
    except (OSError,ValueError,AttributeError):return False


def stop_today(root,day,count):
    try:(Path(root)/STOP_FILE).write_text(json.dumps({'day':day,'deaths':count}),encoding='utf-8')
    except OSError as exc:LOG.warning('낙화 중단 기록 실패 · %s',exc)


def guard(flow_class,boundary,deaths,*,day=game_day):
    """Wrap entry. Boundary is how the native route already reports 'skip this and carry on'."""
    if getattr(flow_class,'_owner_falling_guard',False):return
    ordinary=flow_class.enter
    @wraps(ordinary)
    def enter(flow,*args,**kwargs):
        adapter=flow.adapter
        root=adapter.project.root;today=day()
        if stopped_today(root,today):
            raise boundary('낙화의전장 오늘 중단 · 연속 사망 · 다음 날 다시 시도')
        limit=limit_of(adapter.values)
        if deaths.count>=limit:
            count=deaths.count;deaths.count=0
            stop_today(root,today,count)
            text='낙화의전장 연속 사망 %d회 · 오늘 중단 · 원래 루틴으로 복귀'%count
            LOG.warning(text,extra={'gui_message':text,'state_transition':True})
            raise boundary(text)
        deaths.entering()
        return ordinary(flow,*args,**kwargs)
    flow_class.enter=enter
    flow_class._owner_falling_guard=True


def install():
    from project_adapter import falling_battle as native
    if getattr(native.FallingBattle,'_owner_falling_guard',False):return
    deaths=Deaths()
    LOG.addFilter(Counter(deaths))
    guard(native.FallingBattle,native.Boundary,deaths)
