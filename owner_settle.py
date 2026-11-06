"""Wait for the screen to settle instead of a fixed time (user 11-07: click on like a person).

After an input the old code slept a fixed 1-1.5 s whatever the game did. Here the wait ends once two looks in a row
are the same, but never before MIN_SECONDS (the click must have landed) and never after the old fixed time.
"""
import time
MIN_SECONDS=.3;STEP=.12;STILL=2.5


def _look(frame):
    import numpy as np
    a=np.asarray(getattr(frame,'hi',None) if getattr(frame,'hi',None) is not None else frame)
    if a.ndim!=3:return None
    return a[::16,::16].astype(np.int16)


def settle(service,context,seconds):
    """Up to seconds; returns early once the screen holds still."""
    start=time.monotonic();last=None
    if not callable(getattr(service,'capture',None)):
        context.wait(seconds);return seconds
    context.wait(MIN_SECONDS)
    while True:
        try:now=_look(service.capture())
        except Exception:now=None
        if now is not None and last is not None and now.shape==last.shape:
            import numpy as np
            if float(np.abs(now-last).mean())<STILL:return time.monotonic()-start
        last=now
        if time.monotonic()-start>=seconds:return time.monotonic()-start
        context.wait(STEP)
