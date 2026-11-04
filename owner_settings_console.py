"""One categorized settings console; native IDs and runtime consumers stay."""
import tkinter as tk
from tkinter import ttk,messagebox
from gui_settings import fields,parse_value

UNAVAILABLE={'auto_rewards.training_log.enabled':'사용 불가 · 이미지 수집 필요'}

def category(key):
 # Removed from the console only: the saved value and its consumer stay as they are.
 if key.startswith('common.daily_restart.') or key in ('common.potion_and_favorite.source','common.potion_and_favorite.slot'):return None
 if key.startswith(('common.skill_preset.','auto_schedule.field_boss.skill_preset.','auto_schedule.boss_raid.skill_preset.')):return '기본 설정'
 if key.startswith(('auto_schedule.clan_boss_request.','auto_rewards.clan_help.','auto_growth.clan_cooperative_training.')):return '문파'
 if key in ('auto_rewards.inventory_use.enabled','auto_rewards.seal_release.enabled'):return '아이템 사용'
 if key=='auto_rewards.blessing.enabled':return '가호'
 if key.startswith('auto_growth.spirit_training.') or key=='inner_path.enabled':return '수련'
 if key.startswith(('auto_schedule.','auto_challenge.')):return '비경·보스'
 if key.startswith(('auto_rewards.','auto_register.')):return '보상·정리'
 return '기본 설정'

def coupon_status(root):
 """Shown only: every enabled code with whether the native receipt says it is done.
 Same record and PC scope the coupon step itself reads; nothing is written."""
 import json
 from pathlib import Path
 from owner_startup_receipts import terminal_coupons
 path=Path(root)/'settings/manager_identity.json'
 identity=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
 config=json.loads((Path(root)/'profiles/DKB/config/coupons.json').read_text(encoding='utf-8-sig'))
 _,complete=terminal_coupons(root,identity)
 return [(row['code'],row['code'] in complete) for row in config.get('coupons',[]) if row.get('enabled',True) and row.get('code')]

def option_editable(model,item):
 """TEST runs with the switch off, so its options stay open: pick the raid stage, then TEST."""
 from owner_reward_action_test import TARGETS
 from owner_challenge_test import TARGETS as CHALLENGES
 parent=item.get('enabled_if')
 return model.editable(dict(item,enabled_if=None) if parent in TARGETS or parent in CHALLENGES else item)

class NativeFields:
 def __init__(self,gui):
  self.gui=gui;self.model=gui.load_settings_model();self.baseline=dict(self.model.values);self.vars={};self.controls=[]
  if self.model.load_error:raise ValueError('설정 파일을 읽지 못했습니다.')
 def build(self,parent,name,*,compact=False):
  from owner_settings_theme import scroll_area,bind_wheel,section_box,sections,display_label
  compact=compact or name=='사냥터'
  frame=ttk.Frame(parent);frame.pack(fill='x' if compact else 'both',expand=not compact)
  canvas=None;body=frame
  if not compact:canvas,body=scroll_area(frame)
  group_visible={f['id']:self.model.visible(t) and self.model.visible(g) for t in self.model.schema['tabs'] for g in t['groups'] for f in g['fields']}
  items=[item for item in fields(self.model.schema) if category(item['id'])==name and group_visible[item['id']] and item.get('visible',True) is not False]
  # A long page reads better in two columns; short ones keep one wide column.
  wide=len(items)>14 and name!='보상·정리'
  columns=[body]
  if wide:
   columns=[ttk.Frame(body),ttk.Frame(body)]
   columns[0].grid(row=1,column=0,sticky='new',padx=(0,28));columns[1].grid(row=1,column=1,sticky='new')
   body.columnconfigure(0,weight=1,uniform='page');body.columnconfigure(1,weight=1,uniform='page')
  filled=[0,0]
  if name=='기본 설정':self._membership(section_box(columns[0],'멤버십'))
  for title,rows in sections(name,items):
   slot=filled.index(min(filled)) if wide else 0
   filled[slot]+=len(rows)+2
   box=section_box(columns[slot],title)
   self._section(box,rows,1 if wide else 3,display_label)
   if title=='쿠폰':self._coupons(box)
  self.refresh_controls()
  if canvas is not None:bind_wheel(canvas,body)
  return frame
 def _membership(self,box):
  from owner_membership import paid
  try:self.member_baseline=paid(self.gui.project.root)
  except (OSError,ValueError,AttributeError):
   ttk.Label(box,text='멤버십 설정을 읽지 못했습니다',style='DkbHint.TLabel').pack(anchor='w');return
  self.member=tk.BooleanVar(box,value=self.member_baseline)
  ttk.Checkbutton(box,text='멤버십 결제',variable=self.member).pack(anchor='w',pady=2)
 def _coupons(self,box):
  try:rows=coupon_status(self.gui.project.root)
  except (OSError,ValueError,TypeError,KeyError,AttributeError):
   ttk.Label(box,text='쿠폰 사용 기록을 읽지 못했습니다',style='DkbHint.TLabel').pack(anchor='w',padx=24,pady=(4,0));return
  grid=ttk.Frame(box);grid.pack(fill='x',padx=(24,0),pady=(6,0))
  for column in range(3):grid.columnconfigure(column,weight=1,uniform='coupons')
  for index,(code,used) in enumerate(rows):
   cell=ttk.Frame(grid);cell.grid(row=index//3,column=index%3,sticky='w',pady=2)
   ttk.Label(cell,text='O' if used else 'X',style='DkbYes.TLabel' if used else 'DkbNo.TLabel',width=2).pack(side='left')
   ttk.Label(cell,text=code).pack(side='left')
 def _section(self,box,rows,per_row,display_label):
  from owner_settings_theme import INLINE_CHOICES
  from owner_reward_action_test import TARGETS,PATHS
  from owner_challenge_test import TARGETS as CHALLENGES
  checks=None;count=0;line=None
  for index,item in enumerate(rows):
   key=item['id']
   value=self.model.values[key];var=(tk.BooleanVar(box,value=value) if item['type']=='checkbox' else tk.StringVar(box,value=value))
   self.vars[key]=var
   following=rows[index+1]['type'] if index+1<len(rows) else 'checkbox'
   if key in TARGETS or key in CHALLENGES:
    line=ttk.Frame(box);line.pack(fill='x',pady=3)
    widget=ttk.Checkbutton(line,text=display_label(item),variable=var,width=max(23,round(len(display_label(item))*1.7)));widget.pack(side='left')
    result=tk.StringVar(line)
    test=ttk.Button(line,text='TEST',width=6,command=lambda key=key,result=result:self.test_request(key,result));test.pack(side='left',padx=(8,12))
    if key in UNAVAILABLE:test.configure(state='disabled');result.set(UNAVAILABLE[key])
    elif not self.model.supported(item) or (key not in CHALLENGES and PATHS[key] is None):test.configure(state='disabled');result.set('실행 연결 없음')
    ttk.Label(line,textvariable=result,style='DkbHint.TLabel').pack(side='left')
    checks=None;line=None
   elif index+1<len(rows) and rows[index+1]['id'] in INLINE_CHOICES:
    line=ttk.Frame(box);line.pack(fill='x',pady=3)
    widget=ttk.Checkbutton(line,text=display_label(item),variable=var,width=20);widget.pack(side='left')
    checks=None
   elif key in INLINE_CHOICES and line is not None:
    widget=ttk.Combobox(line,textvariable=var,values=item['choices'],state='readonly',width=8);widget.pack(side='left')
    line=None
   elif item['type']=='checkbox':
    # A switch that owns the next value keeps its own line above that value.
    if following!='checkbox' or checks is None or count>=per_row:
     checks=ttk.Frame(box);checks.pack(fill='x');count=0
     for column in range(per_row):checks.columnconfigure(column,weight=1,uniform='checks')
    widget=ttk.Checkbutton(checks,text=display_label(item),variable=var);widget.grid(row=0,column=count,sticky='w',pady=2)
    count+=1
    if following!='checkbox':checks=None
   else:
    checks=None
    row=ttk.Frame(box);row.pack(fill='x',pady=3)
    # A value that follows a switch sits under it; a plain value stays aligned.
    under=any(earlier['type']=='checkbox' for earlier in rows[:index])
    ttk.Label(row,text=display_label(item),width=26).pack(side='left',padx=(24 if under else 0,8))
    if item['type'] in ('combo','radio'):widget=ttk.Combobox(row,textvariable=var,values=item['choices'],state='readonly',width=18)
    else:widget=ttk.Spinbox(row,textvariable=var,from_=item.get('min',0),to=item.get('max',999999),width=9)
    widget.pack(side='left')
   self.controls.append((item,widget))
   var.trace_add('write',lambda *_:self.refresh_controls())
 def refresh_controls(self):
  original=self.model.values;temporary=dict(original)
  for key,var in self.vars.items():
   try:temporary[key]=parse_value(self.model.items[key],var.get())
   except (ValueError,TypeError,tk.TclError):pass
  self.model.values=temporary
  try:
   for item,widget in self.controls:
    widget.configure(state=('readonly' if item['type'] in ('combo','radio') else 'normal') if item['id'] not in UNAVAILABLE and option_editable(self.model,item) else 'disabled')
  finally:self.model.values=original
 def save(self):
  state=self.gui.session.snapshot()
  paused=state.get('status')=='paused'
  if state.get('status')=='running' or (state.get('worker_alive') and not paused):raise ValueError('일시정지(F2)나 중지 후 설정을 저장해 주세요.')
  latest=self.gui.load_settings_model();changes={}
  for key,var in self.vars.items():
   value=parse_value(self.model.items[key],var.get())
   if value!=self.baseline[key]:
    if latest.values[key]!=self.baseline[key]:raise ValueError('다른 창에서 설정이 변경되었습니다. 다시 열어 주세요.')
    changes[key]=value
  if changes:
   latest.save(latest.mode,dict(latest.values,**changes));self.gui.settings_model=latest;self.gui.refresh_summary()
   if paused:
    from owner_timetable import live_settings
    live_settings(changes)
  self.model=latest;self.baseline=dict(latest.values)
  member=getattr(self,'member',None)
  if member is not None and member.get()!=self.member_baseline:
   from owner_membership import set_paid
   set_paid(self.gui.project.root,member.get());self.member_baseline=member.get()
   import logging
   logging.getLogger('project_gui.DKB').info('멤버십 기능 %s · 다음 시작에 적용','사용' if member.get() else '해제')
  return True

class SettingsConsole:
 def __init__(self,gui,callbacks):
  self.gui=gui;self.native=NativeFields(gui);self.callbacks=callbacks
  self.native.test_request=self.test_action
  self.window=tk.Toplevel(gui.root);self.window.title('세부설정');self.window.geometry('1040x720');self.window.minsize(960,640)
  # A half-built window would keep every later click on its lift branch.
  try:self.build()
  except BaseException:self.window.destroy();raise
 def build(self):
  gui=self.gui
  self.editors=[]
  from owner_hunt_rules_candidate import configured_identity
  identity=configured_identity(gui.project.root)
  from owner_settings_theme import prepare,restyle,follow,hide_inner_saves,tidy,hairline,NAV_GROUPS,SURFACE,MUTED,FONT
  prepare(gui.root);self.window.configure(background=SURFACE)
  layout=ttk.Frame(self.window,style='Dkb.TFrame');layout.pack(fill='both',expand=True)
  side=ttk.Frame(layout,style='DkbSide.TFrame');side.pack(side='left',fill='y')
  ttk.Label(side,text='세부설정',style='DkbBrand.TLabel').pack(anchor='w',padx=18,pady=(18,10))
  nav=ttk.Treeview(side,show='tree',selectmode='browse',height=20,style='DkbNav.Treeview');nav.column('#0',width=170,stretch=False);nav.pack(fill='y',expand=True,padx=(8,8),pady=(0,10))
  nav.tag_configure('group',foreground=MUTED,font=(FONT,9,'bold'))
  hairline(layout,width=1).pack(side='left',fill='y')
  main=ttk.Frame(layout,style='Dkb.TFrame');main.pack(side='left',fill='both',expand=True)
  heading=tk.StringVar(self.window)
  ttk.Label(main,textvariable=heading,style='DkbTitle.TLabel').pack(anchor='w',padx=26,pady=(18,12))
  footer=ttk.Frame(main,style='Dkb.TFrame');footer.pack(side='bottom',fill='x')
  hairline(footer,height=1).pack(fill='x')
  tabs=ttk.Notebook(main,style='OwnerDirect.TNotebook');tabs.pack(fill='both',expand=True,padx=26,pady=(0,10))
  links={}
  def link(label,outer,inner=None,page=None):links[label]=(outer,inner,page)
  for label in ('기본 설정','보상·정리','문파','성장','사냥터','상점','아이템 사용','스케줄','진단'):
   frame=ttk.Frame(tabs);tabs.add(frame,text=label)
   if label not in ('성장','스케줄'):link(label,frame)
   if label in ('기본 설정','보상·정리','문파'):self.native.build(frame,label)
   elif label=='스케줄':
    nested=ttk.Notebook(frame,style='OwnerDirect.TNotebook');nested.pack(fill='both',expand=True)
    for name in ('요일·시간','비경·보스','수련'):
     content=ttk.Frame(nested);nested.add(content,text=name)
     link(name,frame,nested,content)
     if name=='요일·시간':
      from owner_schedule_settings import ScheduleEditor
      self.schedule_editor=ScheduleEditor(content,gui.project.root)
     else:self.native.build(content,name)
   elif label=='성장':
    from owner_gear_settings_candidate import open_settings
    editor=open_settings(frame,gui.project.root,identity,gui=gui,embedded=True);self.editors.append(editor)
    from owner_settings_layout import GROWTH_SWITCHES
    editor.test_request=lambda section,result:self.test_action(GROWTH_SWITCHES[section],result)
    editor.tabs.configure(style='OwnerDirect.TNotebook')
    for page in editor.tabs.tabs():
     name=editor.tabs.tab(page,'text');link(name,frame,editor.tabs,page)
     if name=='가호':
      # Reuse the native setting and save path. Growth remains an independent switch.
      area=ttk.Frame(editor.tabs.nametowidget(page));area.grid(row=11,column=0,columnspan=8,sticky='ew',pady=(12,0))
      self.native.build(area,'가호',compact=True)
   elif label=='사냥터':
    self.native.build(frame,label)
    from owner_hunt_settings_candidate import HuntSettings
    hunt=HuntSettings(frame,gui.project.root,embedded=True);self.editors.append(hunt)
    # Keep the add button under the rows instead of at the far bottom.
    hunt.list.pack_configure(fill='x',expand=False)
   elif label=='상점':
    from owner_shop_settings_candidate import open_settings
    self.editors.append(open_settings(frame,gui.project.root,identity,embedded=True))
   elif label=='아이템 사용':
    self.native.build(frame,label,compact=True)
    from owner_starter_choice_candidate import open_settings
    self.editors.append(open_settings(frame,gui.project.root,identity,embedded=True))
   elif label=='진단':
    from owner_telemetry import show
    show(gui,parent=frame,embedded=True)
  destinations={};names={}
  def place(group,labels):
   nav.insert('','end',text=group,tags=('group',))
   for label in labels:
    key=nav.insert('','end',text='   '+label);destinations[key]=links.pop(label);names[key]=label
  for group,labels in NAV_GROUPS:place(group,[label for label in labels if label in links])
  # A page added elsewhere must stay reachable even without a menu group here.
  if links:place('기타',list(links))
  self.notice=tk.StringVar(self.window)
  actions=ttk.Frame(footer,style='Dkb.TFrame');actions.pack(fill='x',padx=26,pady=12)
  ttk.Label(actions,textvariable=self.notice,style='DkbNotice.TLabel').pack(side='left')
  save=ttk.Button(actions,text='저장',command=self.save,style='DkbPrimary.TButton');save.pack(side='right')
  hide_inner_saves(tabs);tidy(tabs);restyle(tabs);follow(self.window)
  def select(event=None):
   selected=nav.selection()
   if not selected:return
   if selected[0] not in destinations:
    # A group title only leads to its first page.
    following=nav.next(selected[0])
    if following:nav.selection_set(following)
    return
   outer,inner,page=destinations[selected[0]];tabs.select(outer)
   if inner is not None:inner.select(page)
   heading.set(names[selected[0]])
   # Nothing on the diagnostic page is part of this save.
   if names[selected[0]]=='진단':save.pack_forget()
   elif not save.winfo_manager():save.pack(side='right')
  nav.bind('<<TreeviewSelect>>',select)
  first=next(key for key in nav.get_children() if key in destinations)
  nav.selection_set(first);select()
  self.navigation=nav;self.destinations=destinations
 def save(self):
  try:
   self.schedule_editor.validate()
   for editor in self.editors:
    if editor.save() is not True:
     self.notice.set('설정을 확인해 주세요 · 일부 항목 저장 안 됨');return False
   self.native.save();self.schedule_editor.save(raise_errors=True)
   self.notice.set('저장 완료');return True
  except (OSError,ValueError) as exc:self.notice.set(str(exc));return False
 def open_editor(self,key):
  if self.save():self.window.destroy();self.callbacks[key]()
 def test_action(self,key,result):
  from owner_reward_action_test import PATHS
  from owner_challenge_test import TARGETS as CHALLENGES,start
  if key in UNAVAILABLE:result.set(UNAVAILABLE[key]);return
  if key in CHALLENGES:
   if not self.native.model.supported(self.native.model.items[key]):result.set('실행 연결 없음');return
   if not self.save():result.set(self.notice.get());return
   start(self.gui,key,result);return
  if not self.native.model.supported(self.native.model.items[key]) or PATHS.get(key) is None:result.set('실행 연결 없음');return
  if not self.save():result.set(self.notice.get());return
  from owner_reward_action_test import controller
  controller(self.gui).start(key,result,self.window)
