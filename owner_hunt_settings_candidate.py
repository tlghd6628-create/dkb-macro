"""Standalone editor candidate; requires integration with DKB detail settings."""
import tkinter as tk
from tkinter import ttk,messagebox
from owner_hunt_rules_candidate import ConfiguredHuntRules

class HuntSettings:
 def __init__(self,parent,root,*,embedded=False):
  self.rules=ConfiguredHuntRules(root);self.embedded=embedded;self.rows=[]
  self.window=ttk.Frame(parent) if embedded else tk.Toplevel(parent)
  if embedded:self.window.pack(fill='both',expand=True)
  else:self.window.title('사냥터 지정')
  self.body=ttk.Frame(self.window,padding=12);self.body.pack(fill='both',expand=True)
  self.source=tk.StringVar(self.window,value=self.rules.source())
  fixed=ttk.Frame(self.body);fixed.pack(fill='x',pady=(0,10))
  ttk.Radiobutton(fixed,text='고정 사냥터 사용',variable=self.source,value='fixed',command=self.follow).pack(side='left')
  self.stationary=tk.StringVar(self.window,value=str(self.rules.stationary() or ''))
  self.fixed_slot=ttk.Combobox(fixed,textvariable=self.stationary,values=['1','2','3','4'],state='readonly',width=4)
  self.fixed_slot.pack(side='left',padx=(12,4))
  ttk.Label(fixed,text='번').pack(side='left')
  ttk.Radiobutton(self.body,text='전투력별 사냥터 사용',variable=self.source,value='power',command=self.follow).pack(anchor='w')
  self.list=ttk.Frame(self.body);self.list.pack(fill='both',expand=True,pady=8)
  for rule in self.rules.stored():self.add(rule['power'],rule['slot'])
  if not self.rows:self.add('','')
  actions=ttk.Frame(self.body);actions.pack(fill='x')
  ttk.Button(actions,text='기준 추가',command=self.add).pack(side='left')
  ttk.Button(actions,text='저장',command=self.save).pack(side='right')
  self.follow()
 def follow(self):
  """Only the selected source can be edited."""
  self.fixed_slot.configure(state='readonly' if self.source.get()=='fixed' else 'disabled')
  for row in self.rows:
   for widget in row[0].winfo_children():
    if isinstance(widget,ttk.Combobox):widget.configure(state='readonly' if self.source.get()=='power' else 'disabled')
    elif isinstance(widget,(ttk.Entry,ttk.Button)):widget.configure(state='normal' if self.source.get()=='power' else 'disabled')
 def add(self,power='',slot=''):
  if len(self.rows)>=4:
   messagebox.showinfo('사냥터 설정','사냥터는 최대 4개까지 설정할 수 있습니다.',parent=self.window);return
  frame=ttk.Frame(self.list);frame.pack(fill='x',pady=3)
  p=tk.StringVar(self.window,value=str(power));s=tk.StringVar(self.window,value=str(slot))
  ttk.Entry(frame,textvariable=p,width=12).pack(side='left',padx=(0,4))
  ttk.Label(frame,text='이상').pack(side='left');ttk.Combobox(frame,textvariable=s,values=[str(i) for i in range(1,5)],state='readonly',width=4).pack(side='left',padx=(12,4))
  ttk.Label(frame,text='번').pack(side='left')
  row=(frame,p,s);self.rows.append(row)
  ttk.Button(frame,text='삭제',command=lambda:self.remove(row)).pack(side='right')
  if hasattr(self,'fixed_slot'):self.follow()
 def remove(self,row):
  self.rows.remove(row);row[0].destroy()
 def save(self):
  try:
   values=[]
   for _,power,slot in self.rows:
    if not power.get().strip() and not slot.get().strip():continue
    values.append({'power':int(power.get().replace(',','').strip()),'slot':int(slot.get().strip())})
   stationary=int(self.stationary.get()) if self.stationary.get() else None
   power=self.source.get()=='power'
   if power and not values:raise ValueError('전투력 기준을 입력해 주세요')
   self.rules.store(values,stationary,enabled=power,fixed_enabled=not power)
  except (ValueError,OSError) as error:
   messagebox.showerror('사냥터 설정 확인',str(error),parent=self.window);return
  if not self.embedded:self.window.destroy()
  return True

def install(gui):
 """A compact settings entry; reuse the existing editors and native details."""
 if getattr(gui,'_owner_hunt_settings_candidate',False):return
 from owner_settings_layout import install as consolidate_settings
 consolidate_settings(gui)
 from owner_telemetry import install as telemetry_install,show as telemetry_settings
 telemetry_install(gui)
 def character_editor(window,editor):
  try:
   # Share the same unambiguous configured identity as the hunt rules.
   # It scopes settings; it does not prove the character in the live game.
   from owner_hunt_rules_candidate import configured_identity
   identity=configured_identity(gui.project.root)
   editor(window,gui.project.root,identity)
  except (OSError,ValueError,TypeError,AttributeError) as error:
   messagebox.showerror('설정 확인',str(error),parent=window)
 def show(*args,**kwargs):
  # Tk drops callback errors silently under pythonw, so a failure here would
  # look like a button that does nothing. Always leave a log and a message.
  gui.logger.info('세부설정 열기 요청')
  try:return open_hub()
  except Exception as error:
   gui.logger.exception('세부설정 열기 실패')
   messagebox.showerror('세부설정','세부설정을 열지 못했습니다.\n%s: %s'%(type(error).__name__,error),parent=gui.root)
 def open_hub():
  state=gui.session.snapshot()
  gui.logger.info('세부설정 상태 · %s · 작업자 %s',state.get('status'),'동작 중' if state.get('worker_alive') else '없음')
  # A paused session waits on the user, so settings can be edited. A stopped session
  # can still be finishing its last step.
  if state.get('status')=='running' or (state.get('worker_alive') and state.get('status')!='paused'):
   text='일시정지(F2)나 중지 후 설정을 변경해 주세요.' if state.get('status')=='running' else '이전 작업을 정리하는 중입니다. 잠시 후 다시 눌러 주세요.'
   messagebox.showinfo('세부설정',text,parent=gui.root);return
  window=getattr(gui,'_owner_settings_hub',None)
  if window is not None and window.winfo_exists():window.deiconify();window.lift();return
  from owner_shop_settings_candidate import open_settings as shop_editor
  from owner_gear_settings_candidate import open_settings as growth_editor
  from owner_starter_choice_candidate import open_settings as choice_editor
  def hunt_editor():
   try:HuntSettings(gui.root,gui.project.root)
   except (OSError,ValueError,TypeError) as error:messagebox.showerror('설정 확인',str(error),parent=gui.root)
  from owner_settings_console import SettingsConsole
  callbacks={'사냥터':hunt_editor,
    '성장':lambda:character_editor(gui.root,lambda parent,root,character:growth_editor(parent,root,character,gui=gui)),
    '상점':lambda:character_editor(gui.root,shop_editor),
    '상자':lambda:character_editor(gui.root,choice_editor),
    '진단':lambda:telemetry_settings(gui)}
  try:gui._owner_settings_hub=SettingsConsole(gui,callbacks).window;gui.logger.info('세부설정 창 열림')
  except (OSError,ValueError) as error:messagebox.showerror('설정 확인',str(error),parent=gui.root)
 bound={}
 def bind_buttons():
  # The layout hook runs every250ms; rebind only a replaced or changed widget.
  view=getattr(gui,'visual_view',None)
  for widget in (gui.details_button,getattr(view,'widgets',{}).get('details'),getattr(view,'originals',{}).get('details')):
   if widget is None or not widget.winfo_exists():continue
   if bound.get(widget)!=str(widget.cget('command')):
    widget.configure(command=show,text='세부설정');bound[widget]=str(widget.cget('command'))
 gui.open_details=show
 bind_buttons()
 from owner_main import MainPanel
 if not getattr(MainPanel.layout,'_owner_hunt_bind',False):
  from functools import wraps
  ordinary_layout=MainPanel.layout
  @wraps(ordinary_layout)
  def layout(panel):
   result=ordinary_layout(panel)
   rebind=getattr(panel.gui,'_owner_hunt_rebind',None)
   if rebind is not None:rebind()
   return result
  layout._owner_hunt_bind=True;MainPanel.layout=layout
 gui._owner_hunt_rebind=bind_buttons
 gui._owner_hunt_settings_candidate=True
