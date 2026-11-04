"""F1/F2/F3 controls and an on-demand, game-only screen viewer."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W
from datetime import datetime
import json
import logging
import queue
import threading
import time
from pathlib import Path
import os,uuid

def write_preview(root,image,meta):
    """Save the existing native capture losslessly; no new capture or input."""
    if image is None or not isinstance(meta,dict):raise ValueError('먼저 화면을 불러와 주세요.')
    if image.size!=(meta.get('width'),meta.get('height')):raise ValueError('원본 화면 크기 확인 필요')
    directory=Path(root)/'logs/manual-captures';directory.mkdir(parents=True,exist_ok=True)
    name=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    path=directory/(name+'.png');temporary=directory/(name+'.tmp')
    try:
        image.save(temporary,format='PNG',compress_level=2)
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
    (directory/(name+'.json')).write_text(json.dumps(dict(meta,saved_as=str(path),format='PNG',original_size=True),ensure_ascii=False,indent=2),encoding='utf-8')
    return path

KEYS={0x3101:('F1',0x70),0x3102:('F2',0x71),0x3103:('F3',0x72)}
WM_HOTKEY=0x0312
WM_QUIT=0x0012


class GlobalKeys:
    """Own only three registered hotkeys; no keyboard hook or key recording."""
    def __init__(self, events):
        self.events=events
        self.ready=threading.Event()
        self.stopped=threading.Event()
        self.stop_requested=threading.Event()
        self.thread_id=0
        self.registered=[]
        self.failures={}
        self.error=''
        self.thread=threading.Thread(target=self._run,name='dkb-owner-hotkeys',daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        user=ctypes.WinDLL('user32',use_last_error=True)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentThreadId.restype=W.DWORD
        user.RegisterHotKey.argtypes=[W.HWND,ctypes.c_int,W.UINT,W.UINT]
        user.RegisterHotKey.restype=W.BOOL
        user.UnregisterHotKey.argtypes=[W.HWND,ctypes.c_int]
        user.UnregisterHotKey.restype=W.BOOL
        user.PeekMessageW.argtypes=[ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]
        user.PeekMessageW.restype=W.BOOL
        user.GetMessageW.argtypes=[ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT]
        user.GetMessageW.restype=ctypes.c_int
        try:
            msg=W.MSG()
            user.PeekMessageW(ctypes.byref(msg),None,0,0,0)
            self.thread_id=int(kernel.GetCurrentThreadId())
            for ident,(name,vk) in KEYS.items():
                if self.stop_requested.is_set():break
                if user.RegisterHotKey(None,ident,0x4000,vk):self.registered.append(ident)
                else:self.failures[name]=ctypes.get_last_error()
            self.ready.set()
            while not self.stop_requested.is_set():
                result=user.GetMessageW(ctypes.byref(msg),None,0,0)
                if result==0:break
                if result==-1:raise ctypes.WinError(ctypes.get_last_error())
                if msg.message==WM_HOTKEY and int(msg.wParam) in self.registered:
                    self.events.put((KEYS[int(msg.wParam)][0],time.monotonic()))
        except Exception as exc:
            self.error=str(exc)
        finally:
            for ident in self.registered:user.UnregisterHotKey(None,ident)
            self.ready.set()
            self.stopped.set()

    def close(self):
        self.stop_requested.set()
        if self.thread_id and not self.stopped.is_set():
            user=ctypes.WinDLL('user32',use_last_error=True)
            user.PostThreadMessageW.argtypes=[W.DWORD,W.UINT,W.WPARAM,W.LPARAM]
            user.PostThreadMessageW.restype=W.BOOL
            user.PostThreadMessageW(self.thread_id,WM_QUIT,0,0)
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(.2)


def run_command(gui,command):
    """Reuse the established action gates and worker cancellation generation."""
    if gui.closed.is_set():return 'closing'
    state=gui.session.snapshot()
    if command=='F3':
        gui._owner_start_token=None
        gui.action(gui.session.stop)
        return 'stopped'
    if command=='F2':
        if state['status'] not in ('running','paused'):return 'inactive'
        gui.toggle_pause()
        return 'toggled'
    if command=='F1':
        if state['status']=='running':return 'already_running'
        if state['status']=='paused':
            gui.action(gui.session.resume)
            return 'resumed'
        if state['worker_alive']:return 'cleanup_pending'
        if getattr(getattr(gui,'input_preparation',None),'busy',lambda:False)():return 'preparing'
        gui.start_requested()
        job=getattr(gui,'_owner_ocr_readiness',None)
        if job is not None and not job.done.is_set():
            token=object();gui._owner_start_token=token
            logging.getLogger('project_gui.DKB').info('인식 준비가 끝나면 시작합니다')
            gui.root.after(START_POLL_MS,lambda:start_when_ready(gui,token))
        return 'start_requested'
    raise ValueError('Unknown control')

START_POLL_MS=500;START_SETTLE_MS=1500
def start_when_ready(gui,token,settled=False):
    """F1 right after launch used to vanish: the start was refused while OCR warmed up, silently.
    Keep the request until it is ready. F3 cancels it, and a start that took needs nothing."""
    if gui.closed.is_set() or getattr(gui,'_owner_start_token',None) is not token:return
    state=gui.session.snapshot()
    if state['status'] in ('running','paused') or state['worker_alive']:return
    if not gui._owner_ocr_readiness.done.is_set():
        gui.root.after(START_POLL_MS,lambda:start_when_ready(gui,token));return
    if not settled:
        gui.root.after(START_SETTLE_MS,lambda:start_when_ready(gui,token,True));return
    gui._owner_start_token=None
    gui.start_requested()


def capture_current(gui):
    """Read the identified game client without moving/resizing/focusing it."""
    window=gui.game_window
    item=window.describe(window.hwnd,require_size=False) if window.hwnd else None
    if item is None:
        choices=window.candidates()
        if len(choices)!=1:raise RuntimeError('게임 창을 하나만 열고 게임창 연결을 확인해 주세요.')
        item=choices[0]
    width,height=item['client_width'],item['client_height']
    if min(width,height)<=0 or width*height>32_000_000:raise RuntimeError('게임 화면 크기를 확인해 주세요.')
    from project_adapter import protected_assets
    from runtime_capture import capture
    from PIL import Image
    profile=gui.project.root/'profiles'/gui.project.code
    target=json.loads(protected_assets.read_text(profile/'config/authoring-targets.json',encoding='utf-8-sig'))['targets']['game']
    # Preview may display a manually resized client. Automation keeps its own
    # original size checks; this private copy cannot change the input target.
    target=dict(target,client_size=[width,height])
    frame=capture(item['hwnd'],target)
    after=window.describe(item['hwnd'],require_size=False)
    if not after or any(after[k]!=item[k] for k in ('pid','client_width','client_height')):
        raise RuntimeError('캡처 중 게임 창이 변경됐습니다. 다시 불러와 주세요.')
    if frame.shape!=(height,width,3):raise RuntimeError('게임 화면 크기가 일치하지 않습니다.')
    return Image.fromarray(frame,'RGB'),{
        'time':datetime.now().isoformat(timespec='seconds'),
        'hwnd':item['hwnd'],'pid':item['pid'],'width':width,'height':height,
        'backend':target.get('capture',{}).get('backend'),'game_input':False
    }


class Controls:
    def __init__(self,gui):
        self.gui=gui
        self.events=queue.SimpleQueue()
        self.results=queue.SimpleQueue()
        self.keys=GlobalKeys(self.events)
        self.keys.start()
        self.reported=False
        self.closed=False
        self.job=None
        self.preview=None
        self.preview_token=0
        self.capture_worker=None
        self.reload_requested=False
        self.photo=None
        self.last_preview=None
        self.last_preview_image=None
        self.preview_save=None
        self.screen_link=None
        self.fallback_link=None
        self.gui.root.bind('<Destroy>',lambda e:self.close() if e.widget is self.gui.root else None,add='+')
        self.paint(scan=True)
        # The native tick owns captions too. Repaint directly after it instead
        # of racing a separate 30ms timer against the native text assignments.
        ordinary_sync=gui.sync_compact_state
        def sync():
            ordinary_sync()
            if not self.closed:self.paint()
        gui.sync_compact_state=sync
        self.gui.root.bind('<Configure>',lambda e:self.gui.root.after_idle(self.position_screen)
                           if e.widget is self.gui.root and not self.closed else None,add='+')
        from owner_telegram_ui import TelegramPanel
        self.telegram=TelegramPanel(self)
        self.job=gui.root.after(30,self.poll)

    def paint(self,scan=False):
        from tkinter import TclError
        from tkinter import ttk
        style=ttk.Style(self.gui.root)
        for button in (self.gui.start_button,self.gui.pause_toggle,self.gui.stop_button):
            current=str(button.cget('style')) or 'TButton'
            if not current.startswith('OwnerKeys.'):
                owned='OwnerKeys.'+current
                style.configure(owned,font=('Malgun Gothic',9,'bold'),padding=(1,3))
                button.configure(style=owned)
        pause='계속 F2' if self.gui.session.snapshot()['status']=='paused' else '일시정지 F2'
        originals=getattr(getattr(self.gui,'visual_view',None),'originals',{})
        for key,widget,text in (('start',self.gui.start_button,'시작 F1'),('stop',self.gui.stop_button,'중지 F3'),
                                ('pause',self.gui.pause_toggle,pause)):
            for target in {widget,originals.get(key,widget)}:
                if str(target.cget('text'))!=text:target.configure(text=text)
        if not scan:return
        found=False
        self.screen_link=None
        stack=[self.gui.root]
        while stack:
            widget=stack.pop();stack.extend(widget.winfo_children())
            try:
                if str(widget.cget('text')) in ('만료일 확인 중','사용 기간 제한 없음','현재 화면'):
                    if widget is self.fallback_link:continue
                    found=True
                    if self.screen_link is None or widget.winfo_ismapped():self.screen_link=widget
                    widget.configure(textvariable='',text='현재 화면',cursor='hand2')
                    if widget.winfo_class() not in ('TButton','Button'):
                        widget.configure(foreground='#256AAB')
                        widget.bind('<Button-1>',lambda event:self.show_preview())
            except TclError:pass
        if not found:
            from tkinter import ttk
            if self.fallback_link is None or not self.fallback_link.winfo_exists():
                self.fallback_link=ttk.Button(self.gui.root,text='현재 화면',style='UpdateLink.TButton',command=self.show_preview)
            self.screen_link=self.fallback_link
            self.gui.root.after_idle(self.position_screen)
        elif self.fallback_link is not None:
            self.fallback_link.destroy();self.fallback_link=None
        if hasattr(self,'telegram'):self.telegram.paint()

    def position_screen(self):
        if self.closed or self.screen_link is not self.fallback_link or self.fallback_link is None:return
        root=self.gui.root;update=self.gui.update_button
        right=update.winfo_rootx()-root.winfo_rootx()-4
        self.fallback_link.place(x=max(0,right-62),y=update.winfo_rooty()-root.winfo_rooty(),
                                 width=62,height=max(22,update.winfo_height()))

    def poll(self):
        self.job=None
        if self.closed:return
        if self.gui.closed.is_set():self.close();return
        if not self.reported and self.keys.ready.is_set():
            self.reported=True
            if self.keys.error:self.gui.logger.warning('단축키 등록 실패: %s',self.keys.error)
            if self.keys.failures:
                self.gui.logger.warning('다른 프로그램이 사용 중인 단축키: %s',' / '.join(self.keys.failures))
            if len(self.keys.registered)==3:self.gui.logger.info('단축키 준비 완료 · F1 시작 / F2 일시정지·계속 / F3 중지')
        commands=[]
        while not self.events.empty():
            command,stamp=self.events.get()
            if command=='F3' or time.monotonic()-stamp<=2:commands.append(command)
        # Stop dominates a burst, so queued Start cannot undo a newer Stop.
        if 'F3' in commands:commands=['F3']
        for command in commands:
            try:
                result=run_command(self.gui,command)
                self.gui.logger.info('단축키 %s · %s',command,result,extra={'gui_suppress':True})
            except Exception:
                self.gui.logger.exception('단축키 처리 실패',extra={'gui_suppress':True})
        self.paint()
        self.telegram.poll()
        while not self.results.empty():
            token,payload,meta,error=self.results.get()
            if token!=self.preview_token or self.preview is None:continue
            self.reload.configure(state='normal')
            if error:
                self.photo=None
                self.last_preview_image=None;self.last_preview=None
                if self.preview_save is not None:self.preview_save.configure(state='disabled')
                self.picture.configure(image='',text=error)
                self.preview_status.set('불러오기 실패 · 이전 화면을 표시하지 않습니다.')
                self.gui.logger.warning('현재 화면 불러오기 실패: %s',error)
            else:
                from PIL import Image,ImageTk
                self.last_preview_image=payload.copy()
                payload.thumbnail((900,500),Image.Resampling.LANCZOS)
                self.photo=ImageTk.PhotoImage(payload,master=self.preview)
                self.picture.configure(image=self.photo,text='')
                self.preview_status.set('%s · %d × %d'%(meta['time'][11:],meta['width'],meta['height']))
                self.last_preview=meta
                if self.preview_save is not None:self.preview_save.configure(state='normal')
                self.gui.logger.info('현재 화면 로드 완료 · %dx%d',meta['width'],meta['height'])
        if self.reload_requested and self.preview is not None and not self.capture_worker.is_alive():
            self.load_preview()
        self.job=self.gui.root.after(30,self.poll)

    def show_preview(self):
        if self.closed:return
        import tkinter as tk
        from tkinter import ttk
        if self.preview is not None:
            self.preview.deiconify();self.preview.lift();self.load_preview();return
        self.preview=tk.Toplevel(self.gui.root)
        self.preview.title('DKB · 현재 게임 화면')
        self.preview.transient(self.gui.root)
        self.preview.iconbitmap(default=str(self.gui.icon_path))
        self.preview.protocol('WM_DELETE_WINDOW',self.close_preview)
        bar=ttk.Frame(self.preview,padding=8);bar.pack(fill='x')
        self.reload=ttk.Button(bar,text='화면 다시 불러오기',command=self.load_preview)
        self.reload.pack(side='left')
        self.preview_save=ttk.Button(bar,text='원본 저장',command=self.save_preview,state='disabled')
        self.preview_save.pack(side='left',padx=6)
        self.preview_status=tk.StringVar(self.preview,value='불러오는 중…')
        ttk.Label(bar,textvariable=self.preview_status).pack(side='left',padx=12)
        self.picture=ttk.Label(self.preview,text='게임 화면을 불러오는 중입니다.',anchor='center')
        self.picture.pack(padx=8,pady=(0,8))
        self.load_preview()

    def load_preview(self):
        if self.closed or self.preview is None:return
        if self.capture_worker and self.capture_worker.is_alive():
            self.reload_requested=True
            return
        self.reload_requested=False
        self.preview_token+=1
        token=self.preview_token
        self.reload.configure(state='disabled')
        if self.preview_save is not None:self.preview_save.configure(state='disabled')
        self.preview_status.set('불러오는 중…')
        def work():
            try:
                payload,meta=capture_current(self.gui)
                result=(token,payload,meta,'')
            except Exception as exc:result=(token,None,None,str(exc))
            if not self.closed:self.results.put(result)
        self.capture_worker=threading.Thread(target=work,name='dkb-current-screen',daemon=True)
        self.capture_worker.start()

    def save_preview(self):
        try:
            path=write_preview(self.gui.project.root,self.last_preview_image,self.last_preview)
            self.preview_status.set('원본 저장 완료 · '+path.name)
            self.gui.logger.info('현재 화면 원본 저장 · %s',path)
        except (OSError,ValueError) as exc:
            self.preview_status.set('저장 실패 · '+str(exc))
            self.gui.logger.warning('현재 화면 원본 저장 실패 · %s',exc)

    def close_preview(self):
        self.preview_token+=1
        self.reload_requested=False
        window=self.preview;self.preview=None;self.photo=None
        self.last_preview_image=None;self.last_preview=None;self.preview_save=None
        if window is not None:window.destroy()

    def close(self):
        if self.closed:return
        self.closed=True
        if hasattr(self,'telegram'):self.telegram.close()
        self.keys.close()
        if self.job is not None:
            try:self.gui.root.after_cancel(self.job)
            except Exception:pass
            self.job=None
        self.preview_token+=1


def install(gui):
    from owner_window_policy import install as install_window_policy
    install_window_policy(gui)
    controls=getattr(gui,'_owner_controls',None)
    if controls is None:
        gui._owner_controls=Controls(gui)
    else:
        controls.paint(scan=True)
