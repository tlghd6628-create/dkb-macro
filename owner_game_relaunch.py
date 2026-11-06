"""Bring the game back when it closes under a run (짱군네 11-07 04:44: a patch closed it, 2.5 hours lost).

The program already has a launcher start (LauncherFlow: open the official shortcut, press 게임 실행, wait for the game
window, then run). It is used as it is, with three additions:
- After a run ends on an error while no game window is left, this starts that launcher path itself, whatever the
  "런처에서 시작" box says. A stop by the user (F3) is never undone. At most TRIES attempts an hour.
- While the launcher updates itself or the game, its button does not say 게임 실행 yet: wait, pressing 업데이트 when it
  asks, up to UPDATE_MINUTES (user 11-07: updates too).
- The game's own title, patch and 게임 시작 screens are handled by title_step(), called from the start stage.
"""
import logging,threading,time
LOG=logging.getLogger('project_gui.DKB')
TICK_MS=20000;TRIES=6;SPACING=90;UPDATE_MINUTES=45
READY=('게임실행',);UPDATE=('업데이트','설치','다시시도','재시도');BUSY=('%','다운로드','확인중','검사중','준비중','패치')  # not 검사: the launcher always shows 파일 검사하기
# Real 1366x768 game pixels.
TITLE_BAND=(200,560,966,200)
TOUCH=(682,609)
LOADING=('점검하는','다운로드','불러오는')
BAR=(600,680,770,720)   # the patch bar's percent, 36% at 684,699 (07:23)


def _clean(text):
    from owner_text import clean
    return clean(text)


def launcher_words(rows):
    """'ready', 'update' (with the row to press), 'busy' or None from the launcher's bottom words."""
    texts=[(_clean(r['text']),r) for r in rows]
    if any(w in t for t,_ in texts for w in READY):return 'ready',None
    for t,r in texts:
        if any(w in t for w in UPDATE):return 'update',r
    if any(w in t for t,_ in texts for w in BUSY):return 'busy',None
    return None,None


def title_words(rows):
    """'loading', 'touch', ('start', row) or None from the game's bottom band."""
    texts=[(_clean(r['text']),r) for r in rows]
    for t,r in texts:
        if '게임시작' in t:return 'start',r
    # 화면을 눌러주세요; OCR read 눌 as 놀 on the real title (07:25).
    if any('화면을' in t and ('눌러' in t or '주세요' in t) for t,_ in texts):return 'touch',None
    # A percent only on the patch bar: a menu with rates must not hold the start for 45 minutes.
    if any(w in t for t,_ in texts for w in LOADING) or any(t.endswith('%') and BAR[0]<=r['rx']<=BAR[2] and BAR[1]<=r['ry']<=BAR[3]
                                                         for t,r in texts):return 'loading',None
    return None,None


def title_step(service,context,frame,state):
    """One look at a title, patch or 게임 시작 screen in the start stage. True when it acted or waits (the caller keeps
    its unknown-screen clock from running out); state holds when loading began."""
    real=getattr(frame,'hi',None)
    if real is None:return False
    import numpy as np,owner_hd as hd
    from owner_text import read_area
    x,y,w,h=TITLE_BAND;real=np.asarray(real)
    try:rows=read_area(None,real[y:y+h,x:x+w],left=x,top=y,minimum=.6)
    except Exception as exc:
        LOG.debug('타이틀 화면 판독 생략 · %s',type(exc).__name__);return False
    kind,row=title_words(rows)
    if kind is None:
        state.pop('loading',None);return False
    if kind=='loading':
        now=time.monotonic();began=state.setdefault('loading',now)
        if now-began>UPDATE_MINUTES*60:raise RuntimeError('게임 패치·불러오기가 %d분을 넘었습니다.'%UPDATE_MINUTES)
        if now-state.get('said',0)>=60:
            state['said']=now;LOG.info('재접속 · 게임 패치·불러오기 대기 · %d분째',int((now-began)//60))
        context.wait(3);return True
    state.pop('loading',None)
    if kind=='touch':
        LOG.info('재접속 · 타이틀 화면 누름');service.click_hit(hd.real_hit(*TOUCH));context.wait(2.5);return True
    LOG.info('재접속 · 게임 시작 누름 · %d,%d',row['rx'],row['ry'])
    service.click_hit(hd.real_hit(row['rx'],row['ry']));context.wait(6);return True


READ_SECONDS=20


def _launcher_rows(gui,window):
    """The launcher's bottom words, through the same capture the native launcher start uses. Its own 게임 실행 picture
    answers first (no reading); words only otherwise, and a read that does not come back in READ_SECONDS counts as
    nothing seen (07:55: the second try hung in it)."""
    import json,cv2,numpy as np
    from project_adapter import protected_assets
    from project_contract import checked
    from mdt_wgc import capture_client
    from window_resolution import physical_coordinates
    profile=gui.project.root/'profiles'/gui.project.code
    target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['launcher']
    with physical_coordinates():image=capture_client(window.hwnd,target)
    try:
        cfg=gui.official_launcher.config.get('start',{})
        store=json.loads(protected_assets.read_text(checked(profile,target['roi']),encoding='utf-8-sig'));roi=store[cfg['roi']]
        x,y,w,h=(roi[k] for k in ('x','y','w','h'))
        path=checked(checked(profile,target['templates']),roi['image'])
        template=cv2.imdecode(np.frombuffer(protected_assets.read_bytes(path),np.uint8),cv2.IMREAD_COLOR)
        score=cv2.matchTemplate(image[y:y+h,x:x+w,::-1].copy(),template,cv2.TM_CCOEFF_NORMED)
        if float(score.max())>=float(roi.get('threshold',.95)):return [dict(text='게임 실행',score=1.,rx=x+w//2,ry=y+h//2,bounds=(x,y,x+w,y+h))]
    except Exception as exc:LOG.info('런처 게임 실행 그림 확인 생략 · %s',str(exc)[:80])
    cw,ch=target['client_size'];top=int(ch*.7);box={}
    def read():
        from owner_text import read_area
        box['rows']=read_area(None,image[top:,:],left=0,top=top,minimum=.6)
    worker=threading.Thread(target=read,name='dkb-launcher-read',daemon=True);worker.start();worker.join(READ_SECONDS)
    if worker.is_alive():LOG.info('런처 글자 읽기 %d초 초과 · 다음에 다시',READ_SECONDS);return []
    return box.get('rows',[])


def _press(window,context,row):
    from input_safety import InputTransactions
    from launcher_flow import ForegroundPointer
    x,y=row['rx'],row['ry'];x0,y0,x1,y1=row['bounds']
    inputs=InputTransactions(ForegroundPointer(window),context,target=window)
    try:inputs.click(x,y,bounds=(x0-4,y0-4,x1+4,y1+4),hold_seconds=.05)
    finally:inputs.close()


def restore_launcher(title='도깨비의세계 런처'):
    """The launcher start minimizes it after 게임 실행; minimized it has no client and is not found again (08:28)."""
    try:
        import win32gui,win32con
        found=[]
        win32gui.EnumWindows(lambda h,_:found.append(h) if win32gui.GetWindowText(h)==title and win32gui.IsIconic(h) else None,None)
        for h in found:win32gui.ShowWindow(h,win32con.SW_RESTORE)
        if found:LOG.info('최소화된 런처 창 복원 · %d개',len(found))
        return bool(found)
    except Exception as exc:
        LOG.info('런처 창 복원 실패 · %s',str(exc)[:80]);return False


def to_front(hwnd):
    """The launcher's 게임 실행 click is refused while another window covers it (07:55: 입력 지점이 다른 창에 가려져
    있습니다). Windows lets a background process take the foreground after an Alt press."""
    try:
        import ctypes,win32gui,win32con
        user=ctypes.windll.user32
        if win32gui.IsIconic(hwnd):win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
        user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0)
        win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST,0,0,0,0,win32con.SWP_NOMOVE|win32con.SWP_NOSIZE)
        win32gui.SetWindowPos(hwnd,win32con.HWND_NOTOPMOST,0,0,0,0,win32con.SWP_NOMOVE|win32con.SWP_NOSIZE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as exc:
        LOG.info('런처 앞으로 가져오기 실패 · %s',str(exc)[:80]);return False


def wait_launcher_ready(gui,context,clock=time.monotonic,rows=None,press=None,front=to_front):
    """After the launcher opens: wait while it updates, pressing 업데이트 when asked, until 게임 실행 shows."""
    launcher=gui.official_launcher;window=launcher.window
    rows=rows or (lambda:_launcher_rows(gui,window));press=press or (lambda row:_press(window,context,row))
    end=clock()+60
    while not window.candidates():
        context.checkpoint()
        if gui.game_window.candidates():return 'game'
        if clock()>end:return 'no_launcher'
        restore_launcher()
        context.wait(.5)
    if not window.hwnd:window.connect(window.candidates()[0]['hwnd'],context)
    began=clock();said=-1e9;pressed=0
    while True:
        context.checkpoint()
        if gui.game_window.candidates():return 'game'
        LOG.debug('런처 글자 읽기')
        try:kind,row=launcher_words(rows())
        except Exception as exc:
            LOG.info('런처 화면 판독 보류 · %s',str(exc)[:80]);kind,row=None,None
        if kind=='ready':
            if clock()-began>5:LOG.info('런처 준비 완료 · %d분 대기',int((clock()-began)//60))
            if front is not None:front(window.hwnd);context.wait(.8)
            return 'ready'
        if kind=='update' and pressed<3:
            pressed+=1;LOG.info('런처 업데이트 누름 · %s',_clean(row['text']))
            if front is not None:front(window.hwnd);context.wait(.8)
            press(row);context.wait(3);continue
        if clock()-began>UPDATE_MINUTES*60:raise RuntimeError('런처 업데이트 대기 %d분 초과'%UPDATE_MINUTES)
        if clock()-said>=60:said=clock();LOG.info('런처 업데이트 대기 · %d분째',int((clock()-began)//60))
        context.wait(5)


class Watch(logging.Handler):
    """Arms when the game window goes while a run is on, or a run or launcher start ends on an error; F3 disarms.

    Closing the game ends the run either way: an invalid window handle error (04:44) or a plain stop (07:46 test)."""
    def __init__(self,gui):
        super().__init__();self.gui=gui;self.ended=None;self.tries=[];self.live=None
    def emit(self,record):
        try:text=record.getMessage()
        except Exception:return
        if text.startswith(('자동 동작 종료:','게임 준비 중단','Official launcher preparation failed')):self.ended=time.time()
        elif text.startswith('단축키 F3'):self.ended=None;self.live=None
    def tick(self):
        gui=self.gui
        if gui.closed.is_set():return
        try:self.check()
        except Exception as exc:LOG.warning('자동 재접속 확인 실패 · %s',str(exc)[:120])
        gui.root.after(TICK_MS,self.tick)
    def check(self,now=None):
        gui=self.gui;now=time.time() if now is None else now
        state=gui.session.snapshot();games=gui.game_window.candidates()
        if state['status'] in ('running','paused') or state['worker_alive']:
            if games:self.live=now
            return False
        if games:
            self.ended=None;self.live=None;return False   # The game is there: an ordinary stop or error stays.
        # The game went while a run was on: seen running with it at the last look or so.
        if self.ended is None and not (self.live is not None and now-self.live<=TICK_MS/1000+40):return False
        self.live=None
        if not gui.official_launcher.configured:return False
        self.tries=[t for t in self.tries if now-t<3600]
        if len(self.tries)>=TRIES or (self.tries and now-self.tries[-1]<SPACING):return False
        ready=getattr(gui,'_owner_ocr_readiness',None)
        if ready is not None and not ready.done.is_set():return False
        self.tries.append(now)
        LOG.warning('게임 꺼짐 확인 · 런처로 자동 재접속 · %d/%d',len(self.tries),TRIES)
        gui.input_preparation.before_start(lambda:gui.action(self.start))
        return True
    def start(self):
        gui=self.gui;gui.preparation_gate()
        gui._owner_relaunch_force=True;self.checked=False
        try:gui.session.start()
        finally:gui._owner_relaunch_force=False
        gui.root.after(30000,self.stuck)
    def stuck(self):
        """The launcher step did not log in 30 s (07:50, 07:59): write where every thread waits."""
        if getattr(self,'checked',True):return
        import os,sys,traceback
        for ident,frame in sys._current_frames().items():
            rows=traceback.extract_stack(frame)
            if not any('launcher' in r.filename or 'relaunch' in r.filename for r in rows):continue
            rows=rows[-6:]
            LOG.warning('재접속 대기 위치 · %s · %s',ident,' > '.join('%s:%s %s'%(os.path.basename(r.filename),r.lineno,r.name) for r in rows))


def install(gui):
    if getattr(gui,'_owner_relaunch',None) or getattr(gui,'project',None) is None or gui.project.code!='DKB':return
    flow=getattr(gui,'launch_flow',None);launcher=getattr(gui,'official_launcher',None)
    if flow is None or launcher is None:return
    ordinary=flow.enabled
    flow.enabled=lambda:bool(getattr(gui,'_owner_relaunch_force',False)) or ordinary()
    opened=launcher.open
    def open_and_wait():
        state=opened()
        LOG.info('런처 확인 · %s · 런처 창 %d개',state.get('state'),len(state.get('launchers') or []))
        watch.checked=True
        if state.get('games'):return state
        from biol_base.session import Context
        s=gui.session
        result=wait_launcher_ready(gui,Context(s.stop_event,s.pause_event))
        if result=='no_launcher':raise RuntimeError('런처 창이 나타나지 않았습니다.')
        return launcher.snapshot()
    launcher.open=open_and_wait
    # The DKB launcher start then waits for the title by its 897 pictures (버튼_런처_화면을눌러, 게임시작): at 1366 it
    # never saw them and sat on "화면을 눌러 감지 중" for ten minutes (08:05). The start stage reads that screen by its
    # words and presses through it (title_step and the native 게임 시작 handler, live 07:49 and 07:58).
    try:
        import project_adapter.launcher_start as native
        if not getattr(native.DKBLauncherFlow.prepare_game,'_owner_title',False):
            def prepare_game(self,token,context,inputs):
                LOG.info('게임 진입은 시작 화면 처리에 맡김 · 타이틀·게임 시작 글자로 확인')
                return True
            prepare_game._owner_title=True
            native.DKBLauncherFlow.prepare_game=prepare_game
        # After the game closed under a run, the old window handle stays set and the DKB start only waits for it to
        # come back (게임창 복구 대기 · 런처 재실행 없음, 08:18-08:27). A handle that names no live window is cleared
        # first, as after a program restart, where the launcher start worked (07:55).
        if not getattr(native.DKBLauncherFlow.run,'_owner_dead_hwnd',False):
            ordinary_run=native.DKBLauncherFlow.run
            def run(self,token,context):
                window=self.gui.game_window;launcher=self.gui.official_launcher
                if not window.candidates() and (window.hwnd or getattr(launcher,'requested',False) or getattr(self,'game_started',False)):
                    # The DKB start remembers game_started once a game was connected in this program session, and
                    # then only waits for that window to come back (08:31 and 08:36 stacks: wait_window before the
                    # launcher). 'requested' and the old handle stay set too. All three are reset, as on a new program.
                    LOG.info('끊긴 게임창 연결 정리 · 런처로 다시 시작')
                    window.hwnd=0;launcher.requested=False;self.game_started=False;self.game_entry_stage=0
                return ordinary_run(self,token,context)
            run._owner_dead_hwnd=True
            native.DKBLauncherFlow.run=run
    except Exception as exc:LOG.warning('런처 게임 진입 연결 실패 · %s',exc)
    watch=Watch(gui);LOG.addHandler(watch);gui._owner_relaunch=watch
    gui.root.after(TICK_MS,watch.tick)
    LOG.info('자동 재접속 준비 · 게임이 꺼지면 런처로 다시 시작 · 업데이트 대기 %d분',UPDATE_MINUTES)
