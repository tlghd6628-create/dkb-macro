"""Tk settings/pairing UI and GUI-thread bridge for the dedicated bot."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from owner_telegram import Config,Store,Client,Service,jpeg

LABELS={'running':'실행 중','paused':'일시정지','stopped':'중지','error':'오류'}

def obsolete_start(panel,service,item):
    """Remote order uses update IDs; a local stop cancels already queued work.

    Never compare Telegram dates with the PC wall clock. A batched Start with
    a newer update ID remains valid even if both events reached Tk before Stop.
    """
    barrier=getattr(panel,'last_stop_update',None)
    if barrier is not None and barrier[0] is service:
        ident=item.get('update_id')
        return type(ident) is not int or ident<=barrier[1]
    stopped=panel.last_stop
    if not stopped:return False
    queued=item.get('queued_at')
    if not isinstance(queued,(int,float)) or queued<=stopped:return True
    server_now=getattr(getattr(service,'client',None),'server_now',lambda:None)()
    if server_now is not None:
        # Also reject older, previously unread commands after a LOCAL stop.
        stopped_server=server_now-max(0,time.monotonic()-stopped)
        return item.get('date',0)<int(stopped_server)
    return False


class TelegramPanel:
    def __init__(self,controls):
        self.controls=controls;self.gui=controls.gui
        self.events=queue.SimpleQueue();self.service=None;self.dialog=None;self.button=None
        self.status='미연결';self.configuring=False;self.screen_busy=False;self.schedule_busy=False;self.growth_busy=False;self.watch=[]
        self.closed=False;self.last_stop=0.;self.last_stop_update=None;self.last_screen=0.;self.generation=0
        self.path=self.gui.project.root/'settings/telegram-owner.dat'
        self.load_error=''
        try:self.store=Store(self.path)
        except ValueError as exc:
            self.store=None;self.load_error=str(exc);self.status=self.load_error
        ordinary_stop=self.gui.session.stop
        def stopped():
            self.last_stop=time.monotonic();self.last_stop_update=None
            self.watch=[]
            ordinary_stop()
        self.gui.session.stop=stopped
        cfg=self.store.snapshot() if self.store else Config()
        if cfg.enabled:self.start_service()
        self.paint()
        self.gui.root.bind('<Configure>',lambda e:self.gui.root.after_idle(self.position)
                           if e.widget is self.gui.root and not self.closed else None,add='+')
        # NativeLayout clones the toolbar and maps it after the first idle.
        # Recheck settled geometry rather than anchoring to an off-screen label.
        for delay in (100,300,1000):self.gui.root.after(delay,self.position)

    def paint(self):
        if self.closed:return
        if self.button is None or not self.button.winfo_exists():
            self.button=ttk.Button(self.gui.root,text='텔레그램',style='UpdateLink.TButton',command=self.show)
            self.gui.root.after_idle(self.position)

    def position(self):
        if self.closed or self.button is None or not self.button.winfo_exists():return
        parent=self.gui.root
        update=self.gui.update_button
        if not update.winfo_ismapped() or not self.gui.stop_button.winfo_ismapped():return
        # The displayed update control is a stable anchor in both layouts.
        # Leave one current-screen link width between it and this button.
        right=update.winfo_rootx()-parent.winfo_rootx()-6
        left=self.gui.stop_button.winfo_rootx()+self.gui.stop_button.winfo_width()-parent.winfo_rootx()+4
        width=min(70,max(0,right-left))
        if width>=50:
            self.button.place(x=right-width,y=update.winfo_rooty()-parent.winfo_rooty(),width=width,
                              height=max(22,update.winfo_height()))
            self.button.lift()

    def set_status(self,text):
        if text==self.status:return
        self.status=text
        if self.dialog is not None:self.status_var.set(text)

    def start_service(self):
        if self.store is None:return
        cfg=self.store.snapshot()
        if not cfg.enabled:return
        if self.service and not self.service.stop.is_set() and self.service.token==cfg.token:return
        if self.service:self.service.close()
        self.service=Service(self.store,self.events);self.service.start()
        self.set_status('연결 중…')

    def show(self):
        if self.closed:return
        if self.dialog is not None:
            self.dialog.deiconify();self.dialog.lift();return
        cfg=self.store.snapshot() if self.store else Config()
        win=tk.Toplevel(self.gui.root);self.dialog=win
        win.title('DKB · 텔레그램 연결');win.transient(self.gui.root)
        win.iconbitmap(default=str(self.gui.icon_path));win.resizable(False,False)
        win.protocol('WM_DELETE_WINDOW',self.hide)
        frame=ttk.Frame(win,padding=14);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='도깨비 전용 봇으로 시작·일시정지·중지·현재 화면·스케줄표를 이용합니다.').grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,10))
        ttk.Label(frame,text='봇 토큰').grid(row=1,column=0,sticky='w')
        self.token_var=tk.StringVar(win,value=cfg.token)
        entry=ttk.Entry(frame,textvariable=self.token_var,show='●',width=52)
        entry.grid(row=1,column=1,columnspan=2,sticky='ew',padx=(8,0))
        self.enabled_var=tk.BooleanVar(win,value=cfg.enabled or not cfg.token)
        ttk.Checkbutton(frame,text='이 PC에서 텔레그램 연결 사용',variable=self.enabled_var).grid(row=2,column=0,columnspan=3,sticky='w',pady=8)
        self.save_button=ttk.Button(frame,text='저장·연결',command=self.configure)
        self.save_button.grid(row=3,column=0,sticky='w')
        self.code_button=ttk.Button(frame,text='본인 계정 연결 코드 발급',command=self.pair)
        self.code_button.grid(row=3,column=1,sticky='w',padx=8)
        ttk.Button(frame,text='연결 해제',command=self.disconnect).grid(row=3,column=2,sticky='e')
        self.status_var=tk.StringVar(win,value=self.status)
        ttk.Label(frame,textvariable=self.status_var,wraplength=470).grid(row=4,column=0,columnspan=3,sticky='w',pady=(12,6))
        self.code_var=tk.StringVar(win,value='본인 계정을 연결하면 제어 버튼이 봇 대화에 표시됩니다.')
        ttk.Label(frame,textvariable=self.code_var,wraplength=470).grid(row=5,column=0,columnspan=3,sticky='w',pady=4)
        ttk.Button(frame,text='연결 명령 복사',command=self.copy_code).grid(row=6,column=0,columnspan=3,sticky='w',pady=4)
        ttk.Label(frame,text='1. BotFather에서 /newbot으로 도깨비용 봇 만들기\n2. 받은 토큰을 위에 입력하고 저장·연결\n3. 발급된 /연결 명령을 그 봇의 개인 대화에 보내기\n토큰은 이 Windows 사용자 계정으로 암호화 저장됩니다.').grid(row=7,column=0,columnspan=3,sticky='w',pady=(10,0))
        self.current_code=''
        if cfg.chat_id:self.code_var.set('본인 계정 연결 완료 · 봇 대화에서 시작 또는 상태를 보내세요.')

    def hide(self):
        win=self.dialog;self.dialog=None
        if win is not None:win.destroy()

    def configure(self):
        if self.configuring or self.dialog is None:return
        token=self.token_var.get().strip();enabled=self.enabled_var.get()
        try:Config(token=token,enabled=enabled).validate()
        except ValueError as exc:self.set_status(str(exc));return
        if not enabled:
            if self.service:self.service.close();self.service=None
            if self.store:
                try:self.store.update(enabled=False)
                except Exception:self.set_status('연결은 중단했지만 설정 저장에 실패했습니다. 다시 확인해 주세요.');return
            self.set_status('연결 사용 안 함');return
        self.configuring=True;self.save_button.configure(state='disabled');self.set_status('봇 정보 확인 중…')
        serial=self.generation
        def work():
            try:
                client=Client();identity=client.call(token,'getMe')
                hook=client.call(token,'getWebhookInfo')
                if hook.get('url'):raise ValueError('다른 서버가 사용하는 봇입니다. 도깨비 전용 새 봇을 연결해 주세요.')
                if identity.get('is_bot') is not True:raise ValueError('봇 토큰을 확인해 주세요.')
                cfg=Config(token=token,enabled=True,bot_id=int(identity['id']),username=str(identity.get('username','')))
                cfg.validate();result=('configured',(serial,cfg,''))
            except Exception as exc:result=('configured',(serial,None,str(exc) if isinstance(exc,ValueError) else '봇 연결을 확인하지 못했습니다.'))
            if not self.closed:self.events.put(result)
        threading.Thread(target=work,name='dkb-telegram-check',daemon=True).start()

    def pair(self):
        if not self.service or not self.store or not self.store.snapshot().enabled:
            self.set_status('먼저 봇 토큰을 입력하고 저장·연결을 눌러 주세요.');return
        cfg=self.store.snapshot()
        if cfg.chat_id:
            self.set_status('이미 본인 계정이 연결돼 있습니다. 변경하려면 연결 해제 후 다시 설정하세요.');return
        self.current_code=self.service.router.issue_code()
        if self.dialog is not None:
            self.code_var.set('@%s 개인 대화에 전송 (5분 안에):\n/연결 %s'%(cfg.username,self.current_code))
        self.set_status('연결 코드 입력 대기')

    def copy_code(self):
        if not self.current_code:return
        self.gui.root.clipboard_clear();self.gui.root.clipboard_append('/연결 '+self.current_code)

    def disconnect(self):
        self.generation+=1
        if self.service:self.service.close();self.service=None
        self.watch=[]
        if self.store:
            try:self.store.update(enabled=False,chat_id=0,user_id=0)
            except Exception:self.set_status('연결은 중단했지만 설정 저장에 실패했습니다. 다시 확인해 주세요.');return
        self.current_code=''
        if self.dialog is not None:self.code_var.set('연결 해제됨. 새로 저장·연결 후 코드를 발급하세요.')
        self.set_status('연결 해제됨')

    def status_text(self):
        snapshot=self.gui.session.snapshot()
        return 'DKB · %s\n게임: %s'%(LABELS.get(snapshot['status'],snapshot['status']),
                                  '연결됨' if self.gui.game_window.connected() else '연결 필요')

    def command(self,service,item):
        if self.closed or self.gui.closed.is_set() or service is not self.service:return
        cfg=self.store.snapshot()
        if not cfg.enabled or item['chat_id']!=cfg.chat_id:return
        kind=item['kind'];chat=item['chat_id']
        if kind=='paired':
            self.current_code=''
            if self.dialog is not None:self.code_var.set('본인 계정 연결 완료 · 봇 대화의 버튼으로 조작하세요.')
            self.set_status('연결됨');service.reply(chat,'도깨비 프로그램과 연결했습니다.\n'+self.status_text());return
        if kind in ('status','menu'):service.reply(chat,self.status_text());return
        if kind=='growth':self.growth(service,chat,page=item.get('page',1));return
        if kind in ('schedule','schedule_today','schedule_week'):
            panel=getattr(self.gui,'_owner_schedule',None)
            if panel is None:service.reply(chat,'스케줄표를 준비하지 못했습니다. 최신 프로그램인지 확인해 주세요.');return
            group={'schedule':'전체','schedule_today':'일일','schedule_week':'주간'}[kind]
            self.schedule(service,chat,panel.collector.snapshot(today=True),group)
            return
        from owner_controls import run_command
        if kind=='start':
            if obsolete_start(self,service,item):
                logger=getattr(self.gui,'logger',None)
                if logger:logger.info('텔레그램 이전 시작 요청 제외 · 시작번호=%s · 중지번호=%s · 시각기준=%s',item.get('update_id'),(getattr(self,'last_stop_update',None) or (None,None))[1],item.get('clock_source','unknown'))
                service.reply(chat,'중지 이전에 보낸 시작 요청입니다. 시작을 다시 눌러 주세요.');return
            result=run_command(self.gui,'F1')
            snapshot=self.gui.session.snapshot()
            preparing=(getattr(self.gui.input_preparation,'busy',lambda:False)()
                       or getattr(getattr(self.gui,'launch_flow',None),'preparing',False))
            if preparing:
                service.reply(chat,'시작 준비 중입니다.')
                if not any(w[0] is service and w[1]==chat and w[2]=='start' for w in self.watch):
                    self.watch.append((service,chat,'start',time.monotonic()+40,snapshot['generation']))
            elif snapshot['status']=='running':service.reply(chat,'이미 실행 중입니다.' if result=='already_running' else '사냥 자동화를 시작·재개했습니다.')
            else:service.reply(chat,'시작하지 못했습니다.\n'+self.gui.game_hint.get())
        elif kind=='pause':
            if self.gui.session.snapshot()['status']=='running':run_command(self.gui,'F2')
            service.reply(chat,self.status_text())
        elif kind=='stop':
            run_command(self.gui,'F3');snapshot=self.gui.session.snapshot()
            ident=item.get('update_id')
            if type(ident) is int:self.last_stop_update=(service,ident)
            if snapshot['worker_alive']:
                service.reply(chat,'중지 요청을 전달했습니다. 입력 정리 중입니다.')
                self.watch.append((service,chat,'stop',time.monotonic()+15,snapshot['generation']))
            else:service.reply(chat,'사냥 자동화를 중지했습니다.')
        elif kind=='screen':self.screen(service,chat)

    def growth(self,service,chat,*,page=1):
        if getattr(self,'growth_busy',False):
            service.reply(chat,'성장현황을 만드는 중입니다. 잠시만 기다려 주세요.');return
        self.growth_busy=True
        def work():
            try:
                from owner_growth_report import project,sheets
                snapshot=project(self.gui.project.root)
                from owner_growth_report import page_batch
                pages=page_batch(sheets(snapshot),page);scope=snapshot['identity'];problem=''
            except Exception:
                pages=[];scope=None;problem='성장현황을 불러오지 못했습니다. 서버·캐릭터 설정과 저장 기록을 확인해 주세요.'
            if not self.closed:self.events.put(('growth',(service,chat,scope,pages,problem)))
        threading.Thread(target=work,name='dkb-telegram-growth',daemon=True).start()

    def schedule(self,service,chat,snapshot,group):
        if getattr(self,'schedule_busy',False):
            service.reply(chat,'스케줄표를 만드는 중입니다. 잠시만 기다려 주세요.');return
        if not snapshot:service.reply(chat,'스케줄 기록을 준비하는 중입니다. 잠시 후 다시 요청해 주세요.');return
        self.schedule_busy=True
        def work():
            try:
                from owner_schedule_image import sheets
                pages=sheets(snapshot,group);problem=''
            except Exception:
                pages=[];problem='이미지 스케줄표를 만들지 못했습니다. PC 스케줄표에서 확인해 주세요.'
            if not self.closed:self.events.put(('schedule',(service,chat,pages,problem)))
        threading.Thread(target=work,name='dkb-telegram-schedule',daemon=True).start()

    def screen(self,service,chat):
        if self.screen_busy or time.monotonic()-self.last_screen<2:
            service.reply(chat,'화면을 불러오는 중입니다. 잠시 후 다시 요청해 주세요.');return
        self.screen_busy=True;self.last_screen=time.monotonic()
        snapshot=self.gui.session.snapshot();state=LABELS.get(snapshot['status'],snapshot['status'])
        def work():
            try:
                from owner_controls import capture_current
                image,meta=capture_current(self.gui)
                result=(service,chat,jpeg(image),'DKB · 현재 게임 화면\n%s · %s'%(state,meta['time'][11:]),'')
            except Exception:result=(service,chat,None,'','게임 화면을 불러오지 못했습니다. 게임 창의 연결·최소화 상태를 확인해 주세요.')
            if not self.closed:self.events.put(('screen',result))
        threading.Thread(target=work,name='dkb-telegram-screen',daemon=True).start()

    def poll(self):
        if self.closed:return
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='status':
                source,text=value
                if source is self.service:self.set_status(text)
            elif kind=='command':
                try:self.command(*value)
                except Exception:
                    service,item=value
                    if service is self.service:service.reply(item['chat_id'],'요청을 처리하지 못했습니다. PC 프로그램 상태를 확인해 주세요.')
            elif kind=='growth':
                self.growth_busy=False;service,chat,scope,pages,problem=value
                if service is self.service:
                    if not problem:
                        try:
                            from owner_growth_report import identity
                            if identity(self.gui.project.root)[0]!=scope:problem='캐릭터 설정이 바뀌었습니다. 성장현황을 다시 눌러 주세요.'
                        except (OSError,ValueError,KeyError,TypeError):problem='서버·캐릭터 설정을 확인해 주세요.'
                    if problem:service.reply(chat,problem)
                    else:
                        for photo,caption in pages:service.reply(chat,caption,photo=photo)
            elif kind=='schedule':
                self.schedule_busy=False;service,chat,pages,problem=value
                if service is self.service:
                    if problem:service.reply(chat,problem)
                    for photo,caption in pages:service.reply(chat,caption,photo=photo)
            elif kind=='screen':
                self.screen_busy=False;service,chat,photo,caption,problem=value
                if service is self.service:service.reply(chat,problem or caption,photo=photo)
            elif kind=='configured':
                serial,cfg,problem=value
                self.configuring=False
                if self.dialog is not None:self.save_button.configure(state='normal')
                if serial!=self.generation:continue
                if problem:self.set_status(problem);continue
                try:
                    if self.store is None:
                        # Preserve an unreadable old settings file for diagnostics.
                        if self.path.exists():self.path.replace(self.path.with_name('telegram-owner.unreadable-'+str(int(time.time()))+'.dat'))
                        self.store=Store(self.path)
                    with self.store.lock:
                        old=self.store.snapshot()
                        values=asdict(cfg)
                        if old.token==cfg.token:values.update(chat_id=old.chat_id,user_id=old.user_id,offset=old.offset)
                        self.store.update(**values)
                    self.start_service()
                    if not self.store.snapshot().chat_id:self.pair()
                    else:self.set_status('연결됨')
                except Exception:self.set_status('텔레그램 설정을 저장하지 못했습니다.')
        remaining=[]
        for service,chat,kind,deadline,generation in self.watch:
            if service is not self.service:continue
            snapshot=self.gui.session.snapshot()
            if kind=='stop' and snapshot['generation']!=generation:continue
            preparing=(getattr(self.gui.input_preparation,'busy',lambda:False)()
                       or getattr(getattr(self.gui,'launch_flow',None),'preparing',False))
            done=(snapshot['status']=='running' and not preparing) if kind=='start' else not snapshot['worker_alive']
            if done:service.reply(chat,'사냥 자동화를 시작했습니다.' if kind=='start' else '사냥 자동화를 중지했습니다.')
            elif time.monotonic()>deadline:service.reply(chat,'처리가 지연되고 있습니다.\n'+self.status_text())
            else:remaining.append((service,chat,kind,deadline,generation))
        self.watch=remaining
        if (self.dialog is not None and self.current_code and self.service
                and time.monotonic()>=self.service.router.expires):
            self.current_code='';self.code_var.set('연결 코드가 만료됐습니다. 연결 코드 발급을 다시 눌러 주세요.')

    def close(self):
        if self.closed:return
        self.closed=True
        if self.service:self.service.close()
        self.watch=[]
