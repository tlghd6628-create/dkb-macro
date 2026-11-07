"""The clan battle start read as one time as well as a window.

Before the Saturday 08:00 deadline the 미혹의 정원 tab shows a window ('토요일20:00-20:30전투시작', pc1 11-06 18:43);
after it, the game shows the clan's own start ('진행 시간 토요일 20:28 전투 시작', pc2 11-07, read .99-1.0). The native
parser only knew the window, so the 20:00 guess stood and 20:00:22 found no entry button (pc2 11-07). The native
answer is kept whenever it has one.
"""
import logging,re

LOG=logging.getLogger('project_gui.DKB')
ONE=re.compile(r'([월화수목금토일])요일(\d{1,2}):(\d{2})전투시작')


def parse(text,native=None):
    if native is not None:
        found=native(text)
        if found is not None:return found
    m=ONE.search(re.sub(r'\s','',str(text)))
    if not m:return None
    hour,minute=int(m.group(2)),int(m.group(3))
    if hour>23 or minute>59:return None
    LOG.info('문파 전투 시작 시각 · %s %02d:%02d',m.group(1),hour,minute)
    return (m.group(1),hour,minute)


def install(gui=None):
    try:import project_adapter.clan_boss_request as native
    except ImportError:return
    original=native.parse_combat_start
    if getattr(original,'_owner_clan_time',False):return
    def parse_combat_start(text):return parse(text,original)
    parse_combat_start._owner_clan_time=True
    native.parse_combat_start=parse_combat_start
