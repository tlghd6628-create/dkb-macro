"""Non-controlling schedule window shared with personal Telegram queries."""
from datetime import timedelta,datetime
import tkinter as tk
from tkinter import ttk
from owner_schedule import game_day,now_kst,KST,BY_KEY,telegram_pages
from owner_schedule_feed import Collector


class SchedulePanel:
    def __init__(self,gui):
        self.gui=gui;self.closed=False;self.dialog=None;self.button=None;self.timer=None
        self.collector=Collector(gui.project.root,gui.logger)
        self.day=None;self.last_snapshot=None;self.last_render=None
        self.root_button=ttk.Button(gui.root,text='스케줄표',command=self.show)
        frame=getattr(getattr(gui,'_owner_main',None),'frame',None)
        self.mode_button=ttk.Button(frame,text='스케줄표',command=self.show) if frame is not None else None
        self.button=self.root_button
        gui.root.bind('<Destroy>',lambda e:self.close() if e.widget is gui.root else None,add='+')
        self.timer=gui.root.after(100,self.poll)

    def position(self):
        frame=getattr(getattr(self.gui,'_owner_main',None),'frame',None)
        view=getattr(self.gui,'visual_view',None)
        if frame is not None and frame.winfo_ismapped() and not getattr(view,'hud',False):
            # The native panel lifts itself every250ms. A root sibling gets
            # hidden between snapshots and clicks; parent this control inside.
            self.root_button.place_forget();self.button=self.mode_button
            self.button.place(relx=1,x=-88,y=0,width=83,height=23);self.button.lift()
        else:
            if self.mode_button is not None:self.mode_button.place_forget()
            self.button=self.root_button
            stop=getattr(self.gui,'stop_button',None)
            controls=getattr(self.gui,'_owner_controls',None)
            telegram=getattr(getattr(controls,'telegram',None),'button',None)
            if stop is None:self.button.place_forget();return
            if telegram is not None and telegram.winfo_ismapped():
                left=stop.winfo_x()+stop.winfo_width()+5;right=telegram.winfo_x()-5
                if right-left>=60:self.button.place(x=left,y=telegram.winfo_y(),width=min(83,right-left),height=23);self.button.lift();return
            self.button.place_forget()

    def poll(self):
        if self.closed:return
        self.position();session=self.gui.session.snapshot();status=session.get('status','stopped')
        self.collector.request(status,self.day,session.get('current_task',''))
        self.last_snapshot=self.collector.snapshot()
        if self.dialog is not None and self.last_snapshot:self.render(self.last_snapshot)
        elif self.dialog is not None:self.summary.set(self.collector.issue or '기록을 준비하는 중입니다.')
        self.timer=self.gui.root.after(1000,self.poll)

    def show(self):
        if self.closed:return
        if self.dialog is not None:self.dialog.deiconify();self.dialog.lift();return
        win=tk.Toplevel(self.gui.root);self.dialog=win;win.title('DKB · 스케줄표')
        win.geometry('1180x670');win.minsize(900,530);win.transient(self.gui.root)
        win.protocol('WM_DELETE_WINDOW',self.hide)
        bar=ttk.Frame(win,padding=10);bar.pack(fill='x')
        ttk.Label(bar,text='보기').pack(side='left')
        self.group=tk.StringVar(win,value='전체')
        combo=ttk.Combobox(bar,textvariable=self.group,values=['전체','일일','주간','시간제','상시·성장'],state='readonly',width=12)
        combo.pack(side='left',padx=6);combo.bind('<<ComboboxSelected>>',lambda e:self.render(self.last_snapshot,force=True))
        ttk.Label(bar,text='기준일').pack(side='left',padx=(12,0))
        today=game_day(now_kst());self.date=tk.StringVar(win,value=self.day or today.isoformat())
        date=ttk.Combobox(bar,textvariable=self.date,values=[(today-timedelta(days=n)).isoformat() for n in range(8)],state='readonly',width=12)
        date.pack(side='left',padx=6);date.bind('<<ComboboxSelected>>',self.change_day)
        ttk.Button(bar,text='새로고침',command=self.refresh).pack(side='left',padx=6)
        self.summary=tk.StringVar(win,value='기존 실행 기록을 불러오는 중…')
        ttk.Label(win,textvariable=self.summary,padding=(10,0,10,8)).pack(fill='x')
        body=ttk.Frame(win,padding=(10,0));body.pack(fill='both',expand=True)
        columns=('group','name','status','recent','completed','next')
        self.tree=ttk.Treeview(body,columns=columns,show='headings',selectmode='browse')
        from owner_schedule_image import configure_pc_table
        configure_pc_table(self.tree)
        scroll=ttk.Scrollbar(body,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.detail)
        self.detail_text=tk.StringVar(win,value='항목을 선택하면 진행 근거·게임 일정·보류 이유를 볼 수 있습니다.')
        ttk.Label(win,textvariable=self.detail_text,wraplength=1120,padding=10,justify='left').pack(fill='x')
        actions=ttk.Frame(win,padding=(10,0,10,8));actions.pack(fill='x')
        ttk.Button(actions,text='게임에서 완료 확인',command=lambda:self.manual('manual')).pack(side='left')
        ttk.Button(actions,text='사용자 확인 취소',command=lambda:self.manual('unmark')).pack(side='left',padx=8)
        ttk.Button(actions,text='요일·시간 설정',command=self.time_settings).pack(side='left',padx=4)
        ttk.Label(actions,text='완료 확인은 기록만 바꿉니다. 게임 조작·자동 실행 설정은 바뀌지 않습니다.').pack(side='left',padx=8)
        ttk.Label(win,text='일일 기록은 05시, 주간 기록은 수요일 05시 기준입니다. 처리 종료만으로 보상 수령을 확정하지 않습니다.\n확인 시각은 실제 완료 시각과 다를 수 있습니다. 기존 PC 로그는 캐릭터 일치 미검증이며, 직접 플레이한 기록은 누락될 수 있습니다.',padding=(10,0,10,10),justify='left').pack(fill='x')
        self.last_render=None
        if self.last_snapshot:self.render(self.last_snapshot,force=True)

    def refresh(self):
        session=self.gui.session.snapshot()
        self.collector.request(session.get('status','stopped'),self.day,session.get('current_task',''));self.last_render=None

    def change_day(self,event=None):self.day=self.date.get();self.refresh()

    def render(self,snapshot,force=False):
        if snapshot is None or self.dialog is None:return
        rows=[r for r in snapshot['rows'] if self.group.get()=='전체' or r['group']==self.group.get()]
        signature=repr((rows,snapshot.get('status'),snapshot.get('issue'),snapshot.get('dropped'),snapshot['day']))
        if not force and signature==self.last_render:return
        self.last_render=signature
        from owner_schedule_image import fill_pc_table
        fill_pc_table(self.tree,snapshot,self.group.get())
        done=sum(r['verified'] for r in rows)
        label={'running':'실행 중','paused':'일시정지','stopped':'중지','error':'오류'}.get(snapshot['status'],snapshot['status'])
        text=f"{snapshot['identity']} · {snapshot['day']} · {label} · 완료 확인 {done}/{len(rows)}"
        if snapshot.get('issue'):text+='\n'+snapshot['issue']
        if snapshot.get('dropped'):text+=f" · 수집 누락 {snapshot['dropped']}건"
        self.summary.set(text);self.detail()

    def detail(self,event=None):
        selected=self.tree.selection()
        if not selected or not self.last_snapshot:return
        row=next((r for r in self.last_snapshot['rows'] if r['id']==selected[0]),None)
        if not row:return
        text=f"{row['name']} · {row['status']}\n근거: {row['note']} ({row['source'] or '수집 기록 없음'})"
        if row['calendar']:text+='\n게임 일정: '+row['calendar']
        if row['unit_at']!='—':text+=' · 최근 수련 회차 종료 '+row['unit_at']
        self.detail_text.set(text)

    def manual(self,kind):
        selected=self.tree.selection()
        if not selected:return
        when=now_kst()
        if self.day and self.day!=game_day(when).isoformat():
            self.detail_text.set('완료 확인은 현재 게임일에서 기록해 주세요. 과거 실제 완료 시각은 추정하지 않습니다.');return
        self.collector.enqueue((kind,selected[0],when));self.last_render=None

    def messages(self,group='전체'):
        # Remote queries always mean today's game-day, independent of the
        # date the PC viewer is browsing. The worker refreshes this projection.
        snapshot=self.collector.snapshot(today=True)
        if not snapshot:return [self.collector.issue or '스케줄 기록을 불러오는 중입니다. 잠시 후 다시 조회해 주세요.']
        return telegram_pages(snapshot,group)

    def time_settings(self):
        from owner_schedule_settings import show
        show(self.gui.root,self.gui.project.root)

    def hide(self):
        window=self.dialog;self.dialog=None;self.last_render=None
        if window is not None:window.destroy()

    def close(self):
        if self.closed:return
        self.closed=True
        if self.timer:
            try:self.gui.root.after_cancel(self.timer)
            except tk.TclError:pass
        self.collector.close()


def install(gui):
    if getattr(gui,'_owner_schedule',None) is None:gui._owner_schedule=SchedulePanel(gui)
