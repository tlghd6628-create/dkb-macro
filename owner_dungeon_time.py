"""Second look when the dungeon timer reads as an impossible time.

Actual crop 23:43: raw 03:59:45 reads as 03:69:45 at .982, and the native reader
stops at its first confident text, so all six tries fail the same way. Its later
preprocessing reads the same crop correctly, so those are tried here, keeping
its confidence rule. The crop is kept as evidence; None still never means zero.
"""
from datetime import datetime
from functools import wraps
from pathlib import Path
import logging,re,time

LOG=logging.getLogger('project_gui.DKB')
OUT_OF_RANGE='시간 유효 범위 이탈'
SCALES=(3,4,6)

def keep(rgb,project_root):
    """Evidence only: a failed save must not change the read."""
    try:
        from PIL import Image
        folder=Path(project_root)/'logs/dungeon-time';folder.mkdir(parents=True,exist_ok=True)
        for old in sorted(folder.glob('*.png'))[:-19]:old.unlink()
        Image.fromarray(rgb).save(folder/(datetime.now().strftime('%Y%m%dT%H%M%S_%f')+'.png'))
    except (OSError,ValueError,TypeError,ImportError):pass

def second_look(rgb,project_root,context,module,deadline):
    import cv2,numpy as np
    from tools.ocr_support import get_paddle_engine
    client=get_paddle_engine(project_root,'number')
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    for scale in SCALES:
        up=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
        for variant in (cv2.cvtColor(up,cv2.COLOR_GRAY2RGB),cv2.cvtColor(((up>140)*255).astype(np.uint8),cv2.COLOR_GRAY2RGB)):
            context.checkpoint()
            for page in module._predict(client,variant,context,deadline):
                texts=page.get('rec_texts',[]);scores=page.get('rec_scores',[])
                if not texts or min(float(s) for s in scores)<.85:continue
                parsed=module.parse_hms(''.join(str(t) for t in texts))
                if parsed is not None:return parsed
    return None

def wrap(original,module):
    @wraps(original)
    def read_time_image(rgb,project_root,context,*,deadline=None):
        result=original(rgb,project_root,context,deadline=deadline)
        if result.ok or result.error!=OUT_OF_RANGE:return result
        keep(rgb,project_root)
        limit=deadline if deadline is not None else time.monotonic()+module.TOTAL_TIMEOUT_SECONDS
        try:parsed=second_look(rgb,project_root,context,module,limit)
        except (module.Cancelled,module.TimeOCRTimeout):raise
        except (ValueError,OSError,RuntimeError,KeyError,TypeError) as exc:
            LOG.warning('비경 시간 재판독 실패 · %s',exc);return result
        if parsed is None:return result
        LOG.info('비경 시간 재판독 · %s',parsed[0])
        return module.TimeRead(True,*parsed)
    read_time_image._owner_dungeon_time=True
    return read_time_image

def install():
    import tools.time_ocr as module
    if not getattr(module.read_time_image,'_owner_dungeon_time',False):
        module.read_time_image=wrap(module.read_time_image,module)
