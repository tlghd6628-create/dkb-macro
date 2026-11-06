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
TICK_MS=20000;TRIES=4;SPACING=300;UPDATE_MINUTES=45
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


def _launcher_rows(gui,window):
    """The launcher client's bottom words, through the same capture the native launcher start uses."""
    import json
    from project_adapter import protected_assets
    from mdt_wgc import capture_client
    from window_resolution import physical_coordinates
    from owner_text import read_area
    profile=gui.project.root/'profiles'/gui.project.code
    target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['launcher']
    with physical_coordinates():image=capture_client(window.hwnd,target)
    cw,ch=target['client_size'];top=int(ch*.7)
    return read_area(None,image[top:,:],left=0,top=top,minimum=.6)


def _press(window,context,row):
    from input_safety import InputTransactions
    from launcher_flow import ForegroundPointer
    x,y=row['rx'],row['ry'];x0,y0,x1,y1=row['bounds']
    inputs=InputTransactions(ForegroundPointer(window),context,target=window)
    try:inputs.click(x,y,bounds=(x0-4,y0-4,x1+4,y1+4),hold_seconds=.05)
    finally:inputs.close()


def wait_launcher_ready(gui,context,clock=time.monotonic,rows=None,press=None):
    """After the launcher opens: wait while it updates, pressing 업데이트 when asked, until 게임 실행 shows."""
    launcher=gui.official_launcher;window=launcher.window
    rows=rows or (lambda:_launcher_rows(gui,window));press=press or (lambda row:_press(window,context,row))
    end=clock()+60
    while not window.candidates():
        context.checkpoint()
        if gui.game_window.candidates():return 'game'
        if clock()>end:return 'no_launcher'
        context.wait(.5)
    if not window.hwnd:window.connect(window.candidates()[0]['hwnd'],context)
    began=clock();said=0;pressed=0
    while True:
        context.checkpoint()
        if gui.game_window.candidates():return 'game'
        try:kind,row=launcher_words(rows())
        except Exception as exc:
            LOG.info('런처 화면 판독 보류 · %s',str(exc)[:80]);kind,row=None,None
        if kind=='ready':
            if clock()-began>5:LOG.info('런처 준비 완료 · %d분 대기',int((clock()-began)//60))
            return 'ready'
        if kind=='update' and pressed<3:
            pressed+=1;LOG.info('런처 업데이트 누름 · %s',_clean(row['text']));press(row);context.wait(3);continue
        if clock()-began>UPDATE_MINUTES*60:raise RuntimeError('런처 업데이트 대기 %d분 초과'%UPDATE_MINUTES)
        if clock()-said>=60:said=clock();LOG.info('런처 업데이트 대기 · %d분째',int((clock()-began)//60))
        context.wait(5)


class Watch(logging.Handler):
    """Arms on a run that ended on an error, disarms on the user's stop."""
    def __init__(self,gui):
        super().__init__();self.gui=gui;self.ended=None;self.tries=[]
    def emit(self,record):
        try:text=record.getMessage()
        except Exception:return
        if text.startswith('자동 동작 종료:') or text.startswith('게임 준비 중단'):self.ended=time.time()
        elif '사용자 정지' in text or text.startswith('단축키 F3'):self.ended=None
    def tick(self):
        gui=self.gui
        if gui.closed.is_set():return
        try:self.check()
        except Exception as exc:LOG.warning('자동 재접속 확인 실패 · %s',str(exc)[:120])
        gui.root.after(TICK_MS,self.tick)
    def check(self,now=None):
        gui=self.gui;now=time.time() if now is None else now
        if self.ended is None:return False
        state=gui.session.snapshot()
        if state['status'] in ('running','paused') or state['worker_alive']:return False
        if gui.game_window.candidates():
            self.ended=None;return False   # The game is there: an ordinary error stays stopped as before.
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
        gui._owner_relaunch_force=True
        try:gui.session.start()
        finally:gui._owner_relaunch_force=False


def install(gui):
    if getattr(gui,'_owner_relaunch',None) or getattr(gui,'project',None) is None or gui.project.code!='DKB':return
    flow=getattr(gui,'launch_flow',None);launcher=getattr(gui,'official_launcher',None)
    if flow is None or launcher is None:return
    ordinary=flow.enabled
    flow.enabled=lambda:bool(getattr(gui,'_owner_relaunch_force',False)) or ordinary()
    opened=launcher.open
    def open_and_wait():
        state=opened()
        if state.get('games'):return state
        from biol_base.session import Context
        s=gui.session
        result=wait_launcher_ready(gui,Context(s.stop_event,s.pause_event))
        if result=='no_launcher':raise RuntimeError('런처 창이 나타나지 않았습니다.')
        return launcher.snapshot()
    launcher.open=open_and_wait
    watch=Watch(gui);LOG.addHandler(watch);gui._owner_relaunch=watch
    gui.root.after(TICK_MS,watch.tick)
    LOG.info('자동 재접속 준비 · 게임이 꺼지면 런처로 다시 시작 · 업데이트 대기 %d분',UPDATE_MINUTES)
