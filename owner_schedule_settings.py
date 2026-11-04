"""Compact schedule editor over the existing persistent timetable."""
import copy
import tkinter as tk
from tkinter import ttk
from owner_timetable import JOBS,config,save_user_rules,set_user_rule

def rows(cfg):
 result=[]
 for job in JOBS:
  from owner_reward_context import JOBS as reward_jobs
  if job.key in reward_jobs:continue
  rule=cfg.get('jobs',{}).get(job.key,{})
  days=rule.get('weekdays',[job.weekday] if job.week and job.weekday is not None else list(range(7)))
  label='일회성' if job.once else '매일' if set(days)==set(range(7)) else ' '.join('월화수목금토일'[i] for i in sorted(days))
  result.append((job.key,job.label,label,rule.get('time',job.clock),str(rule.get('jitter_seconds',cfg.get('jitter_seconds',60)))))
 return result

class ScheduleEditor:
 def __init__(self,parent,root):
  self.root=root;self.cfg=config(root);self.selected=None;self.loading=False;self.drafts={}
  self.frame=ttk.Frame(parent,padding=8);self.frame.pack(fill='both',expand=True)
  columns=('name','days','clock','spread')
  self.tree=ttk.Treeview(self.frame,columns=columns,show='headings',height=12,selectmode='browse')
  for key,label,width in zip(columns,('콘텐츠','요일','시각','랜덤 ±초'),(220,150,85,90)):
   self.tree.heading(key,text=label);self.tree.column(key,width=width,anchor='w' if key=='name' else 'center')
  self.tree.grid(row=0,column=0,columnspan=5,sticky='nsew')
  scroll=ttk.Scrollbar(self.frame,orient='vertical',command=self.tree.yview);scroll.grid(row=0,column=5,sticky='ns');self.tree.configure(yscrollcommand=scroll.set)
  self.frame.rowconfigure(0,weight=1);self.frame.columnconfigure(1,weight=1)
  self.days=[tk.BooleanVar(self.frame) for _ in range(7)]
  group=ttk.Frame(self.frame);group.grid(row=1,column=0,columnspan=6,sticky='w',pady=8)
  self.day_widgets=[]
  for i,label in enumerate('월화수목금토일'):
   w=ttk.Checkbutton(group,text=label,variable=self.days[i]);w.pack(side='left',padx=3);self.day_widgets.append(w)
  self.hour=tk.StringVar(self.frame);self.minute=tk.StringVar(self.frame);self.spread=tk.StringVar(self.frame)
  bar=ttk.Frame(self.frame);bar.grid(row=2,column=0,columnspan=6,sticky='w')
  ttk.Label(bar,text='시각').pack(side='left')
  ttk.Spinbox(bar,textvariable=self.hour,from_=0,to=23,width=4,format='%02.0f').pack(side='left',padx=4)
  ttk.Label(bar,text=':').pack(side='left')
  ttk.Spinbox(bar,textvariable=self.minute,from_=0,to=59,width=4,format='%02.0f').pack(side='left',padx=4)
  ttk.Label(bar,text='랜덤 ±초').pack(side='left',padx=(18,4))
  ttk.Spinbox(bar,textvariable=self.spread,from_=0,to=120,width=5).pack(side='left')
  ttk.Button(bar,text='저장',command=self.save).pack(side='left',padx=14)
  self.notice=tk.StringVar(self.frame,value='선택한 콘텐츠의 기준 시각 · 보스 출발 시간은 자동 회피')
  ttk.Label(self.frame,textvariable=self.notice).grid(row=3,column=0,columnspan=6,sticky='w',pady=(8,0))
  self.tree.bind('<<TreeviewSelect>>',self.select);self.refresh()
  first=self.tree.get_children()
  if first:self.tree.selection_set(first[0]);self.select()
 def refresh(self):
  for key,name,days,clock,spread in rows(self.cfg):
   values=(name,days,clock,spread)
   if self.tree.exists(key):self.tree.item(key,values=values)
   else:self.tree.insert('','end',iid=key,values=values)
 def select(self,event=None):
  chosen=self.tree.selection()
  if not chosen:return
  self.stash()
  self.selected=chosen[0];job=next(j for j in JOBS if j.key==self.selected);rule=self.cfg['jobs'][job.key]
  draft=self.drafts.get(job.key)
  clock=rule.get('time',job.clock);self.hour.set(draft['hour'] if draft else clock[:2]);self.minute.set(draft['minute'] if draft else clock[3:])
  self.spread.set(draft['spread'] if draft else str(rule.get('jitter_seconds',self.cfg.get('jitter_seconds',60))))
  days=draft['days'] if draft else rule.get('weekdays',[job.weekday] if job.week and job.weekday is not None else list(range(7)))
  for i,var in enumerate(self.days):var.set(i in days)
  for widget in self.day_widgets:widget.configure(state='disabled' if job.once else 'normal')
  self.notice.set(job.label+(' · 일회성 완료 기록 유지' if job.once else ''))
 def stash(self):
  if self.selected:self.drafts[self.selected]={'hour':self.hour.get(),'minute':self.minute.get(),'spread':self.spread.get(),'days':[i for i,v in enumerate(self.days) if v.get()]}
 def validate(self):
  self.stash();changes={};trial=self.cfg
  for key,draft in self.drafts.items():
   clock=f"{int(draft['hour']):02d}:{int(draft['minute']):02d}"
   changes[key]={'clock':clock,'weekdays':draft['days'],'jitter_seconds':int(draft['spread'])}
   trial=set_user_rule(trial,key,clock,draft['days'],int(draft['spread']))
  return changes
 def save(self,*,raise_errors=False):
  try:
   changes=self.validate()
   self.cfg=save_user_rules(self.root,changes,expected_rules={key:copy.deepcopy(self.cfg['jobs'][key]) for key in changes})
   self.drafts.clear();self.refresh();self.notice.set('저장 완료');return True
  except (OSError,ValueError) as exc:
   self.notice.set(str(exc))
   if raise_errors:raise
   return False

def show(parent,root):
 win=tk.Toplevel(parent);win.title('스케줄 설정');win.geometry('740x600');ScheduleEditor(win,root);return win
