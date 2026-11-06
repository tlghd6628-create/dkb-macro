"""Confirmed native hunting deaths and per-character route holds."""
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
import hashlib,json,logging,threading,time

LOG=logging.getLogger('project_gui.DKB')
SLEEP_OFF=True   # user 11-06: hunting needs no sleep mode
LOCAL=threading.local()

class HuntMemory:
 def __init__(self,root,character):
  if not character:raise ValueError('사냥 기록 캐릭터 확인 필요')
  from owner_hunt_rules_candidate import configured_identity
  self.path=Path(root)/'settings/owner-hunt-history.json'
  raw=json.dumps([configured_identity(root),character],ensure_ascii=False,separators=(',',':')).encode()
  self.identity=hashlib.sha256(raw).hexdigest()
 def read(self):
  if not self.path.exists():return {'version':1,'characters':{}}
  obj=json.loads(self.path.read_text(encoding='utf-8-sig'))
  if not isinstance(obj,dict) or obj.get('version')!=1 or not isinstance(obj.get('characters'),dict):raise ValueError('사냥 사망 기록 형식 확인 필요')
  return obj
 def rows(self):return self.read()['characters'].get(self.identity,{})
 def blocked(self,key,power):
  row=self.rows().get(key,{})
  if row.get('deaths',0)<2:return False
  base=row.get('power')
  return not (type(power) is int and type(base) is int and base>0 and power>=int(__import__('math').ceil(base*1.15)))
 def died(self,key,power):
  from owner_timetable import save
  doc=self.read();rows=doc['characters'].setdefault(self.identity,{})
  old=rows.get(key,{});count=int(old.get('deaths',0))
  if count>=2 and not self.blocked(key,power):count=0
  count+=1;rows[key]={'deaths':count,'power':None,'last_observed_power':power if type(power) is int and power>0 else None,'at':time.time()}
  save(self.path,doc)
  return count
 def accept_fresh(self,power,observed_epoch):
  if type(power) is not int or power<=0:return
  from owner_timetable import save
  doc=self.read();changed=False
  for row in doc['characters'].get(self.identity,{}).values():
   if row.get('deaths',0)>=2 and row.get('power') is None and observed_epoch>=row.get('at',float('inf')):
    row['power']=power;row['baseline_source']='fresh_after_death';changed=True
  if changed:save(self.path,doc)

def memory(adapter):
 from owner_progression import state
 progress=state(adapter);book=HuntMemory(adapter.project.root,progress.character)
 age=time.monotonic()-progress.observed
 if 0<=age<=3:book.accept_fresh(progress.power,time.time()-age)
 return book

def saved_key(rule):return 'slot:'+str(rule['slot'])+'@'+str(rule['power'])

def blocked_saved(adapter,rule,power):
 progress=getattr(adapter,'_owner_progression',None)
 if not progress or not progress.character:return False
 return memory(adapter).blocked(saved_key(rule),power)

def guide_excluded(adapter,power):
 from owner_progression import state
 if not state(adapter).character:return set()
 book=memory(adapter)
 return {int(k.split(':',1)[1]) for k in book.rows() if k.startswith('guide:') and k.split(':',1)[1].isdigit() and book.blocked(k,power)}

def set_route(adapter,key,label):
 adapter._owner_actual_hunt_route={'key':key,'label':label}

def record_death(adapter):
 from owner_progression import state
 route=getattr(adapter,'_owner_actual_hunt_route',None);progress=state(adapter)
 if not route or not progress.character:return None
 count=memory(adapter).died(route['key'],progress.power)
 LOG.warning('사냥터 사망 기록 · %s · %d회%s',route['label'],count,' · 추천 사냥터로 변경' if count>=2 else '')
 if count>=2:adapter._owner_hunt_fallback_due=True
 return count

def apply_fallback(adapter,context,inputs):
 if not getattr(adapter,'_owner_hunt_fallback_due',False):return False
 context.checkpoint()
 from owner_hunt import run
 result=run(adapter,context,inputs)
 if result is not True:raise RuntimeError('사망 2회 이후 추천 사냥터 도착 확인 필요')
 adapter._owner_hunt_fallback_due=False
 return True

@contextmanager
def active_hunt(adapter,context,inputs):
 old=getattr(LOCAL,'owner',None);LOCAL.owner=(adapter,context,inputs)
 try:yield
 finally:LOCAL.owner=old

def install(gui):
 if getattr(gui,'_owner_hunt_memory',False):return
 from project_adapter import reservations,sleep_mode
 import sys
 original=reservations.wait_reservations
 @wraps(original)
 def waiting(adapter,context,periodic=None,inputs=None):
  if inputs is None or adapter.mode!='auto_mode':return original(adapter,context,periodic=periodic,inputs=inputs)
  def tick(*args,**kwargs):
   context.checkpoint()
   apply_fallback(adapter,context,inputs)
   return periodic(*args,**kwargs) if periodic else True
  with active_hunt(adapter,context,inputs):return original(adapter,context,periodic=tick,inputs=inputs)
 reservations.wait_reservations=waiting
 for name,module in tuple(sys.modules.items()):
  if module is None or not name.startswith(('project_adapter','owner_')):continue
  for key,value in tuple(vars(module).items()):
   if value is original:setattr(module,key,waiting)
 cls=sleep_mode.SleepModeActions;old_exit=cls.exit_sleep_mode;old_enter=cls.enter_sleep_mode
 @wraps(old_exit)
 def exit_sleep(actions,death_confirmed=False,**kwargs):
  result=old_exit(actions,death_confirmed=death_confirmed,**kwargs)
  owner=getattr(LOCAL,'owner',None)
  if owner and death_confirmed is True and result is not False:
   adapter,context,inputs=owner
   from owner_task_flow import LOCAL as task
   if not getattr(adapter,'_owner_temporary_work',None) and not getattr(task,'servicing',False) and not getattr(adapter,'_owner_hunt_death_latched',False):
    context.checkpoint();record_death(adapter);adapter._owner_hunt_death_latched=True
  return result
 @wraps(old_enter)
 def enter_sleep(actions,*args,**kwargs):
  owner=getattr(LOCAL,'owner',None)
  if SLEEP_OFF:
   # User 11-06: no sleep mode while hunting. The hunt goes on as after a failed entry, death watch included.
   import time
   if time.monotonic()-getattr(enter_sleep,'noted',-1e9)>=600:
    enter_sleep.noted=time.monotonic();__import__('logging').getLogger('project_gui.DKB').info('절전모드 사용 안 함 · 필드에서 사냥 계속')
   if owner:
    from owner_boss_range import pending,restore
    if pending(owner[0].project.root):restore(*owner)
    from owner_camera import zoom_once
    zoom_once(*owner)
   return False
  # The last normal screen before sleeping: finish a boss range restore left undone.
  if owner:
   from owner_boss_range import pending,restore
   if pending(owner[0].project.root):restore(*owner)
   from owner_camera import zoom_once
   zoom_once(*owner)
   from owner_worn_stats import refresh_when_stale
   refresh_when_stale(*owner)
  result=old_enter(actions,*args,**kwargs);owner=getattr(LOCAL,'owner',None)
  if owner and result is not False:owner[0]._owner_hunt_death_latched=False
  return result
 cls.exit_sleep_mode=exit_sleep;cls.enter_sleep_mode=enter_sleep
 gui._owner_hunt_memory=True
