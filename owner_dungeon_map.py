"""Read the common dungeon map prefix, independent of map/character name.

Uses retained game pixels and the existing strict foreground matcher. No OCR,
input, mutable observation cache, or per-character map-coordinate learning.
"""
from functools import lru_cache
from pathlib import Path

TITLES=('title-normal.png','title-small.png','title-always.png')
TITLE_SCORE=.92

@lru_cache(maxsize=1)
def label():
    import numpy as np
    from PIL import Image
    image=np.asarray(Image.open(Path(__file__).parent/'assets/dungeon-map/bi-gyeong.png').convert('L'))
    if image.shape!=(10,22) or int((image>0).sum())<20:raise ValueError('비경 지도 표기 이미지 확인 필요')
    return image

@lru_cache(maxsize=1)
def titles():
    import numpy as np
    from PIL import Image
    return tuple(np.asarray(Image.open(Path(__file__).parent/'assets/dungeon-map'/name).convert('L')) for name in TITLES)

def title_inside(frame):
    """The title shrinks to fit a long map name, and 24-hour maps say [상시 비경]."""
    import cv2,numpy as np
    hay=frame[2:26,22:66,1]
    return any(float(np.nan_to_num(cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED)).max())>=TITLE_SCORE for needle in titles())

def map_inside(frame):
    import numpy as np
    if getattr(frame,'shape',None)!=(479,897,3):return False
    if title_inside(frame):return True
    # Text only: [비경], not the particular area or player. The small margin
    # tolerates the native map-title placement, never scans other HUD labels.
    crop=frame[8:22,23:49].astype('int16')
    mask=((crop[:,:,1]>160)&(crop[:,:,1]-crop[:,:,0]>18)&(crop[:,:,1]-crop[:,:,2]>18)).astype('uint8')*255
    from owner_reward_visual_guard import match
    return match(mask,label())

def inside(detector,frame):
    if map_inside(frame):return True
    return bool(detector.find('체크_던전진행중',frame,threshold=.95)
                and detector.find('버튼_던전_나가기',frame,threshold=.95))
