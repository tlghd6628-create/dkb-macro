"""User-triggered feature inspection UI; no game input is implemented here."""
import queue,threading,logging,weakref,json
from pathlib import Path
from owner_feature_check_status_candidate import status as display_status,stage_name as stage_label
from functools import wraps
import tkinter as tk
from tkinter import ttk,messagebox

LOG=logging.getLogger('project_gui.DKB')

def level_label(row):
 checked=row.get('verification') if isinstance(row.get('verification'),dict) else {}
 return checked.get('level') or '—'

def detail_text(row):
 checked=row.get('verification') if isinstance(row.get('verification'),dict) else {}
 parts=[str(row.get('detail',''))]
 if checked:parts.append('검증 '+str(checked.get('level') or '없음')+'('+str(checked.get('level_name',''))+')')
 if checked.get('unverified_reason'):parts.append('미검증 사유: '+str(checked['unverified_reason']))
 if checked.get('next_step'):parts.append('다음 조치: '+str(checked['next_step']))
 if row.get('evidence_file'):parts.append('증거: '+str(row['evidence_file']))
 return ' · '.join(parts)

class FeaturePanel:
 def __init__(self,gui):
  self.gui=gui;self.lock=threading.RLock();self.worker=None;self.cancel=None;self.preparing=False
  self.events=queue.Queue();self.dialog=None;self.tree=None;self.detail=None;self.poll_job=None;self.generation=0;self.has_probe=False;self.report_path=None;self.error=None
  self._bound_commands=weakref.WeakKeyDictionary();self.summary=None
  panel=getattr(gui,'_owner_main',None)
  if panel is None or not getattr(panel,'frame',None):raise RuntimeError('기능 점검 버튼을 놓을 기본 패널이 없습니다')
  self.button=ttk.Button(panel.frame,text='기능 점검',command=self.open)
  # The compact live panel is only 458px wide. Its schedule button already
  # occupies the upper-right slot; another grid column is clipped offscreen.
  self.button.place(relx=1,x=-88,y=24,width=83,height=23);self.button.lift()
  self._guard_starts();self.bind_buttons()
  gui.root.bind('<Destroy>',self.on_root_destroy,add='+')

 def active(self):return self.preparing or (self.worker is not None and self.worker.is_alive())

 def _guard_starts(self):
  panel=self;gui=self.gui
  def fence(original):
   @wraps(original)
   def guarded(*args,**kwargs):
    with panel.lock:
     if panel.active():raise RuntimeError('기능 점검이 끝난 뒤 시작해 주세요')
     return original(*args,**kwargs)
   return guarded
  gui.session.start=fence(gui.session.start)
  original_stop=gui.session.stop
  @wraps(original_stop)
  def stop_session(*args,**kwargs):
   with panel.lock:
    if panel.active():
     if panel.cancel is not None:panel.cancel.set()
     state=gui.session.snapshot()
     if state.get('status')=='stopped' and not state.get('worker_alive'):return None
    return original_stop(*args,**kwargs)
  gui.session.stop=stop_session
  flow=getattr(gui,'launch_flow',None)
  if flow is not None and callable(getattr(flow,'start',None)):flow.start=fence(flow.start)
  original_request=gui.start_requested
  @wraps(original_request)
  def request(*args,**kwargs):
   with panel.lock:
    if panel.active():
     hint=getattr(gui,'game_hint',None)
     if hint is not None:hint.set('기능 점검이 끝난 뒤 시작해 주세요')
     LOG.info('자동 진행 시작 보류 · 기능 점검 중')
     return None
    return original_request(*args,**kwargs)
  gui.start_requested=request
  # A readiness callback may already have been queued by a Start request.
  ready=getattr(gui,'_start_after_input_ready',None)
  if callable(ready):gui._start_after_input_ready=fence(ready)

 def bind_buttons(self):
  view=getattr(self.gui,'visual_view',None)
  items=[getattr(self.gui,'start_button',None),getattr(view,'widgets',{}).get('start'),getattr(view,'originals',{}).get('start')]
  for widget in items:
   if widget is not None:
    try:
     if widget.winfo_exists():
      current=str(widget.cget('command'))
      if current!=self._bound_commands.get(widget):
       widget.configure(command=self.gui.start_requested)
       self._bound_commands[widget]=str(widget.cget('command'))
    except (tk.TclError,AttributeError):pass

 def catalog(self):
  from owner_feature_check_catalog_candidate import CHECKS
  result=[];seen=set()
  for item in CHECKS:
   if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'] or item['id'] in seen or not isinstance(item.get('name'),str):
    raise ValueError('기능 점검 항목 목록을 확인해 주세요')
   seen.add(item['id']);result.append(item)
  return result

 def open(self):
  if self.dialog is not None:
   try:self.dialog.lift();return
   except tk.TclError:self.dialog=None
  try:items=self.catalog()
  except (ImportError,ValueError,OSError) as exc:
   messagebox.showerror('기능 점검',str(exc),parent=self.gui.root);return
  self.item_meta={item['id']:item for item in items}
  win=tk.Toplevel(self.gui.root);self.dialog=win;win.title('기능 점검');win.geometry('900x520')
  win.protocol('WM_DELETE_WINDOW',self.close_dialog)
  outer=ttk.Frame(win,padding=10);outer.pack(fill='both',expand=True)
  ttk.Label(outer,text='화면·조건 점검 · 실제 강화·구매·입장 없음').pack(anchor='w',pady=(0,6))
  table=ttk.Frame(outer);table.pack(fill='both',expand=True)
  self.tree=ttk.Treeview(table,columns=('name','settings','screen','stage','result','level'),show='headings',selectmode='extended')
  for key,label,width in (('name','기능',165),('settings','설정',65),('screen','화면',170),('stage','단계',85),('result','결과',270),('level','검증',45)):
   self.tree.heading(key,text=label);self.tree.column(key,width=width,stretch=key not in ('stage','result'))
  bar=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=bar.set)
  self.tree.pack(side='left',fill='both',expand=True);bar.pack(side='right',fill='y')
  for item in items:self.tree.insert('','end',iid=item['id'],values=(item['name'],'미점검','미점검','—','대기','—'))
  self.details={};self.detail=tk.StringVar(win,value='항목을 선택하면 점검 내용을 볼 수 있습니다.')
  self.tree.bind('<<TreeviewSelect>>',self.select_detail)
  ttk.Label(outer,textvariable=self.detail,wraplength=860).pack(fill='x',pady=6)
  controls=ttk.Frame(outer);controls.pack(fill='x')
  self.selected_btn=ttk.Button(controls,text='선택 점검',command=self.run_selected);self.selected_btn.pack(side='left')
  self.all_btn=ttk.Button(controls,text='전체 점검',command=self.run_all);self.all_btn.pack(side='left',padx=6)
  self.stop_btn=ttk.Button(controls,text='점검 중지',command=self.stop);self.stop_btn.pack(side='left')
  self.status=tk.StringVar(win,value='점검 대기');ttk.Label(controls,textvariable=self.status).pack(side='right')
  self.restore_latest();self.paint()

 def restore_latest(self):
  folder=Path(self.gui.project.root)/'logs/feature-checks'
  try:
   paths=sorted(folder.glob('*.json'))
   if not paths:return
   data=json.loads(paths[-1].read_text(encoding='utf-8'))
   if not isinstance(data.get('rows'),list):return
   for row in data['rows']:
    key=row.get('id')
    if not key or not self.tree.exists(key):continue
    self.tree.item(key,values=(row.get('name',''),row.get('settings','—'),row.get('screen','미점검'),stage_label(row),display_status(row),level_label(row)))
    self.details[key]=detail_text(row)
   self.report_path=str(paths[-1]);self.status.set('이전 점검 결과 · '+str(data.get('at',''))[11:19])
  except (ValueError,OSError,TypeError):self.status.set('이전 점검 결과 확인 필요')

 def select_detail(self,_event=None):
  selection=self.tree.selection() if self.tree is not None else ()
  if self.detail is not None:self.detail.set(self.details.get(selection[0],'상세 기록 없음') if selection else '항목을 선택하면 점검 내용을 볼 수 있습니다.')

 def run_selected(self):
  selected=list(self.tree.selection())
  if not selected:
   messagebox.showinfo('기능 점검','점검할 항목을 먼저 선택해 주세요.',parent=self.dialog);return
  self.start(selected)

 def run_all(self):self.start([item['id'] for item in self.catalog()])

 def start(self,selected):
  with self.lock:
   state=self.gui.session.snapshot()
   busy=getattr(getattr(self.gui,'input_preparation',None),'busy',lambda:False)()
   if self.active():self.message('이미 기능 점검 중입니다.');return False
   if self.gui.closed.is_set() or state.get('status')!='stopped' or state.get('worker_alive') or busy:
    self.message('프로그램이 완전히 중지된 상태에서 점검해 주세요.');return False
   known={item['id'] for item in self.catalog()}
   if not selected or any(x not in known for x in selected):self.message('점검 항목을 다시 선택해 주세요.');return False
   self.cancel=threading.Event();self.preparing=True
   for key in selected:
    if self.tree is not None and self.tree.exists(key):
     old=self.tree.item(key,'values');self.tree.item(key,values=(old[0],'미점검','미점검','—','대기','—'));self.details.pop(key,None)
   cancel=self.cancel;root=self.gui.project.root
   factory=getattr(self.gui,'_owner_feature_probe_factory',None)
   try:probe=factory(cancel) if callable(factory) else getattr(self.gui,'_owner_feature_probe',None)
   except Exception as exc:
    self.preparing=False;self.message('점검 준비 실패 · '+str(exc));return False
   self.has_probe=callable(probe)
   if probe is not None and not self.has_probe:
    self.preparing=False;self.message('화면 점검 준비 형식 확인 필요');return False
   self.generation+=1;generation=self.generation;self.report_path=None;self.error=None;self.summary=None
   def worker():
    try:
     from owner_feature_checks_candidate import run_checks
     report=run_checks(root,list(selected),lambda row:self.events.put((generation,'row',row)),cancel,probe=probe)
     if isinstance(report,dict) and isinstance(report.get('report_file'),str):
      self.events.put((generation,'report',report['report_file']))
      self.events.put((generation,'summary',report.get('summary')))
    except Exception as exc:self.events.put((generation,'error',str(exc) or type(exc).__name__))
    finally:
     close=getattr(probe,'close',None)
     if callable(close):
      try:close()
      except Exception as exc:self.events.put((generation,'error','점검 자원 정리 실패 · '+str(exc)))
     self.events.put((generation,'done',None))
   self.worker=threading.Thread(target=worker,name='dkb-feature-check',daemon=True)
   try:self.worker.start()
   except Exception:
    self.preparing=False
    raise
   self.preparing=False;self.message('점검 중');self.paint();self.ensure_poll();return True

 def message(self,text):
  if self.dialog is not None and self.status is not None:self.status.set(text)
  LOG.info('기능 점검 · %s',text)

 def ensure_poll(self):
  if self.poll_job is None and not self.gui.closed.is_set():self.poll_job=self.gui.root.after(100,self.poll)

 def poll(self):
  self.poll_job=None;finished=False
  while True:
   try:generation,kind,value=self.events.get_nowait()
   except queue.Empty:break
   if generation!=self.generation:continue
   if kind=='row' and isinstance(value,dict) and self.dialog is not None:
    key=value.get('id')
    if self.tree is not None and isinstance(key,str) and self.tree.exists(key):
     screen=value.get('screen','미검증');result=value.get('result','확인 필요')
     meta=self.item_meta.get(key,{})
     if not self.has_probe:
      if meta.get('disabled_by_user'):screen='제외'
      elif meta.get('schedule_only'):screen='화면 미점검 · 예약 계산'
      else:
       screen='미검증'
       if result=='정상':result='확인 필요'
     if result=='정상' and not meta.get('schedule_only') and (value.get('screen_verified') is not True or value.get('decision_verified') is not True):
      result='확인 필요'
     shown=dict(value,result=result,screen=screen)
     self.tree.item(key,values=(str(value.get('name','')),str(value.get('settings','미점검')),str(screen),stage_label(shown),display_status(shown),level_label(value)))
     self.details[key]=detail_text(value)
     if key in self.tree.selection():self.select_detail()
   elif kind=='error':self.error='점검 오류 · '+str(value)
   elif kind=='report':self.report_path=value
   elif kind=='summary':self.summary=value
   elif kind=='done':finished=True
  if self.error:self.message(self.error)
  elif finished:
   text='점검 중지' if self.cancel and self.cancel.is_set() else '점검 종료'
   self.message(text+' · 결과 자동 저장' if self.report_path else text+' · 결과를 확인해 주세요')
   if isinstance(self.summary,dict):
    self.message(' · '.join(label+' '+str(self.summary.get(key,0)) for key,label in (('normal','정상'),('waiting','대기'),('excluded','제외'),('error','오류'),('unverified','미검증')))+' · 자동 저장')
   if self.report_path:LOG.info('기능 점검 결과 저장 · %s',self.report_path)
  self.paint()
  if self.active() or not self.events.empty():self.ensure_poll()

 def paint(self):
  if self.dialog is None:return
  status='disabled' if self.active() else 'normal'
  for widget in (self.selected_btn,self.all_btn):widget.configure(state=status)
  self.stop_btn.configure(state='normal' if self.active() else 'disabled')

 def stop(self):
  if self.cancel is not None and self.active():self.cancel.set();self.message('중지 요청 · 현재 단계 종료 대기')

 def close_dialog(self):
  self.stop()
  if self.dialog is not None:self.dialog.destroy()
  self.dialog=None;self.tree=None;self.detail=None

 def on_root_destroy(self,event):
  if event.widget is self.gui.root and self.cancel is not None:self.cancel.set()

def install(gui):
 if getattr(gui,'_owner_feature_check',None) is not None:return gui._owner_feature_check
 panel=FeaturePanel(gui);gui._owner_feature_check=panel
 # MainPanel/layout is periodically rebuilt: attach to its stable child frame
 # and rebind any newly created visible Start button to the same fence.
 from owner_main import MainPanel
 original=MainPanel.layout
 if not getattr(original,'_owner_feature_check_fence',False):
  @wraps(original)
  def layout(main,*args,**kwargs):
   result=original(main,*args,**kwargs)
   owner=getattr(main.gui,'_owner_feature_check',None)
   if owner is not None:
    owner.button.lift();owner.bind_buttons()
   return result
  layout._owner_feature_check_fence=True;MainPanel.layout=layout
 return panel
