"""Optional, reversible MissionUI measurements; never changes game inputs.

Installs wrappers only when explicitly requested by the caller. The collector
is supplied by the caller and can fail without changing the wrapped return or
exception. Timings are inclusive: e.g. selected can contain rows and capture.
"""
from functools import wraps

METHODS={'frame':'capture','rows':'ocr_workflow','open':'mission_open',
         'wheel':'mission_scroll','selected':'mission_select'}

def _start(collector):
    try:return collector.mark()
    except BaseException:return None

def _outcome(error, result, name):
    if error is not None:
        if isinstance(error, TimeoutError):return 'timeout'
        if type(error).__name__ == 'MissionRowUnreadable':return 'unreadable'
        if type(error).__name__ == 'Pending':return 'blocked'
        if type(error).__name__ in ('Cancelled','CancelledError'):return 'cancelled'
        return 'error'
    if result is None and name in ('frame','rows','selected'):
        return 'unreadable' if name in ('frame','rows') else 'no_match'
    if name in ('rows','markers') and isinstance(result,(list,tuple)) and not result:
        return 'no_match'
    return 'ok'

def _wrap(original, collector, stage, name, frame_timestamp):
    @wraps(original)
    def observed(*args, **kwargs):
        start=_start(collector); error=None; result=None
        try:
            result=original(*args, **kwargs)
            return result
        except BaseException as exc:
            error=exc
            raise
        finally:
            if start is not None:
                try:
                    # No implicit capture time inference: accept a caller's
                    # validated monotonic timestamp only when explicitly given.
                    frame_at=frame_timestamp(name,args,kwargs) if frame_timestamp is not None else None
                    collector.record(stage,_outcome(error,result,name),start,frame_at=frame_at)
                except BaseException:
                    pass
    observed._owner_mission_perf_wrapper=True
    return observed

class Handle:
    def __init__(self,collector,restores):
        self.collector=collector;self.restores=restores;self.closed=False
    def close(self):
        if self.closed:return
        self.closed=True
        for target,name,original,wrapper,owned in reversed(self.restores):
            if getattr(target,name,None) is not wrapper:continue
            if owned:setattr(target,name,original)
            else:delattr(target,name)
        try:self.collector.close(timeout=0)
        except BaseException:pass

def install(module,collector,*,frame_timestamp=None):
    """Wrap available methods; return a handle that restores originals on close.

    Do not install a second time over an active wrapper. Existing subclasses
    that override methods or pre-imported function aliases are not instrumented.
    """
    cls=module.MissionUI
    targets=[(cls,name,stage) for name,stage in METHODS.items() if callable(getattr(cls,name,None))]
    if callable(getattr(module,'markers',None)):targets.append((module,'markers','template_match'))
    if any(getattr(getattr(target,name),'_owner_mission_perf_wrapper',False) for target,name,_ in targets):
        raise ValueError('이미 임무 성능 계측이 연결되어 있습니다.')
    restores=[]
    try:
        for target,name,stage in targets:
            original=getattr(target,name);owned=name in vars(target)
            wrapper=_wrap(original,collector,stage,name,frame_timestamp)
            setattr(target,name,wrapper);restores.append((target,name,original,wrapper,owned))
    except BaseException:
        Handle(collector,restores).close()
        raise
    return Handle(collector,restores)
