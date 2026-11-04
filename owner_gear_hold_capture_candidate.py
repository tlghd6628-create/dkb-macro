"""Bounded, asynchronous evidence of gear holds, never an input authority."""
from collections import deque
from datetime import datetime
from pathlib import Path
import json,os,queue,threading,time,uuid
from PIL import Image
import numpy as np

_queue=queue.Queue(maxsize=2)
_recent={}
_lock=threading.Lock()
_started=False
MAX_BYTES=512*1024*1024

def _space_available(folder):
    used=0
    if folder.exists():
        for directory,_,names in os.walk(folder):
            for name in names:
                try:used+=(Path(directory)/name).stat().st_size
                except OSError:continue
                if used+2*897*479*3>=MAX_BYTES:return False
    return True

def _write(root,phase,reason,frames):
    folder=Path(root)/'logs'/'gear-holds'
    if not _space_available(folder):return False
    folder.mkdir(parents=True,exist_ok=True)
    out=folder/(datetime.now().strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);out.mkdir()
    for index,frame in enumerate(frames):Image.fromarray(frame).save(out/(str(index+1)+'.png'),compress_level=3)
    (out/'hold.json').write_text(json.dumps({'phase':phase,'reason':reason,'frame_count':len(frames)},ensure_ascii=False),encoding='utf8')
    return True

def _worker():
    while True:
        item=_queue.get()
        try:_write(*item)
        except (OSError,ValueError,TypeError):pass
        finally:_queue.task_done()

def enqueue(root,phase,reason,frames,*,clock=time.monotonic):
    """Queue at most two saved RGB frames; identical holds once per 5 min."""
    global _started
    if not isinstance(phase,str) or not isinstance(reason,str):return False
    phase=phase[:48];reason=reason[:100]
    if not isinstance(frames,(list,tuple,deque)):return False
    frames=tuple(f for f in frames if isinstance(f,np.ndarray) and f.shape==(479,897,3) and f.dtype==np.uint8)[-2:]
    if not frames:return False
    key=(str(root),phase,reason);now=clock()
    with _lock:
        if key in _recent and 0<=now-_recent[key]<300:return False
        if _queue.full():return False
        if not _started:
            threading.Thread(target=_worker,name='gear-hold-evidence',daemon=True).start();_started=True
        try:_queue.put_nowait((root,phase,reason,frames))
        except queue.Full:return False
        _recent[key]=now
        if len(_recent)>256:
            for k in list(_recent):
                if now-_recent[k]>=300:del _recent[k]
            while len(_recent)>256:del _recent[next(iter(_recent))]
    return True
