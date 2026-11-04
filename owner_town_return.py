"""Do not mistake town AUTO for hunting; restore hunts after town services."""
from functools import wraps,lru_cache
from pathlib import Path
import logging,threading
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
BOX=(24,9,47,14)


class MissingFavorite(BaseException):pass


@lru_cache(maxsize=1)
def town_label():
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(Path(__file__).parent/'assets/town-tabaro-label.png').convert('RGB'))


def green(image):
    image=image.astype('float32')
    return (image[:,:,1]>105)&(image[:,:,1]>image[:,:,0]*1.12)&(image[:,:,1]>image[:,:,2]*1.08)


def is_town(frame):
    import numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return False
    x,y,w,h=BOX;current=green(frame[y:y+h,x:x+w]);expected=green(town_label())
    return bool(expected.sum()>=50 and (2*(expected&current).sum())/max(1,expected.sum()+current.sum())>=.96)


def town_pair(adapter,context,inputs):
    from project_adapter.town_services import TownServices
    service=TownServices(adapter,context,inputs,[])
    first=is_town(service.capture());context.wait(.15);context.checkpoint()
    return first and is_town(service.capture())


def require_hunting_location(adapter,context,inputs):
    """Called only after the native hunt's positive receipt; restore sleep."""
    context.checkpoint();adapter.exit_sleep_mode(context,inputs)
    if town_pair(adapter,context,inputs):
        raise RuntimeError('사냥터 이동 후에도 타바로성입니다. 마을 AUTO를 사냥 성공으로 처리하지 않습니다. 즐겨찾기 사냥터를 확인해 주세요.')
    # This negative guard rejects the observed town only. It does not assert
    # every other screen is a valid hunt map; native AUTO/location guards stay.
    context.checkpoint();adapter.enter_sleep_mode(context,inputs)


def wrap_slots(ordinary):
    @wraps(ordinary)
    def slots(*args,**kwargs):
        result=ordinary(*args,**kwargs)
        if not result:raise MissingFavorite()
        LOG.info('사냥터 등록 확인 · 사용 가능한 저장 슬롯=%s · 임의 이동 사용 안 함',result)
        return result
    slots._owner_no_random=True
    return slots


def wrap_wait(ordinary):
    @wraps(ordinary)
    def wait(adapter,context,inputs):
        previous=getattr(LOCAL,'periodic',None);LOCAL.periodic=(adapter,context)
        try:return ordinary(adapter,context,inputs)
        finally:LOCAL.periodic=previous
    return wait


def wrap_training(ordinary):
    @wraps(ordinary)
    def training(adapter,context,inputs):
        result=ordinary(adapter,context,inputs)
        from owner_progression import state
        if result is not True or getattr(LOCAL,'periodic',None)!=(adapter,context):return result
        if adapter.mode!='auto_mode' or state(adapter).work_mode!='auto_mode' or getattr(adapter,'_owner_temporary_work',None):return result
        context.checkpoint();adapter.exit_sleep_mode(context,inputs)
        if town_pair(adapter,context,inputs):
            LOG.warning('주기 수련 후 타바로성 확인 · 마을 AUTO 대신 기존 사냥터로 복귀')
            context.checkpoint()
            if adapter.run_favorite_hunt(context,inputs) is not True:
                raise RuntimeError('주기 수련 후 사냥터 복귀를 확인하지 못했습니다.')
            LOG.info('주기 수련 후 사냥터 복귀 완료 · 마을 AUTO 방지 확인')
        else:adapter.enter_sleep_mode(context,inputs)
        return result
    return training


def install(gui):
    if getattr(gui,'_owner_town_return',False):return
    from project_adapter._entry import Adapter
    from project_adapter import favorite_hunt
    if not getattr(favorite_hunt.available_slots,'_owner_no_random',False):
        favorite_hunt.available_slots=wrap_slots(favorite_hunt.available_slots)
        Adapter._wait_for_spirit_training=wrap_wait(Adapter._wait_for_spirit_training)
        Adapter.run_spirit_training=wrap_training(Adapter.run_spirit_training)
    gui._owner_town_return=True
    LOG.info('마을 사냥 오판 방지 준비 · 즐겨찾기 미등록 임의 이동 차단 · 주기 수련 후 마을이면 사냥터 복귀')
