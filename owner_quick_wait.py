"""Waits after a click end when the screen is ready, in every function (user 11-07: cut the time to a tenth).

Measured on the night's runs: waiting was 63-85% of each reward function's time (이벤트 76.6 s, 63%; 화첩 17 s, 85%);
finding buttons and capturing were under 10%. Most of it is a fixed second after a click while the next screen was
already there. Every native wait goes through Context.wait and every press through InputTransactions down/up, so
both are watched here; neither changes what is pressed.

After a click, a wait of FLOOR seconds or more ends once the screen differs from before the click and has held still
for two looks in a row (STEP apart). A screen that never changes keeps the whole wait, as before. Shorter waits (the
native polls) are left alone. settings/owner-quick-wait.json {"enabled": false} turns it off.
"""
import json,logging,threading,time
from pathlib import Path
LOG=logging.getLogger('project_gui.DKB')
FLOOR=.4;FIRST=.2;STEP=.08;WINDOW=3.;CHANGED=1.5;STILL=.8;REPORT=120
# One shared note, not per thread: presses run on the input worker's thread and waits on the session's (09:53: 102
# presses seen, not one wait matched). Only one run drives the game at a time.
class _Shared:pass
LOCAL=_Shared()
STATS=dict(cut=0,saved=0.,waited=0,said=time.monotonic(),presses=0,blind=0,long=0,released=0,ages=[])


def diff(a,b):
    import numpy as np
    return float(np.abs(a-b).mean()) if a is not None and b is not None and a.shape==b.shape else 255.


def settled(before,frames):
    """True when the last frame differs from the pre-click one and the last two looks match it."""
    if len(frames)<3 or before is None:return False
    a,b,c=frames[-3:]
    return diff(c,before)>CHANGED and diff(c,b)<STILL and diff(b,a)<STILL


class Look:
    """A small grey copy of the game client, or None."""
    def __init__(self,gui):self.gui=gui;self.target=None
    def __call__(self):
        try:
            hwnd=getattr(self.gui.game_window,'hwnd',0)
            if not hwnd:return None
            if self.target is None:
                from project_adapter import protected_assets
                profile=self.gui.project.root/'profiles'/self.gui.project.code
                self.target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
            # The profile's game target says 897x479; at 1366x768 that size check refused every look (09:14: no quick
            # wait ever). The program's own screen viewer passes the window's real size the same way.
            import win32gui
            left,top,width,height=win32gui.GetClientRect(hwnd)
            from runtime_capture import capture
            a=capture(hwnd,dict(self.target,client_size=[width,height]))
            return a[::8,::8].astype('int16').mean(axis=2)
        except Exception as exc:
            if not getattr(self,'told',False):
                self.told=True;LOG.info('빠른 대기 화면 보기 실패 · %s · %s',type(exc).__name__,str(exc)[:100])
            return None


def enabled(root):
    try:return json.loads((Path(root)/'settings/owner-quick-wait.json').read_text(encoding='utf-8')).get('enabled',True) is not False
    except (OSError,ValueError):return True


def quick(ordinary,look,clock=time.monotonic):
    def wait(self,seconds,*args,**kwargs):
        before=getattr(LOCAL,'before',None);at=getattr(LOCAL,'click_at',None)
        if seconds>=FLOOR:
            STATS['long']+=1
            if at is not None:STATS['ages'].append((round(clock()-at,1),round(seconds,2),before is not None))
            STATS['ages']=STATS['ages'][-12:];report(clock)
        if seconds<FLOOR or before is None or at is None or clock()-at>WINDOW or getattr(LOCAL,'off',False):
            return ordinary(self,seconds,*args,**kwargs)
        LOCAL.before=None   # one quick wait per click
        start=clock();end=start+seconds;frames=[]
        ordinary(self,min(FIRST,seconds))
        while True:
            left=end-clock()
            if left<=STEP:
                if left>0:ordinary(self,left)
                break
            now=look()
            if now is None:
                ordinary(self,left);break
            frames.append(now)
            if settled(before,frames):
                STATS['cut']+=1;STATS['saved']+=max(0.,left);report(clock);return
            ordinary(self,STEP)
        STATS['waited']+=1;report(clock)
    wait._owner_quick=True
    return wait


def report(clock=time.monotonic):
    if clock()-STATS['said']<REPORT:return
    STATS['said']=clock()
    LOG.info('빠른 대기 · %d회 단축 · %.0f초 절약 · 그대로 기다림 %d회 · 누름 %d(화면 못 봄 %d) · 긴 대기 %d',
             STATS['cut'],STATS['saved'],STATS['waited'],STATS['presses'],STATS['blind'],STATS['long'])
    LOG.info('빠른 대기 진단 · 손 뗌 %d · 긴 대기(클릭 뒤 초, 대기 초, 기록) %s',STATS['released'],STATS['ages'])


def watch_press(down,up,look,clock=time.monotonic):
    """Native code presses through transaction() with down/up, not click() (09:06: no quick wait at all on click()).
    The look is taken at the press and counts from the release."""
    def pressed(self,kind,value):
        # The release was never seen (10:02, 10:06: 0 of 21), so the press itself starts the count.
        seen=look();STATS['presses']+=1
        if seen is None:STATS['blind']+=1
        else:LOCAL.before=seen;LOCAL.click_at=clock()
        LOCAL.pressing=seen
        return down(self,kind,value)
    def released(self,kind,value):
        try:return up(self,kind,value)
        finally:
            before=getattr(LOCAL,'pressing',None);LOCAL.pressing=None;STATS['released']+=1
            if before is not None:LOCAL.before=before;LOCAL.click_at=clock()
    pressed._owner_quick=released._owner_quick=True
    return pressed,released


def watch_transaction(ordinary,clock=time.monotonic):
    """Most presses are let go by the transaction's own cleanup, not up() (10:02: 22 presses, 0 releases seen). The
    note is finished when the transaction ends."""
    from contextlib import contextmanager
    @contextmanager
    def transaction(self,*args,**kwargs):
        try:
            with ordinary(self,*args,**kwargs) as inner:yield inner
        finally:
            before=getattr(LOCAL,'pressing',None)
            if before is not None:
                LOCAL.pressing=None;STATS['released']+=1;LOCAL.before=before;LOCAL.click_at=clock()
    transaction._owner_quick=True
    return transaction


def install(gui):
    if getattr(gui,'_owner_quick_wait',False):return
    from biol_base.session import Context
    from input_safety import InputTransactions
    if not enabled(gui.project.root):
        LOG.info('빠른 대기 꺼짐 · settings/owner-quick-wait.json');return
    look=Look(gui)
    if not getattr(Context.wait,'_owner_quick',False):Context.wait=quick(Context.wait,look)
    if not getattr(InputTransactions.down,'_owner_quick',False):
        InputTransactions.down,InputTransactions.up=watch_press(InputTransactions.down,InputTransactions.up,look)
    if not getattr(InputTransactions.transaction,'_owner_quick',False):
        InputTransactions.transaction=watch_transaction(InputTransactions.transaction)
    gui._owner_quick_wait=True
    LOG.info('빠른 대기 연결 · 클릭 뒤 화면이 바뀌고 멈추면 바로 다음 동작')
