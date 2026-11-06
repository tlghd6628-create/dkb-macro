"""The game's own red dots bring growth forward instead of the clock (issue #24, user 11-06).

pc2 grew two new characters by hand: almost all their power came from the bag. The gear with the green ▲ and the
boxes behind the bag icon's red dot (one 희귀 무기 선택 상자 took 37K to 55.9K). The program had run those only by
its timetable, so they waited for hours.

The top bar is read from the frame alone, with no input: a red dot at the top right of an icon, at y 14 real.
- 가방: open the boxes, equip, and grow. These are the inventory, gear_equip, blessing_equip and gear jobs, brought
  forward on the timetable the same way a death does it.
- 길라잡이, 이벤트, 우편: their reward-cycle rows are made due now.
A dot that is still on after its work (boxes the program does not open, pc2 20:50) waits MUTE seconds before it
brings anything forward again. Only jobs the user switched on are moved; combat content is not touched here.
"""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
DOT_Y=14;DOT_HALF=6;DOT_PIXELS=8
DOTS={'guide':1019,'event':1073,'mail':1237,'bag':1292}   # real x of each icon's dot (pc1 11-06: 1073, 1128, 1292, 1346)
LABELS={'guide':'길라잡이','event':'이벤트','mail':'우편','bag':'가방'}
BAG_JOBS=('inventory','gear_equip','blessing_equip','gear')
REWARD_KEYS={'guide':'auto_rewards.guide.enabled','event':'auto_rewards.event.enabled','mail':'auto_rewards.mail.enabled'}
LOOK_EVERY=60;MUTE=1800
QUEST_GROWTH_SECONDS=900   # a quest's end brings growth forward at most every 15 minutes (user 11-06)


def dots(real):
    """Names whose icon shows a red dot."""
    import numpy as np
    a=np.asarray(real)
    if a.ndim!=3 or a.shape[0]<DOT_Y+DOT_HALF+1:return set()
    found=set()
    for name,x in DOTS.items():
        p=a[DOT_Y-DOT_HALF:DOT_Y+DOT_HALF+1,x-DOT_HALF:x+DOT_HALF+1].astype(int)
        if int(((p[...,0]>200)&(p[...,1]<90)&(p[...,2]<90)).sum())>=DOT_PIXELS:found.add(name)
    return found


def bring_bag(adapter):
    from datetime import datetime
    from owner_timetable import planner,BY_KEY,EQUIP_JOBS,enabled
    plan=planner(adapter);now=datetime.now().isoformat();moved=[]
    for key in BAG_JOBS:
        job=BY_KEY.get(key);item=plan.state.get(key)
        if job is None or item is None or not enabled(job,plan.values):continue
        extra={'equip_recheck':True} if key in EQUIP_JOBS else ({'growth_recheck':True} if key=='gear' else {})
        item.update(status='pending',at=now,attempts=0,signal_at=time.time(),**extra);moved.append(job.label)
    if moved:plan.commit()
    from owner_worn_growth import wake
    wake(adapter)
    return moved


def bring_reward(adapter,name):
    key=REWARD_KEYS[name]
    if adapter.values.get(key) is not True:return []
    from owner_reward_cycle import ledger
    signalled=getattr(adapter,'_owner_reward_signal',None)
    if signalled is None:signalled=adapter._owner_reward_signal={}
    signalled[key]=time.time()
    book=ledger(adapter);row=book.rows.get(key)
    if isinstance(row,dict) and row.get('state')!='running':
        row['at']=0;row.pop('rechecks',None)
        from owner_timetable import save
        save(book.path,book.data)
    return [LABELS[name]]


def look(adapter,frame):
    """Read the dots on this frame and bring their work forward. Returns the labels moved."""
    now=time.monotonic()
    if now-getattr(adapter,'_owner_signal_look',-1e9)<LOOK_EVERY:return []
    adapter._owner_signal_look=now
    real=getattr(frame,'hi',None)
    if real is None:return []
    muted=getattr(adapter,'_owner_signal_muted',None)
    if muted is None:muted=adapter._owner_signal_muted={}
    moved=[]
    for name in sorted(dots(real)):
        if now<muted.get(name,0):continue
        try:done=bring_bag(adapter) if name=='bag' else bring_reward(adapter,name)
        except Exception as exc:
            LOG.info('빨간 점 처리 보류 · %s · %s',LABELS[name],str(exc)[:80]);continue
        muted[name]=now+MUTE
        if done:
            moved+=done
            LOG.info('빨간 점 · %s · %s 앞당김',LABELS[name],' · '.join(done))
    return moved


def quest_end(adapter):
    """A quest just ended: its reward may have brought materials. Growth and equip move up, at most every
    QUEST_GROWTH_SECONDS; a level-up moves them at once."""
    now=time.monotonic();reason=None
    try:
        from owner_progression import state
        level=state(adapter).level
    except Exception:level=None
    last=getattr(adapter,'_owner_signal_level',None)
    if type(level) is int:
        adapter._owner_signal_level=level
        if type(last) is int and level>last:reason='레벨 %d→%d'%(last,level)
    if reason is None and now-getattr(adapter,'_owner_quest_growth_at',-1e9)>=QUEST_GROWTH_SECONDS:reason='퀘스트 완료'
    if reason is None:return []
    adapter._owner_quest_growth_at=now
    try:moved=bring_bag(adapter)
    except Exception as exc:
        LOG.info('퀘스트 완료 성장 앞당김 보류 · %s',str(exc)[:80]);return []
    if moved:LOG.info('%s · %s 앞당김',reason,' · '.join(moved))
    return moved
