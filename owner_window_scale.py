"""Run the game window larger so its small text can be read, without moving any picture or coordinate.

Measured on the same shop screen (11-05): at 897x479 the reader gave 영음 장비, 결명 도슬, 도사 주감협깔 3/60; at
1.5 times 절명 도술 and 도사 주간 한정:(3/50), and the existing pictures still matched the frame scaled back down.

Everything keeps working in 897x479 terms. A capture is taken at the real size and scaled down, and the
real image rides along on the frame for the reader (owner_progression.resized). Clicks are scaled up at the
single point where client coordinates become screen coordinates. A smaller screen simply stays at 1x.
"""
import ctypes,logging,os
import numpy as np

LOG=logging.getLogger('project_gui.DKB')
LOGICAL=(897,479)
SCALE=1.5
PROGRAM_WIDTH=493   # the program window sits beside the game
FRAME_EXTRA=(16,39)
_game={};_state={}


class HiFrame(np.ndarray):
    """A normal 897x479 frame that also carries the real capture."""
    hi=None
    def __array_finalize__(self,obj):
        self.hi=getattr(obj,'hi',None)


def with_real(frame,real):
    made=frame.view(HiFrame);made.hi=real
    return made


def wanted_scale(screen=None):
    """1.5 where the larger game and the program fit side by side, otherwise the old size."""
    forced=os.environ.get('DKB_WINDOW_SCALE')
    if forced:
        try:return float(forced)
        except ValueError:pass
    if screen is None:
        user=ctypes.windll.user32;screen=(user.GetSystemMetrics(16),user.GetSystemMetrics(17))
    w,h=screen
    fits=w>=round(LOGICAL[0]*SCALE)+FRAME_EXTRA[0]+PROGRAM_WIDTH and h>=round(LOGICAL[1]*SCALE)+FRAME_EXTRA[1]
    return SCALE if fits else 1.0


def physical_size(hwnd):
    import win32gui
    _,_,w,h=win32gui.GetClientRect(hwnd)
    return w,h


def is_game(hwnd):
    import win32gui
    if hwnd not in _game:
        try:_game[hwnd]=win32gui.GetClassName(hwnd)=='UnityWndClass'
        except Exception:return False
    return _game[hwnd]


def factor_of(size):
    """How much larger than 897x479 this client is. 1 unless it keeps the same shape."""
    w,h=size
    if w<=0 or h<=0:return 1.0
    x,y=w/LOGICAL[0],h/LOGICAL[1]
    return x if abs(x-y)/x<.01 else 1.0


def logical_of(size):
    return LOGICAL if factor_of(size)!=1.0 else tuple(size)


def scaled_point(point,factor):
    x,y=point
    return (x,y) if factor==1.0 or (x==0 and y==0) else (round(x*factor),round(y*factor))


def scale_down(real):
    import cv2
    down=cv2.resize(real,LOGICAL,interpolation=cv2.INTER_AREA)
    return with_real(down,real)


def real_crop(frame,box):
    """The box from the real capture at 4x, the size the reader has always been given, or None."""
    real=getattr(frame,'hi',None)
    if real is None or frame.shape[:2]!=(LOGICAL[1],LOGICAL[0]):return None
    import cv2
    f=real.shape[1]/LOGICAL[0];x,y,w,h=box
    if f<=1:return None
    crop=real[round(y*f):round((y+h)*f),round(x*f):round((x+w)*f)]
    if crop.size==0:return None
    return cv2.resize(crop,(w*4,h*4),interpolation=cv2.INTER_CUBIC)


def _ensure_size(hwnd,logical,context,physical):
    """Set the real client size for this logical one, correcting from measurement as the original does."""
    import time
    import win32gui
    want=tuple(round(v*wanted_scale()) for v in logical) if tuple(logical)==LOGICAL else tuple(logical)
    for attempt in range(3):
        if context:context.checkpoint()
        L,T,R,B=win32gui.GetWindowRect(hwnd);cw,ch=physical(hwnd)
        if (cw,ch)==want:return tuple(logical)
        # no z-order change, no move, no activate
        win32gui.SetWindowPos(hwnd,0,0,0,want[0]+(R-L-cw),want[1]+(B-T-ch),0x16)
        for _ in range(8):
            if context:context.wait(.04)
            else:time.sleep(.04)
            if physical(hwnd)==want:
                LOG.info('게임 창 크기 %dx%d · 글자 판독용',want[0],want[1]);return tuple(logical)
    raise RuntimeError('창 크기 조절 실패: %s (기준 %s)'%(physical(hwnd),want))


def install():
    """Safe to call again. Also used by the tools, which then follow whatever size the window has."""
    import win32gui,window_resolution,mdt_owned_capture
    if getattr(window_resolution,'_owner_window_scale',False):return
    window_resolution._owner_window_scale=True
    physical=window_resolution.client_size
    _state['physical']=physical
    ordinary_ensure=window_resolution.ensure_client_size
    def client_size(hwnd):
        size=physical(hwnd)
        return logical_of(size) if is_game(hwnd) else size
    def ensure_client_size(hwnd,expected,context=None):
        if not is_game(hwnd):return ordinary_ensure(hwnd,expected,context)
        return _ensure_size(hwnd,expected,context,physical)
    window_resolution.client_size=client_size
    window_resolution.ensure_client_size=ensure_client_size
    ordinary_capture=mdt_owned_capture.capture_client
    def capture_client(hwnd,target,printwindow=None):
        real=physical_size(hwnd)
        if factor_of(real)==1.0:return ordinary_capture(hwnd,target,printwindow=printwindow)
        return scale_down(ordinary_capture(hwnd,dict(target,client_size=list(real)),printwindow=printwindow))
    mdt_owned_capture.capture_client=capture_client
    ordinary_point=win32gui.ClientToScreen
    def client_to_screen(hwnd,point):
        if is_game(hwnd):
            point=scaled_point(tuple(point),factor_of(physical_size(hwnd)))
        return ordinary_point(hwnd,point)
    win32gui.ClientToScreen=client_to_screen


def keep_size(gui):
    """While nothing is running: the game at the larger size, the program window beside it.

    The connect step sees 897x479 as already right, so nothing else would ever enlarge it. A running job is
    never disturbed; the next idle check catches a game restarted at its old size.
    """
    try:
        state=gui.session.snapshot()
        if state.get('status') not in ('running','paused') and not state.get('worker_alive'):
            hwnd=getattr(getattr(gui,'game_window',None),'hwnd',0)
            if hwnd and is_game(hwnd) and 'physical' in _state:
                _ensure_size(hwnd,LOGICAL,None,_state['physical'])
                place_program(gui)
    except Exception as exc:
        LOG.debug('게임 창 크기 확인 생략 · %s',exc)
    if hasattr(gui,'root'):gui.root.after(15000,lambda:keep_size(gui))


def place_program(gui):
    """Keep the program window beside the larger game instead of under it."""
    import win32gui
    try:
        hwnd=getattr(getattr(gui,'game_window',None),'hwnd',0)
        if not hwnd or not win32gui.IsWindow(hwnd):return False
        right=win32gui.GetWindowRect(hwnd)[2]
        root=gui.root
        if root.winfo_rootx()<right:
            top=root.winfo_rooty()
            root.geometry('+%d+%d'%(right+2,max(0,top-31)))
            return True
    except Exception as exc:
        LOG.debug('프로그램 창 위치 조정 생략 · %s',exc)
    return False
