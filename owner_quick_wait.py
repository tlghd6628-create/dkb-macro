"""Waits after a click end when the screen is ready, in every function (user 11-07: cut the time to a tenth).

Measured on the night's runs: waiting was 63-85% of each reward function's time (이벤트 76.6 s, 63%; 화첩 17 s, 85%);
finding buttons and capturing were under 10%. Most of it is a fixed second after a click while the next screen was
already there. Every native wait goes through Context.wait and every click through InputTransactions.click, so both
are watched here; neither changes what is pressed.

After a click, a wait of FLOOR seconds or more ends once the screen differs from before the click and has held still
for two looks in a row (STEP apart). A screen that never changes keeps the whole wait, as before. Shorter waits (the
native polls) are left alone. settings/owner-quick-wait.json {"enabled": false} turns it off.
"""
import json,logging,threading,time
from pathlib import Path
LOG=logging.getLogger('project_gui.DKB')
FLOOR=.4;FIRST=.2;STEP=.08;WINDOW=3.;CHANGED=1.5;STILL=.8;REPORT=300
LOCAL=threading.local()
STATS=dict(cut=0,saved=0.,waited=0,said=time.monotonic())


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
            from runtime_capture import capture
            a=capture(hwnd,self.target)
            return a[::8,::8].astype('int16').mean(axis=2)
        except Exception:return None


def enabled(root):
    try:return json.loads((Path(root)/'settings/owner-quick-wait.json').read_text(encoding='utf-8')).get('enabled',True) is not False
    except (OSError,ValueError):return True


def quick(ordinary,look,clock=time.monotonic):
    def wait(self,seconds,*args,**kwargs):
        before=getattr(LOCAL,'before',None);at=getattr(LOCAL,'click_at',None)
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
    LOG.info('빠른 대기 · %d회 단축 · %.0f초 절약 · 그대로 기다림 %d회',STATS['cut'],STATS['saved'],STATS['waited'])


def watch_click(ordinary,look,clock=time.monotonic):
    def click(self,*args,**kwargs):
        before=look()
        try:return ordinary(self,*args,**kwargs)
        finally:LOCAL.before=before;LOCAL.click_at=clock()
    click._owner_quick=True
    return click


def install(gui):
    if getattr(gui,'_owner_quick_wait',False):return
    from biol_base.session import Context
    from input_safety import InputTransactions
    if not enabled(gui.project.root):
        LOG.info('빠른 대기 꺼짐 · settings/owner-quick-wait.json');return
    look=Look(gui)
    if not getattr(Context.wait,'_owner_quick',False):Context.wait=quick(Context.wait,look)
    if not getattr(InputTransactions.click,'_owner_quick',False):InputTransactions.click=watch_click(InputTransactions.click,look)
    gui._owner_quick_wait=True
    LOG.info('빠른 대기 연결 · 클릭 뒤 화면이 바뀌고 멈추면 바로 다음 동작')
