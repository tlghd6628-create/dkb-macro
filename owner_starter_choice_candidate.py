"""Starter-choice settings and positive learned-skill check on the owner worker.

The selection-box dialog and claim receipt have not yet been observed; this
module never opens/chooses/consumes a box and never treats absence as proof.
"""
from functools import wraps
from pathlib import Path
import hashlib,json,logging,math,os,sys,tempfile,threading,time
import tkinter as tk
from tkinter import ttk,messagebox
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()
ENERGIES=('생명','여명','몽환','홍염')
SKILLS=('생명의 흐름','방패 밀기','공간 결계')
# The rows of the 기념 도술 조각 box and the 강화 요령서 box, read from the game on 2026-11-05.
BOX_SKILLS=('방패 치기','방패 밀기','방패 충격파','방패 내려찍기','강인한 의지',
            '생명의 흐름','산들 바람','생명의 축복','불굴','최후의 저항',
            '부적 던지기','살 날리기','저주 내리기','신벌의 영역','영혼 소용돌이',
            '슬쩍 베기','어지럼 유발','광기의 칼놀림','솟아오르는 창','간파의 눈','공간 결계',
            '급소 관통','도약 찌르기','휩쓸어 베기','후퇴 사격','쌍검 가르기')
MANUALS=('절명','연타','강타','척살','저격','주술','파멸','강인','기동','기만','헌신','제압')
class ChoiceNavigationError(RuntimeError):pass

def chosen_skills(root,profile):
 """(id, name) of the skills picked for the fragment box; the three named ones until changed."""
 from owner_skill_goal import catalog
 names=Choices(root,profile).snapshot()[0].get('skills',SKILLS);known=catalog()['all_skill_names']
 return [(known[name]['id'],name) for name in names if name in known]

class SkillAttestation:
 """Separate evidence for three skills seen under the proved owned filter."""
 def __init__(self,root,receipt_key):
  if not isinstance(receipt_key,str) or not receipt_key.strip():raise ValueError('캐릭터 확인 필요')
  key=hashlib.sha256(receipt_key.encode('utf8')).hexdigest()[:24]
  self.path=Path(root)/'settings'/('owner-starter-skill-'+key+'.json')
  self.key=receipt_key
 def known(self):
  if not self.path.exists():return False
  value=json.loads(self.path.read_text(encoding='utf8'))
  return (isinstance(value,dict) and value.get('version')==1 and value.get('receipt_key')==self.key
          and value.get('owned_ids')==[68,84,89] and value.get('filter')=='paired_owned_only_v1'
          and type(value.get('observed_at')) in (int,float) and math.isfinite(value['observed_at']))
 def record(self,owned):
  if not isinstance(owned,set) or not {68,84,89}.issubset(owned):raise ValueError('세 도술의 보유 확인 필요')
  self.path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.starter-skill-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w',encoding='utf8') as f:
    json.dump({'version':1,'receipt_key':self.key,'owned_ids':[68,84,89],
               'filter':'paired_owned_only_v1','observed_at':time.time()},f,ensure_ascii=False,indent=2)
    f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)

def owned_filter_frame(frame):
 """Check the filter on the same frame used to identify a skill."""
 from PIL import Image
 import cv2,numpy as np
 from owner_skill_ui import skill_screen
 path=Path(__file__).parent/'assets/starter-choice/owned-filter-unchecked.png'
 if not path.is_file():return False
 try:template=np.asarray(Image.open(path).convert('RGB'))
 except (OSError,ValueError):return False
 if not skill_screen(frame):return False
 patch=frame[57:75,687:705]
 if template.shape[0]>patch.shape[0] or template.shape[1]>patch.shape[1]:return False
 score=cv2.matchTemplate(patch,template,cv2.TM_CCOEFF_NORMED)
 return bool(np.isfinite(score).all() and float(score.max())>=.97)

def owned_filter_proved(ui):
 """Require a positively observed unchecked filter, not absent checkmark."""
 # The list is still settling right after a scroll or filter press, so give it a moment.
 for attempt in range(5):
  first=ui.frame();ui.context.wait(.12);second=ui.frame()
  if owned_filter_frame(first) and owned_filter_frame(second):return True
  ui.context.wait(.4)
 return False

def positive_skill_icons(first,second):
 """Find target icons with full-catalog competition in two saved frames.

 Icon recognition alone never asserts ownership; caller must first prove the
 owned-only filter. Return ids/positions only, no missing-skill inference.
 """
 import cv2,numpy as np
 from owner_skill_ui import icon,identify_icon,skill_screen
 if not skill_screen(first) or not skill_screen(second):return []
 def page(frame):
  crop=frame[79:479,695:737];result=[]
  for sid in (68,84,89):
   possibilities=[]
   for width in (30,32,34):
    needle=icon(sid,width)
    score=cv2.matchTemplate(crop,needle,cv2.TM_CCOEFF_NORMED)
    positions=np.argwhere(np.isfinite(score)&(score>=.90))
    for yy,xx in positions:
     cx=int(xx)+695+needle.shape[1]//2;cy=int(yy)+79+needle.shape[0]//2
     box=(max(0,cx-20),max(0,cy-20),40,min(40,479-max(0,cy-20)))
     if identify_icon(frame,box)==sid:possibilities.append(cy)
   if possibilities:result.append((sid,round(sum(possibilities)/len(possibilities))))
  return result
 a,b=page(first),page(second)
 return [(sid,y) for sid,y in a if any(other==sid and abs(y-y2)<=3 for other,y2 in b)]

def _icons_to_end(ui,Pending):
 """Target icons on every page of the proved owned-only list, until the list stops moving."""
 import numpy as np
 from owner_skill_ui import skill_screen
 ui.open_skills();ui.all_filter(True)
 for _ in range(3):ui.drag((762,118),(762,424),skill_screen)
 found=set();previous=None
 for _ in range(30):
  ui.context.wait(1.);first=ui.frame();ui.context.wait(.12);second=ui.frame()
  if not owned_filter_frame(first) or not owned_filter_frame(second):raise Pending('보유 도술 필터 변경')
  found.update(sid for sid,_y in positive_skill_icons(first,second))
  page=second[79:440,695:840].astype('int16')
  if previous is not None and float(np.abs(page-previous).mean())<4:return found
  previous=page;ui.drag((762,425),(762,117),skill_screen)
 raise Pending('보유 도술 목록 끝 확인 실패')

class _RequiredSkillsFound(Exception):
 def __init__(self,owned):self.owned=set(owned)

def _enable_owned_icon_fallback(ui):
 """Extend native owned-list rows without treating an uncertain filter as owned."""
 from owner_skill_goal import Pending,catalog
 original=ui.skill_rows
 found=set()
 def rows():
  try:result=list(original())
  except Pending:result=[]
  if not owned_filter_proved(ui):raise Pending('보유 도술 전용 필터 확인 필요')
  paired=getattr(ui,'_owner_last_rows_pair',None)
  if result and (not paired or len(paired[0])!=2 or not all(owned_filter_frame(f) for f in paired[0])):result=[]
  first=ui.frame();ui.context.wait(.12);second=ui.frame()
  if not owned_filter_frame(first) or not owned_filter_frame(second):raise Pending('보유 도술 필터 변경')
  ids={row['id'] for row in result}
  for sid,y in positive_skill_icons(first,second):
   if sid not in ids:
    result.append({'id':sid,'name':catalog()['skills'][str(sid)]['name'],'y':y,'x':716,'score':.90})
  found.update(row['id'] for row in result)
  if {68,84,89}.issubset(found):raise _RequiredSkillsFound(found)
  return result
 ui.skill_rows=rows

class Choices:
 def __init__(self,root,profile):
  if not isinstance(profile,str) or not profile.strip():raise ValueError('캐릭터 설정 확인 필요')
  key=hashlib.sha256(profile.encode('utf8')).hexdigest()[:24]
  self.path=Path(root)/'settings'/('owner-starter-choice-'+key+'.json')
 def snapshot(self):
  if not self.path.exists():return {'version':1,'energy_mode':'balanced','energies':['생명','여명','몽환']},'missing'
  raw=self.path.read_bytes();data=json.loads(raw.decode('utf-8-sig'));self.validate(data)
  return data,hashlib.sha256(raw).hexdigest()
 @staticmethod
 def validate(data):
  if not isinstance(data,dict) or data.get('version')!=1 or data.get('energy_mode') not in ('balanced','single','percent'):raise ValueError('상자 설정 형식 오류')
  names=data.get('energies')
  if not isinstance(names,list) or len(names)!=len(set(names)) or any(x not in ENERGIES for x in names):raise ValueError('기운 종류 확인 필요')
  if data['energy_mode']=='single' and len(names)!=1:raise ValueError('한 가지 모드는 기운을 한 개만 선택해 주세요')
  from owner_energy_allocation_candidate import weights
  weights(data)
  skills=data.get('skills',SKILLS)
  if not isinstance(skills,(list,tuple)) or len(skills)>5 or any(x not in BOX_SKILLS for x in skills):raise ValueError('도술 조각은 5개까지 고를 수 있습니다')
  if data.get('manual') not in (None,)+MANUALS:raise ValueError('요령서 종류 확인 필요')
 def write(self,data,expected):
  self.validate(data);_,revision=self.snapshot()
  if revision!=expected:raise ValueError('다른 창에서 설정이 바뀌었습니다. 다시 열어 주세요')
  self.path.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(prefix='.starter-choice-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
   if self.snapshot()[1]!=expected:raise ValueError('다른 창에서 설정이 바뀌었습니다. 다시 열어 주세요')
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)

class EnergyLedger:
 """Only confirmed acquisitions influence balancing, scoped to character."""
 def __init__(self,root,receipt_key):
  if not isinstance(receipt_key,str) or not receipt_key.strip():raise ValueError('캐릭터 확인 필요')
  key=hashlib.sha256(receipt_key.encode('utf8')).hexdigest()[:24]
  self.path=Path(root)/'settings'/('owner-energy-choice-'+key+'.json')
 def read(self):
  if not self.path.exists():return {'version':1,'confirmed':{name:0 for name in ENERGIES},'receipts':[],'pending':None}
  data=json.loads(self.path.read_text(encoding='utf8'))
  if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('confirmed'),dict) or not isinstance(data.get('receipts'),list):raise ValueError('기운 상자 기록 형식 오류')
  if any(type(data['confirmed'].get(name)) is not int or data['confirmed'][name]<0 for name in ENERGIES):raise ValueError('기운 상자 누적 수량 확인 필요')
  if data.get('pending') is not None and not isinstance(data['pending'],dict):raise ValueError('기운 상자 대기 기록 확인 필요')
  return data
 def _write(self,data):
  self.path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.energy-choice-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 def next(self,selected):
  if not isinstance(selected,list) or len(selected)!=len(set(selected)) or any(name not in ENERGIES for name in selected):raise ValueError('기운 선택 확인 필요')
  if not selected:return None
  data=self.read()
  if data['pending'] is not None:raise ValueError('이전 상자 수령 결과 미확인')
  return min(selected,key=lambda name:(data['confirmed'][name],ENERGIES.index(name)))
 def begin(self,name,before):
  if name not in ENERGIES or not isinstance(before,dict) or before.get('verified') is not True or type(before.get('owned')) is not int or type(before.get('boxes')) is not int or before['owned']<0 or before['boxes']<1:
   raise ValueError('상자 선택 전 현재 수량 확인 필요')
  frames=before.get('frame_ids')
  if not isinstance(frames,list) or len(frames)!=2 or any(not isinstance(x,str) or not x for x in frames) or frames[0]==frames[1]:raise ValueError('서로 다른 두 화면 필요')
  observed=before.get('captured_at');now=time.time()
  if type(observed) not in (int,float) or not math.isfinite(observed) or not 0<=now-observed<=5:raise ValueError('상자 선택 전 화면 신선도 확인 필요')
  data=self.read()
  if data['pending'] is not None:raise ValueError('이전 상자 수령 결과 미확인')
  old={frame for entry in data['receipts'] for frame in entry.get('frame_ids',[])}
  if set(frames)&old:raise ValueError('이전 수령 화면 재사용 불가')
  data['pending']={'name':name,'before':before,'at':now};self._write(data)
 def confirm(self,after):
  data=self.read();pending=data['pending']
  if not pending or not isinstance(after,dict) or after.get('verified') is not True or after.get('name')!=pending['name']:
   raise ValueError('상자 획득 증거 확인 필요')
  before=pending['before'];frames=after.get('frame_ids')
  observed=after.get('captured_at');now=time.time()
  old={frame for entry in data['receipts'] for frame in entry.get('frame_ids',[])}
  if (not isinstance(frames,list) or len(frames)!=2 or any(not isinstance(x,str) or not x for x in frames) or frames[0]==frames[1] or set(frames)&old
      or set(frames)&set(before['frame_ids']) or type(after.get('owned')) is not int or type(after.get('boxes')) is not int
      or type(observed) not in (int,float) or not math.isfinite(observed) or observed<pending['at'] or not 0<=now-observed<=5
      or after['boxes']!=before['boxes']-1 or after['owned']<=before['owned'] or after.get('receipt') is not True):
   raise ValueError('상자 차감과 선택 기운 획득을 두 화면에서 확인해야 합니다')
  increase=after['owned']-before['owned'];data['confirmed'][pending['name']]+=increase
  data['receipts'].append({'name':pending['name'],'increase':increase,'frame_ids':frames,'at':time.time()})
  data['pending']=None;self._write(data);return increase

def open_settings(parent,root,profile,*,embedded=False):
 from owner_energy_allocation_candidate import equal_display,percent_units
 store=Choices(root,profile);data,revision=store.snapshot()
 win=ttk.Frame(parent) if embedded else tk.Toplevel(parent)
 if embedded:win.pack(fill='both',expand=True)
 else:win.title('선택 상자 설정');win.transient(parent)
 body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True)
 ttk.Label(body,text='기념 도술 조각 선택 상자').pack(anchor='w')
 skill_box=tk.Listbox(body,selectmode='multiple',height=8,exportselection=False)
 skill_box.pack(fill='x',pady=(4,10))
 for index,name in enumerate(BOX_SKILLS):
  skill_box.insert('end',name)
  if name in data.get('skills',SKILLS):skill_box.selection_set(index)
 ttk.Label(body,text='강화 요령서 선택 첩').pack(anchor='w')
 manual=tk.StringVar(win,value=data.get('manual') or '사용 안 함')
 ttk.Combobox(body,textvariable=manual,values=('사용 안 함',)+MANUALS,state='readonly',width=14).pack(anchor='w',pady=(4,10))
 ttk.Label(body,text='발현 재료 선택 상자').pack(anchor='w')
 grid=ttk.Frame(body);grid.pack(fill='x',pady=(4,8))
 for column,label in enumerate(('기운','비율 (%)','')):ttk.Label(grid,text=label).grid(row=0,column=column,padx=6,sticky='w')
 initial=data.get('energy_percentages') if data['energy_mode']=='percent' else equal_display(data['energies'])
 choices={name:tk.StringVar(win,value=str(initial[name])) for name in ENERGIES};equal=[data['energy_mode'] in ('balanced','single')]
 total=tk.StringVar(win)
 def changed(*args):
  equal[0]=False
  try:
   from decimal import Decimal
   value=sum(Decimal(v.get().strip()) for v in choices.values())
   total.set('사용 안 함' if value==0 else '합계 '+format(value,'f')+'%')
  except Exception:total.set('합계 —')
 for index,name in enumerate(ENERGIES,1):
  ttk.Label(grid,text=name).grid(row=index,column=0,padx=6,pady=4,sticky='w')
  ttk.Entry(grid,textvariable=choices[name],width=8).grid(row=index,column=1,padx=6,pady=4)
  if name=='홍염':ttk.Label(grid,text='수령 확인 대기').grid(row=index,column=2,padx=6,sticky='w')
  choices[name].trace_add('write',changed)
 def make_equal():
  from decimal import Decimal,InvalidOperation
  selected=[]
  for name in ENERGIES:
   try:
    if Decimal(choices[name].get())>0:selected.append(name)
   except InvalidOperation:pass
  if not selected:selected=['생명','여명','몽환']
  for name,value in equal_display(selected).items():choices[name].set(value)
  equal[0]=True
 changed();equal[0]=data['energy_mode'] in ('balanced','single')
 footer=ttk.Frame(body);footer.pack(fill='x')
 ttk.Label(footer,textvariable=total).pack(side='left')
 ttk.Button(footer,text='균등',command=make_equal).pack(side='left',padx=10)
 def save():
  nonlocal revision,data
  try:
   values={n:choices[n].get() for n in ENERGIES};units=percent_units(values)
   updated=dict(data,energy_mode='balanced' if equal[0] else 'percent',energies=[n for n in ENERGIES if units[n]>0],
                energy_percentages={n:f'{units[n]//100}.{units[n]%100:02d}' for n in ENERGIES},
                skills=[BOX_SKILLS[i] for i in skill_box.curselection()],manual=None if manual.get()=='사용 안 함' else manual.get())
   store.write(updated,revision)
   data,revision=store.snapshot()
  except (OSError,ValueError) as exc:messagebox.showerror('상자 설정 확인',str(exc),parent=win);return
  if not embedded:win.destroy()
  return True
 win.save=save
 ttk.Button(footer,text='저장',command=save).pack(side='right')
 return win

def scan_learned(adapter,context,inputs):
 """Persist positive skill observations from the native paired owned list."""
 from owner_progression import state
 from owner_quest_preflight import read_power
 from owner_skill_goal import runtime_ledger,Pending
 from owner_learned_skills_candidate import LearnedSkills,remember_verified_owned
 from owner_hunt_rules_candidate import configured_identity
 from owner_skill_ui import SkillUI
 progress=state(adapter)
 if type(progress.level) is not int or progress.level<30:return 'level_wait'
 start=time.monotonic();read_power(adapter,context,inputs);progress=state(adapter)
 if not progress.character or progress.observed<start or type(progress.level) is not int or progress.level<30:raise Pending('상자 확인 전 캐릭터·레벨 재확인 필요')
 character=progress.character;profile=configured_identity(adapter.project.root);ledger=runtime_ledger(adapter,character)
 learned=LearnedSkills(adapter.project.root,ledger.receipt_key)
 attested=SkillAttestation(adapter.project.root,ledger.receipt_key)
 if all(learned.known(name) for name in SKILLS) and attested.known():return 'all_known'
 cooldown=getattr(adapter,'_owner_starter_scan',None)
 if cooldown and cooldown[0] is context and cooldown[1]==ledger.receipt_key and time.monotonic()-cooldown[2]<600:return 'scan_wait'
 ui=SkillUI(adapter,context,inputs)
 _enable_owned_icon_fallback(ui)
 try:
  try:owned=ui.scan_owned()
  except _RequiredSkillsFound as done:owned=done.owned
  except Pending as exc:
   # List names are too small to agree on every read, and an empty page used to end the check.
   LOG.info('보유 도술 이름 판독 보류 · 아이콘으로 끝까지 확인 · %s',exc)
   owned=_icons_to_end(ui,Pending)
  if not owned_filter_proved(ui):raise Pending('보유 도술 전용 필터 확인 필요')
  adapter._owner_starter_owned=(context,set(owned))
 finally:
  try:ui.close_known()
  except Exception as exc:raise ChoiceNavigationError('도술 화면을 닫고 일반 화면으로 돌아왔는지 확인 필요') from exc
 context.checkpoint()
 current=state(adapter)
 if current.character!=character or configured_identity(adapter.project.root)!=profile:raise Pending('도술 판독 중 캐릭터 변경')
 remember_verified_owned(ledger,owned)
 adapter._owner_starter_scan=(context,ledger.receipt_key,time.monotonic())
 learned=LearnedSkills(adapter.project.root,ledger.receipt_key)
 if {68,84,89}.issubset(owned):
  attested.record(owned)
  LOG.info('선택상자 도술 3종 보유 확인 · 도술 상자 생략');return 'all_known'
 LOG.info('선택상자 도술 미확인 · 보유 목록에 없는 항목을 미학습으로 단정하지 않음')
 return 'unknown'

def open_chosen_manual(adapter,context,inputs):
 """The 강화 요령서 box follows the setting; nothing is opened until one is picked."""
 from owner_progression import state
 from owner_skill_goal import runtime_ledger
 from owner_hunt_rules_candidate import configured_identity
 from owner_skill_ui import SkillUI
 from owner_skill_box import open_manuals
 if getattr(adapter,'_owner_manual_checked',None) is context:return
 progress=state(adapter)
 if not progress.character or type(progress.level) is not int or progress.level<30:return
 style=Choices(adapter.project.root,configured_identity(adapter.project.root)).snapshot()[0].get('manual')
 if not style:return
 result=open_manuals(SkillUI(adapter,context,inputs),runtime_ledger(adapter,progress.character),style)
 adapter._owner_manual_checked=context
 LOG.info('요령서 상자 · %s · %s',style,result)

def install(gui):
 """Wrap the already installed inventory path; never replace its behavior."""
 from project_adapter import market_inventory
 from project_adapter._entry import Adapter
 from owner_skill_goal import Pending
 if getattr(gui,'_owner_starter_choice_installed',False):return
 replacements=[]
 def wrap(original):
  if getattr(original,'_owner_starter_choice',False):return original
  @wraps(original)
  def run(adapter,context,inputs,*args,**kwargs):
   if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return False
   if getattr(LOCAL,'active',False):return original(adapter,context,inputs,*args,**kwargs)
   LOCAL.active=True
   try:
    skip_generation=getattr(adapter,'_owner_inventory_skip_generation',0)
    result=original(adapter,context,inputs,*args,**kwargs)
    if result is not False and getattr(adapter,'_owner_inventory_skip_generation',0)==skip_generation:
     from owner_schedule_priority import LOCAL as priority
     previous=getattr(priority,'feature',None);priority.feature='선택 상자 확인'
     try:
      context.checkpoint()
      try:
       result_scan=scan_learned(adapter,context,inputs)
       if result_scan=='unknown':
        from owner_coupon_skills_candidate import process
        process(adapter,context,inputs)
      except (Pending,OSError,ValueError) as exc:LOG.info('선택상자 도술 확인 보류 · %s',str(exc))
      try:open_chosen_manual(adapter,context,inputs)
      except (Pending,OSError,ValueError) as exc:LOG.info('요령서 상자 확인 보류 · %s',str(exc))
     finally:priority.feature=previous
    return result
   finally:LOCAL.active=False
  run._owner_starter_choice=True;return run
 current=market_inventory.run_inventory_use;replacements.append((current,wrap(current)))
 for module in tuple(m for name,m in sys.modules.items() if name.startswith('project_adapter') and m is not None):
  for name,value in tuple(vars(module).items()):
   if value is current:setattr(module,name,replacements[0][1])
 original=getattr(Adapter,'run_inventory_use',None)
 if callable(original):Adapter.run_inventory_use=wrap(original)
 gui._owner_starter_choice_installed=True
