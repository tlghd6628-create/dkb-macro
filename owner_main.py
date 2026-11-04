"""One visible choice for the next run, beside the ordinary Start controls."""
import copy
import time
import tkinter as tk
from tkinter import ttk

MODES=(('main_quest','메인퀘스트'),('sub_quest','서사퀘스트'),('auto_mode','제자리 사냥'))


def choose(gui,mode):
    if mode not in dict(MODES):return False
    state=gui.session.snapshot()
    if state['status'] in ('running','paused') or state['worker_alive']:return False
    if getattr(getattr(gui,'input_preparation',None),'busy',lambda:False)():return False
    return gui.set_execution_mode(mode)


class MainPanel:
    def __init__(self,gui):
        self.gui=gui;self.closed=False;self.timer=None;self.view=None
        self.frame=ttk.Frame(gui.root,padding=(4,0))
        self.mode=tk.StringVar(gui.root,value=gui.load_settings_model().mode)
        self.hint=tk.StringVar(gui.root)
        self.buttons=[]
        for index,(value,label) in enumerate(MODES):
            button=ttk.Radiobutton(self.frame,text=label,variable=self.mode,value=value,command=self.selected)
            button.grid(row=0,column=index,padx=(0,8),sticky='w');self.buttons.append(button)
        self.hint_label=ttk.Label(self.frame,textvariable=self.hint,font=('Malgun Gothic',8))
        self.hint_label.grid(row=2,column=0,columnspan=3,sticky='w',pady=(2,0))
        self._hunt_identity=None;self._hunt_identity_checked=-1e30
        self.hunt_slot=tk.StringVar(gui.root,value='')
        self.hunt_source=tk.StringVar(gui.root,value='fixed')
        self.hunt_row=ttk.Frame(self.frame)
        self.hunt_row.grid(row=1,column=0,columnspan=3,sticky='w')
        self.hunt_label=ttk.Label(self.hunt_row,text='사냥 위치',font=('Malgun Gothic',8))
        self.hunt_label.pack(side='left',padx=(0,8))
        self.hunt_fixed=ttk.Radiobutton(self.hunt_row,text='고정',variable=self.hunt_source,value='fixed',command=self.save_hunt_slot)
        self.hunt_fixed.pack(side='left')
        self.hunt_combo=ttk.Combobox(self.hunt_row,textvariable=self.hunt_slot,values=('1','2','3','4'),width=3,state='readonly')
        self.hunt_combo.pack(side='left',padx=(2,12))
        self.hunt_combo.bind('<<ComboboxSelected>>',self.save_hunt_slot)
        self.hunt_power=ttk.Radiobutton(self.hunt_row,text='전투력별',variable=self.hunt_source,value='power',command=self.save_hunt_slot)
        self.hunt_power.pack(side='left')
        self.originals_hidden=[]
        gui.root.bind('<Destroy>',lambda event:self.close() if event.widget is gui.root else None,add='+')
        self.refresh()

    def selected(self):
        if not choose(self.gui,self.mode.get()):
            self.mode.set(self.gui.load_settings_model().mode)
        self.refresh(schedule=False)

    def layout(self):
        gui=self.gui;view=getattr(gui,'visual_view',None)
        if view is not None:
            if view.layout is not getattr(view,'_owner_main_layout',None):
                layout=copy.deepcopy(view.layout)
                layout['height']+=70
                for rect in layout['components'].values():
                    if rect['y']>=40:rect['y']+=70
                view._owner_main_layout=layout;view.layout=layout
                view.predicates['execution_mode']=lambda:False
                view.apply()
            if not view.hud:
                self.frame.place(x=10,y=43,width=max(1,gui.root.winfo_width()-20),height=67)
                self.frame.lift()
            else:self.frame.place_forget()
        # The former update slot now opens the game-only current-screen viewer.
        controls=gui._owner_controls
        for button in {gui.update_button,getattr(view,'originals',{}).get('update',gui.update_button)}:
            button.configure(text='현재 화면',command=controls.show_preview,state='normal')
        link=getattr(controls,'screen_link',None)
        if link is not None and link is not gui.update_button and link.winfo_exists():
            link.place_forget();link.pack_forget()
            if link not in self.originals_hidden:self.originals_hidden.append(link)
        for widget in self.originals_hidden:
            if widget.winfo_exists():widget.place_forget()
        controls.screen_link=gui.update_button
        controls.telegram.position()

    def refresh(self,schedule=True):
        if self.closed or self.gui.closed.is_set():return
        if time.monotonic()-self._hunt_identity_checked>=1.0:
            self._hunt_identity_checked=time.monotonic();self.sync_hunt_slot()
        self.layout()
        state=self.gui.session.snapshot()
        saved=self.gui.load_settings_model().mode
        if self.mode.get()!=saved:self.mode.set(saved)
        busy=state['status'] in ('running','paused') or state['worker_alive'] or getattr(getattr(self.gui,'input_preparation',None),'busy',lambda:False)()
        for button in self.buttons:button.configure(state='disabled' if busy else 'normal')
        # The hunt spot applies in every game mode, and a paused run reads it again on resume.
        locked=state['status']=='running' or (busy and state['status']!='paused')
        self.hunt_fixed.configure(state='disabled' if locked else 'normal')
        self.hunt_power.configure(state='disabled' if locked else 'normal')
        self.hunt_combo.configure(state='readonly' if not locked and self.hunt_source.get()=='fixed' else 'disabled')
        text=('실행 중 · 모드를 바꾸려면 먼저 F3으로 중지하세요.' if state['status']=='running' else
              '일시정지 중 · F1을 누르면 하던 작업을 재개합니다.' if state['status']=='paused' else
              '중지 처리 중입니다.' if busy else '원하는 모드 선택 후 F1 시작 · 자동 저장됩니다.')
        stage=getattr(self.gui,'_owner_stage_snapshot',None)
        if stage and state['status'] in ('running','paused'):
            text=('일시정지 · ' if state['status']=='paused' else '')+'현재 위치: '+stage['location_label']+' · '+stage['phase']
        recognition=getattr(self.gui,'_owner_ocr_readiness',None)
        if recognition is not None and not recognition.done.is_set():
            text='인식 준비 중 · 게임 입력 대기 · F3 중지 가능'
        elif recognition is not None and recognition.error:
            text='인식 준비 실패 · 실행 기록 확인'
        if self.hint.get()!=text:self.hint.set(text)
        if schedule:self.timer=self.gui.root.after(250,self.refresh)

    def sync_hunt_slot(self):
        from owner_hunt_rules_candidate import ConfiguredHuntRules
        try:
            rules=ConfiguredHuntRules(self.gui.project.root);value=str(rules.stationary() or '')
            if self._hunt_identity!=rules.identity or self.hunt_slot.get()!=value:self.hunt_slot.set(value)
            if self.hunt_source.get()!=rules.source():self.hunt_source.set(rules.source())
            self._hunt_identity=rules.identity;return True
        except (ValueError,OSError):
            self._hunt_identity=None;self.hunt_slot.set('');return False

    def save_hunt_slot(self,event=None):
        from owner_hunt_rules_candidate import ConfiguredHuntRules
        try:
            rules=ConfiguredHuntRules(self.gui.project.root)
            if self._hunt_identity!=rules.identity:
                self.sync_hunt_slot();raise ValueError('서버 또는 캐릭터가 바뀌었습니다. 위치를 다시 선택해 주세요')
            power=self.hunt_source.get()=='power';slot=self.hunt_slot.get()
            stored=rules.stored()
            if power and not stored:
                self.hunt_source.set('fixed')
                raise ValueError('전투력 기준이 없습니다. 세부설정 사냥터에서 먼저 입력해 주세요')
            if not power and not slot:raise ValueError('고정 사냥터 번호를 선택해 주세요')
            # stored(), not read(): read() is empty for a source that is off, and that wiped the rules.
            rules.store(stored,int(slot) if slot else None,enabled=power,fixed_enabled=not power)
        except (ValueError,OSError) as error:
            self.gui.logger.warning('사냥 위치 저장 실패 · %s',error)

    def close(self):
        self.closed=True
        if self.timer is not None:
            try:self.gui.root.after_cancel(self.timer)
            except tk.TclError:pass


def install(gui):
    if not getattr(gui,'_owner_quest_schema',False):
        model=gui.load_settings_model()
        if model.mode not in ('main_quest','sub_quest','auto_mode'):model.save('main_quest',model.values)
        schema=copy.deepcopy(model.schema)
        from owner_clan_field_help import add_switch
        add_switch(schema)
        from owner_raid_preset import add_fields as add_raid_preset,install as install_raid_preset
        add_raid_preset(schema);install_raid_preset()
        from owner_raid_tickets import add_fields as add_raid_count
        add_raid_count(schema)
        from owner_disassembly_settings import add_fields as add_disassembly_fields
        add_disassembly_fields(schema)
        schema['modes']=[m for m in schema['modes'] if m['id'] in ('main_quest','sub_quest','auto_mode')]
        for mode in schema['modes']:
            if mode['id']=='sub_quest':mode['label']='서사퀘 진행'
            if mode['id']=='auto_mode':mode['label']='제자리 사냥'
        schema['default_mode']='main_quest'
        schema.setdefault('mode_aliases',{}).pop('auto_mode',None)
        schema['mode_aliases'].update(custom_mode='main_quest')
        for alias,target in tuple(schema['mode_aliases'].items()):
            if target not in ('main_quest','sub_quest','auto_mode'):schema['mode_aliases'][alias]='main_quest'
        def update(node):
            if isinstance(node,dict):
                if 'checkbox_modes' in node:node['checkbox_modes']=['main_quest','sub_quest','auto_mode']
                condition=node.get('visible_if') or {}
                if 'mode' in condition:
                    condition['mode']=(['main_quest','sub_quest','auto_mode'] if 'auto_mode' in condition['mode'] else [m for m in condition['mode'] if m in ('main_quest','sub_quest')])
                for value in node.values():update(value)
            elif isinstance(node,list):
                for value in node:update(value)
        update(schema);gui._live_schema=schema;gui._settings_schema_revision=getattr(gui,'_settings_schema_revision',0)+1
        gui._owner_quest_schema=True
        title=gui.root.title()
        if ' · r20' in title:title=title.replace(' · r20',' · r21')
        elif ' · r21' not in title:title+=' · r21'
        gui.root.title(title)
    if getattr(gui,'_owner_main',None) is None:gui._owner_main=MainPanel(gui)
    else:gui._owner_main.refresh(schedule=False)
    # Colours only: a failure here must not stop the installs that follow this one.
    try:
        from owner_main_theme import install as paint
        paint(gui)
    except Exception:
        import logging
        logging.getLogger('project_gui.DKB').exception('메인 창 색상 적용 실패 · 기능은 그대로 사용 가능')
