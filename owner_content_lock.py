"""Content a character has not opened yet is not tried (user 11-07: 레이드·비경 fail on 짱군네 because they are not open).

짱군네 (level 50, power 36.7K): 비경탐험 failed four times on "전체메뉴 진입 버튼 미감지" and 보스 레이드 spent minutes on
menu retries and five screen recoveries. In the full menu a closed tile's label is dim (90th-percentile brightness
106-119 on 비경 탐험, 승천의 탑, 도깨비 수련장, 유물 수집, 내면의 길) and an open one bright (144-171). 보스토벌 was open
but held only the 필드 보스 tab, no 레이드. The full menu is read once, kept per character, and read again after
RECHECK_HOURS, a level change or a finished quest (they open with the story); until then a closed job is passed over
at its time.
"""
from pathlib import Path
import json,logging,time
LOG=logging.getLogger('project_gui.DKB')
FILE='settings/owner-content-lock.json'
RECHECK_HOURS=6;DIM=132
TILES={'비경탐험':('daily_dungeon','daily24_dungeon'),'승천의탑':('tower',)}
BOSS_TILE='보스토벌';RAID_JOBS=('raid',)
GATED=frozenset(k for keys in TILES.values() for k in keys)|frozenset(RAID_JOBS)
# Real 1366 places.
MENU=(1333,32);CLOSE=(1330,32);MENU_AREA=(945,100,421,545)
TABS=(20,62,700,46);BACK=(35,30)


def _clean(text):
    from owner_text import clean
    return clean(text)


def tiles(real,rows):
    """{label: open} for the menu labels read; open when the label's bright pixels are not dim."""
    import numpy as np
    a=np.asarray(real);found={}
    for r in rows:
        x0,y0,x1,y1=r['bounds'];patch=a[max(0,y0):y1,max(0,x0):x1]
        if patch.size==0:continue
        found[_clean(r['text'])]=float(np.percentile(patch.max(axis=2),90))>=DIM
    return found


def closed_jobs(found,raid_tab):
    """Job keys closed by these tiles; raid_tab is True/False when 보스토벌 was opened, None when not looked at."""
    closed=set()
    for label,keys in TILES.items():
        if found.get(label) is False:closed.update(keys)
    if found.get(BOSS_TILE) is False or raid_tab is False:closed.update(RAID_JOBS)
    return closed


def _who(root):
    from owner_membership import _who as who
    return who(root)


def _level(adapter):
    try:
        from owner_job_timing import known_level
        return known_level(adapter,None)
    except Exception:return None


def kept(adapter,now=None):
    """The kept closed set for this character, or None when there is none, it is old, or the level moved."""
    root=adapter.project.root;who=_who(root)
    if not who:return None
    try:data=json.loads((Path(root)/FILE).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    row=data.get(who) if isinstance(data,dict) else None
    if not isinstance(row,dict):return None
    now=time.time() if now is None else now
    if not 0<=now-row.get('at',0)<RECHECK_HOURS*3600:return None
    if row.get('level')!=_level(adapter):return None
    return set(row.get('closed') or [])


def keep(adapter,closed,now=None):
    root=adapter.project.root;who=_who(root)
    if not who:return
    path=Path(root)/FILE
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):data={}
    if not isinstance(data,dict):data={}
    data[who]=dict(at=time.time() if now is None else now,level=_level(adapter),closed=sorted(closed))
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')


def forget(adapter):
    """A quest ended: what was closed may be open now. Only a kept record with something closed is dropped."""
    root=adapter.project.root;who=_who(root);path=Path(root)/FILE
    if not who or not path.exists():return False
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return False
    row=data.get(who) if isinstance(data,dict) else None
    if not isinstance(row,dict) or not row.get('closed'):return False
    data.pop(who);path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return True


def look(adapter,context,inputs):
    """Open the full menu, read the tiles (and 보스토벌's tabs when it is open), close it. The closed set, or None."""
    import numpy as np,owner_hd as hd
    from owner_mission_ui import MissionUI
    from owner_text import read_area
    from owner_settle import settle
    service=MissionUI(adapter,context,inputs).service
    def real():
        r=getattr(service.capture(),'hi',None)
        return None if r is None else np.asarray(r)
    service.click_hit(hd.real_hit(*MENU));settle(service,context,1.5)
    a=real()
    if a is None:return None
    x,y,w,h=MENU_AREA
    found=tiles(a,read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5))
    if not any(label in found for label in (*TILES,BOSS_TILE)):
        LOG.info('콘텐츠 열림 확인 보류 · 전체메뉴 글자 미확인');service.click_hit(hd.real_hit(*CLOSE));settle(service,context,1.)
        return None
    raid_tab=None
    if found.get(BOSS_TILE):
        rows=[r for r in read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5) if _clean(r['text'])==BOSS_TILE]
        if rows:
            service.click_hit(hd.real_hit(rows[0]['rx'],rows[0]['ry']-24));settle(service,context,2.)
            b=real()
            if b is not None:
                tx,ty,tw,th=TABS
                raid_tab=any('레이드' in _clean(r['text']) for r in read_area(None,b[ty:ty+th,tx:tx+tw],left=tx,top=ty,minimum=.5))
            service.click_hit(hd.real_hit(*BACK));settle(service,context,1.5)
    a=real()
    if a is not None and any(_clean(r['text']) in TILES or _clean(r['text'])==BOSS_TILE for r in read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5)):
        service.click_hit(hd.real_hit(*CLOSE));settle(service,context,1.)
    closed=closed_jobs(found,raid_tab)
    LOG.info('콘텐츠 열림 확인 · 닫힘 %s',' · '.join(sorted(closed)) or '없음')
    return closed


def gate(adapter,job,context,inputs):
    """True when this job's content is not open for the character (the job is passed over), else None."""
    from owner_dungeon_death import gate as death_gate
    if death_gate(adapter,job):return True
    if job.key not in GATED:return None
    closed=kept(adapter)
    if closed is None:
        try:closed=look(adapter,context,inputs)
        except Exception as exc:
            from biol_base.session import Cancelled
            if isinstance(exc,Cancelled):raise
            LOG.info('콘텐츠 열림 확인 실패 · %s',str(exc)[:80]);return None
        if closed is None:return None
        keep(adapter,closed)
    if job.key in closed:
        LOG.info('%s 아직 열리지 않음 · 건너뜀 · 퀘스트 완료·레벨업·%d시간 뒤 다시 확인',job.label,RECHECK_HOURS)
        return True
    return None
