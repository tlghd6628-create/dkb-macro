"""One visible choice for the next run, beside the ordinary Start controls.

The main window is the native compact layout; this module only decides where
the native widgets sit and draws one status card over the free band. Every
native widget keeps its callback, Tcl variable and saved file. Hidden widgets
are hidden with the layout's own ``visible`` flag, nothing is destroyed.
"""
import copy
import time
import tkinter as tk
from tkinter import ttk

MODES=(('main_quest','메인퀘스트'),('sub_quest','서사퀘스트'),('auto_mode','제자리 사냥'))
STATE_TEXT={'running':'실행중','paused':'일시정지','stopped':'정지','error':'오류'}

# Picture only. Rectangles are for the authored 477-wide window; a layout of
# another width keeps the old +70 band instead of these positions.
WIDTH=477;HEIGHT=412
PANEL=dict(x=10,y=58,width=457,height=100)
PLACES={
 'start':(10,10,70,30),'pause':(84,10,92,30),'stop':(180,10,70,30),'update':(389,12,78,26),
 'accent':(10,50,457,2),
 'game_connect':(10,168,96,28),'game_refresh':(110,168,80,28),'game_hint':(196,173,110,19),'input_prepare':(310,168,157,28),
 'log':(10,204,443,124),'log_scroll':(453,204,14,124),
 'log_send':(10,338,80,28),'log_note':(96,343,150,19),'launcher_start':(250,343,120,19),'details':(387,338,80,28),
 'identity.server_name.label':(10,380,30,19),'identity.server_name.entry':(44,379,96,22),
 'identity.character_name.label':(150,380,42,19),'identity.character_name.entry':(196,379,96,22),
 'identity.save':(302,376,52,27),
}
# Removed from the picture; the widgets, their variables and saved values stay.
HIDDEN=('status','identity.pc_alias.label','identity.pc_alias.entry',
        'alignment.label','alignment.tl','alignment.bl','alignment.tr','alignment.br','alignment.manager',
        'mode_fixed','execution_mode')


def choose(gui,mode):
    if mode not in dict(MODES):return False
    state=gui.session.snapshot()
    if state['status'] in ('running','paused') or state['worker_alive']:return False
    if getattr(getattr(gui,'input_preparation',None),'busy',lambda:False)():return False
    return gui.set_execution_mode(mode)


def arranged(authored,hud_on):
    """A copy of the authored layout with this module's positions applied."""
    layout=copy.deepcopy(authored)
    components=layout['components']
    if layout['width']!=WIDTH:
        # Unknown width: keep the former behaviour, a band above the native rows.
        layout['height']+=70
        for rect in components.values():
            if rect['y']>=40:rect['y']+=70
        return layout
    for key,(x,y,width,height) in PLACES.items():
        if key in components:components[key].update(x=x,y=y,width=width,height=height,visible=True)
    for key in HIDDEN:
        if key in components:components[key]['visible']=False
    for key in ('hud','hud_place'):
        # The HUD switch stays reachable only while a saved HUD state is on.
        if key in components:components[key]['visible']=bool(hud_on)
    layout['height']=HEIGHT
    return layout


class MainPanel:
    def __init__(self,gui):
        self.gui=gui;self.closed=False;self.timer=None;self.view=None
        from owner_settings_theme import prepare,SURFACE,BORDER,FONT
        prepare(gui.root)
        self.frame=tk.Frame(gui.root,background=SURFACE,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER,borderwidth=0)
        self.frame._dkb_card=True
        body=ttk.Frame(self.frame,style='DkbCard.TFrame');body.pack(fill='both',expand=True,padx=12,pady=(8,6))
        # Row 1: run state, current activity. The schedule button lands top-right.
        top=ttk.Frame(body,style='DkbCard.TFrame');top.pack(fill='x')
        self.state_text=tk.StringVar(gui.root,value='정지')
        self.pill=tk.Label(top,textvariable=self.state_text,font=(FONT,9,'bold'),padx=10,pady=1,background='#CBD0D8',foreground='#3B4252')
        self.pill.pack(side='left')
        self.hint=tk.StringVar(gui.root)
        self.hint_label=ttk.Label(top,textvariable=self.hint,style='DkbCard.TLabel',font=(FONT,9),wraplength=250)
        self.hint_label.pack(side='left',padx=(10,0))
        # Row 2: the mode for the next run.
        modes=ttk.Frame(body,style='DkbCard.TFrame');modes.pack(fill='x',pady=(9,0))
        ttk.Label(modes,text='모드',style='DkbCardMuted.TLabel',width=8).pack(side='left')
        self.mode=tk.StringVar(gui.root,value=gui.load_settings_model().mode)
        self.buttons=[]
        for value,label in MODES:
            button=ttk.Radiobutton(modes,text=label,variable=self.mode,value=value,command=self.selected,style='DkbCard.TRadiobutton')
            button.pack(side='left',padx=(0,14));self.buttons.append(button)
        # Row 3: hunt spot, game connection.
        self._hunt_identity=None;self._hunt_identity_checked=-1e30
        self.hunt_slot=tk.StringVar(gui.root,value='')
        self.hunt_source=tk.StringVar(gui.root,value='fixed')
        self.hunt_row=ttk.Frame(body,style='DkbCard.TFrame')
        self.hunt_row.pack(fill='x',pady=(3,0))
        self.hunt_label=ttk.Label(self.hunt_row,text='사냥 위치',style='DkbCardMuted.TLabel',width=8)
        self.hunt_label.pack(side='left')
        self.hunt_fixed=ttk.Radiobutton(self.hunt_row,text='고정',variable=self.hunt_source,value='fixed',command=self.save_hunt_slot,style='DkbCard.TRadiobutton')
        self.hunt_fixed.pack(side='left')
        self.hunt_combo=ttk.Combobox(self.hunt_row,textvariable=self.hunt_slot,values=('1','2','3','4'),width=3,state='readonly',style='Dkb.TCombobox')
        self.hunt_combo.pack(side='left',padx=(2,14))
        self.hunt_combo.bind('<<ComboboxSelected>>',self.save_hunt_slot)
        self.hunt_power=ttk.Radiobutton(self.hunt_row,text='전투력별',variable=self.hunt_source,value='power',command=self.save_hunt_slot,style='DkbCard.TRadiobutton')
        self.hunt_power.pack(side='left')
        self.game_text=tk.StringVar(gui.root,value='')
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
                authored=getattr(view,'_owner_authored_layout',None)
                if authored is None:authored=view._owner_authored_layout=copy.deepcopy(view.layout)
                layout=arranged(authored,view.hud)
                view._owner_main_layout=layout;view.layout=layout
                view.predicates['execution_mode']=lambda:False
                for key in HIDDEN:
                    if key in view.widgets:view.predicates[key]=lambda:False
                view.apply()
            if not view.hud:
                self.frame.place(**PANEL)
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

    def paint_state(self,state):
        """Run-state pill and connection text, from the values the host already keeps."""
        from owner_main_theme import STATE_COLORS
        key=getattr(self.gui,'_painted_state',None) or ('paused' if state['status']=='paused' else 'running' if state['status']=='running' else 'stopped')
        colors=STATE_COLORS.get(key,STATE_COLORS['stopped'])
        var=getattr(self.gui,'state',None)
        text=var.get() if var is not None else STATE_TEXT.get(state['status'],state['status'])
        if self.state_text.get()!=text:self.state_text.set(text)
        foreground='#FFFFFF' if key!='stopped' else colors['foreground']
        if self.pill.cget('background')!=colors['accent']:self.pill.configure(background=colors['accent'],foreground=foreground)
        game=getattr(self.gui,'game_state',None)
        value=game.get() if game is not None else ''
        game_text='게임 '+('연결' if value=='연결' else '미연결')
        if self.game_text.get()!=game_text:self.game_text.set(game_text)

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
        text=('실행 중 · 모드 변경은 F3 중지 후' if state['status']=='running' else
              '일시정지 · F1 계속' if state['status']=='paused' else
              '중지 처리 중' if busy else '대기 · 모드 선택 후 F1 시작')
        if state['status']=='running' and state.get('current_task'):text=str(state['current_task'])
        stage=getattr(self.gui,'_owner_stage_snapshot',None)
        if stage and state['status'] in ('running','paused'):
            text=('일시정지 · ' if state['status']=='paused' else '')+stage['location_label']+' · '+stage['phase']
        recognition=getattr(self.gui,'_owner_ocr_readiness',None)
        if recognition is not None and not recognition.done.is_set():
            text='인식 준비 중 · F3 중지 가능'
        elif recognition is not None and recognition.error:
            text='인식 준비 실패 · 실행 기록 확인'
        if self.hint.get()!=text:self.hint.set(text)
        self.paint_state(state)
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


OLD_NAMES=(('가호 보상','가호 일괄 획득'),)

def rename_in_logs():
    """The original modules are compiled and still name the blessing bulk claim 가호 보상. The log says what the owner calls it."""
    import logging
    old=logging.getLogRecordFactory()
    if getattr(old,'_owner_rename',False):return
    def swap(value):
        if not isinstance(value,str):return value
        for before,after in OLD_NAMES:value=value.replace(before,after)
        return value
    def factory(*args,**kwargs):
        record=old(*args,**kwargs)
        record.msg=swap(record.msg)
        if isinstance(record.args,tuple):record.args=tuple(swap(value) for value in record.args)
        if isinstance(getattr(record,'gui_message',None),str):record.gui_message=swap(record.gui_message)
        return record
    factory._owner_rename=True
    logging.setLogRecordFactory(factory)

def install(gui):
    import owner_hd,owner_text
    owner_hd.install()
    owner_text.set_root(gui.project.root)
    rename_in_logs()
    if hasattr(gui,'root'):gui.root.after(4000,lambda:owner_hd.keep_size(gui))
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
        from owner_falling_guard import add_fields as add_falling_limit,install as install_falling_guard
        add_falling_limit(schema);install_falling_guard()
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
