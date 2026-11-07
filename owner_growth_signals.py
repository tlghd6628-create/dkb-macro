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
from owner_job_timing import SPEC_JOBS as BAG_JOBS
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


MENU_DOT_X=1346   # real x of the full menu (≡) icon's dot
MENU_OPEN=(1333,32);MENU_CLOSE=(1330,32);MENU_AREA=(945,100,421,545)
# A dot sits at a tile's top right, its label 25-80 px below and up to 75 px left (pc1 11-07 menu frame: 9 of 9).
TILE_JOBS={'성장':('gear',),'도술':('gear',),'가호':('blessing','blessing_equip'),'단봉인해제':('seal_release',),
           '기운발현':('growth',),'화첩':('album',),'업적':('achievement',),'임무':('daily_missions',),'도사수행록':('training_log',)}


MENU_LABELS=('내정보','성장','도술','가호','단봉인해제','영기수련','내면의길','기운발현','의복','탈것','신수','칭호','문파','친구',
             '구인구직','세계지도','아이템사전','제작','화첩','유물수집','요귀도감','보물찾기','업적','임무','도사수행록','비경탐험',
             '보스토벌','승천의탑','플래너','문파전투','낙화의전장','차원쟁탈전','도깨비수련장','순위','만귀비경')


def known_label(word):
    """The menu's own name nearest to an OCR word ('도글' read for 도술 on one pass), or None when unsure."""
    from difflib import SequenceMatcher
    if word in MENU_LABELS:return word
    scored=sorted(((SequenceMatcher(None,word,label).ratio(),label) for label in MENU_LABELS),reverse=True)
    if scored[0][0]>=.5 and (len(scored)<2 or scored[0][0]>scored[1][0]):return scored[0][1]
    return None


def menu_dot(real):
    import numpy as np
    a=np.asarray(real)
    if a.ndim!=3:return False
    p=a[DOT_Y-DOT_HALF:DOT_Y+DOT_HALF+1,MENU_DOT_X-DOT_HALF:MENU_DOT_X+DOT_HALF+1].astype(int)
    return int(((p[...,0]>200)&(p[...,1]<90)&(p[...,2]<90)).sum())>=DOT_PIXELS


def dotted_tiles(real,rows):
    """Cleaned labels of the menu tiles that carry a red dot."""
    import numpy as np,cv2
    from owner_text import clean
    a=np.asarray(real).astype(int);r,g,b=a[...,0],a[...,1],a[...,2]
    mask=((r>200)&(g<90)&(b<90)).astype(np.uint8)
    n,_,st,cen=cv2.connectedComponentsWithStats(mask,8);found=set()
    for i in range(1,n):
        x,y=cen[i];w,h,area=st[i][2],st[i][3],st[i][4]
        if not(6<=area<=80 and w<=12 and h<=12 and x>MENU_AREA[0] and y>MENU_AREA[1]):continue
        near=[row for row in rows if -75<=row['rx']-x<=10 and 25<=row['ry']-y<=80]
        if near:
            label=known_label(clean(min(near,key=lambda row:abs(row['ry']-y-49))['text']))
            if label:found.add(label)
    return found


def bring_jobs(adapter,keys):
    """Timetable jobs brought to now, as the bag's dot does; only those the user switched on."""
    from owner_timetable import planner,BY_KEY,EQUIP_JOBS,enabled
    from owner_timetable import now as kst_now
    plan=planner(adapter);now=kst_now().isoformat();moved=[]
    for key in dict.fromkeys(keys):
        job=BY_KEY.get(key);item=plan.state.get(key)
        if job is None or item is None or not enabled(job,plan.values):continue
        extra={'equip_recheck':True} if key in EQUIP_JOBS else ({'growth_recheck':True} if key=='gear' else {})
        item.update(status='pending',at=now,attempts=0,signal_at=time.time(),**extra);moved.append(job.label)
    if moved:plan.commit()
    return moved


def menu_dots(adapter,context,inputs,real):
    """The ≡ icon's dot: open the full menu once, bring forward what its dotted tiles name, and close it (user 11-07:
    every red dot at once)."""
    now=time.monotonic();muted=getattr(adapter,'_owner_signal_muted',None)
    if muted is None:muted=adapter._owner_signal_muted={}
    if now<muted.get('menu',0) or not menu_dot(real):return []
    muted['menu']=now+MUTE
    import numpy as np,owner_hd as hd
    from owner_mission_ui import MissionUI
    from owner_text import read_area
    from owner_settle import settle
    service=MissionUI(adapter,context,inputs).service
    service.click_hit(hd.real_hit(*MENU_OPEN));settle(service,context,1.5)
    frame=getattr(service.capture(),'hi',None)
    if frame is None:return []
    a=np.asarray(frame);x,y,w,h=MENU_AREA
    rows=read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5)
    tiles=dotted_tiles(a,rows)
    if any(row for row in rows):service.click_hit(hd.real_hit(*MENU_CLOSE));settle(service,context,1.)
    keys=[key for tile in tiles for key in TILE_JOBS.get(tile,())]
    moved=bring_jobs(adapter,keys) if keys else []
    LOG.info('빨간 점 · 전체메뉴 · 점 있는 칸 %s · %s',' · '.join(sorted(tiles)) or '없음',(' · '.join(moved)+' 앞당김') if moved else '앞당길 작업 없음')
    return moved


def bring_bag(adapter):
    from datetime import datetime
    from owner_timetable import planner,BY_KEY,EQUIP_JOBS,enabled
    from owner_timetable import now as kst_now
    plan=planner(adapter);now=kst_now().isoformat();moved=[]
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
    # Closed content (비경, 승천의 탑, 레이드) opens with story quests: the kept menu read is dropped, and the next
    # time one of them comes due the full menu is read again (user 11-07).
    try:
        from owner_content_lock import forget
        forget(adapter)
    except Exception:pass
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
