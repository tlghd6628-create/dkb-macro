"""Already at the saved hunting spot: no teleport (500 gold each, pc1 11-06 15:33 and 15:34 twice in a minute).

On the world map the saved location's own panel says how far it is ('0m' while standing on it, pc1 14:52). Within
NEAR metres the move is skipped and only AUTO is made sure of. Anything unread keeps the ordinary move.
"""
import logging,re
import owner_hd as hd
import owner_text as text

LOG=logging.getLogger('project_gui.DKB')
NEAR=15
MAP_TITLE=(90,14,100,34)        # real: 세계지도
PIN=(35,284)                    # real: the saved-location list
ROW_Y0,ROW_STEP,ROW_X=125,52,180  # real: saved rows 1, 2, ...
DISTANCE=(1012,672,110,26)      # real: the walk distance, 84m
CLOSE=(1332,31)


AUTO_BOX=(1188,700,44,42)          # real: the AUTO button, orange while on


def auto_lit(frame):
    """AUTO's orange ring: 2.4-2.7% of the button on six shots with it on, 0 on four with it off (pc1 11-06).
    The native AUTO picture missed it for 30 s in a fight at the spot and a teleport was paid for nothing (20:27)."""
    import numpy as np
    hi=getattr(frame,'hi',None)
    if getattr(hi,'shape',None) is None or len(hi.shape)!=3:return False
    x,y,w,h=AUTO_BOX;p=np.asarray(hi)[y:y+h,x:x+w].astype(int);r,g,b=p[...,0],p[...,1],p[...,2]
    return float(((r>200)&(g>120)&(g<210)&(b<90)).mean())>=.01


def words(frame,box):return [text.clean(r['text']) for r in text.read(None,frame,box,scale=2,minimum=.6)]


def map_open(frame):return any('세계지도' in w for w in words(frame,MAP_TITLE))


def slot_number(adapter):
    m=re.match(r'(\d+)',str(adapter.values.get('common.potion_and_favorite.slot','')))
    return int(m.group(1)) if m and adapter.values.get('common.potion_and_favorite.source')=='저장위치' else None


def distance(service,context,slot):
    """Metres to saved location slot, read on the map, or None. The map is closed again either way."""
    service.check();service.key(0x4D);context.wait(1.5)
    if not map_open(service.capture()):return None
    try:
        service.click_hit(hd.real_hit(*PIN));context.wait(1.)
        service.click_hit(hd.real_hit(ROW_X,ROW_Y0+ROW_STEP*(slot-1)));context.wait(1.)
        found=[int(m.group(1)) for w in words(service.capture(),DISTANCE) for m in [re.fullmatch(r'(\d{1,4})m',w.replace('O','0').replace('o','0'))] if m]   # 0m read as Om
        return found[0] if len(found)==1 else None
    finally:
        for _ in range(3):
            if not map_open(service.capture()):break
            service.click_hit(hd.real_hit(*CLOSE));context.wait(1.)


def already_there(adapter,context,inputs):
    """True when standing at the saved slot and AUTO is on; the caller then skips the move."""
    slot=slot_number(adapter)
    if slot is None:return False
    from project_adapter.town_services import TownServices
    from project_adapter import favorite_hunt
    service=TownServices(adapter,context,inputs,[])
    if getattr(service.capture(),'hi',None) is None:return False
    from owner_town_return import town_pair
    if town_pair(adapter,context,inputs):return False
    try:metres=distance(service,context,slot)
    except Exception as exc:
        LOG.info('저장위치 거리 확인 보류 · %s',type(exc).__name__);return False
    if metres is None or metres>NEAR:
        if metres is not None:LOG.info('저장위치 %d번까지 %dm · 축지술 이동',slot,metres)
        return False
    lit=auto_lit(service.capture())
    if lit:context.wait(.5);lit=auto_lit(service.capture())
    if not lit and favorite_hunt.ensure_auto_active(service.actions,context,LOG,post_click_wait=1,poll_seconds=.5) is False:return False
    LOG.info('저장위치 %d번에 이미 있음 · %dm · 축지술 없이 사냥 계속',slot,metres)
    return True
