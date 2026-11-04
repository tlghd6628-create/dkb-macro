"""Guarded general-to-rare changes with durable exact-item confirmation.

UI readers are provided by owner_equipment_tooltip_candidate. Importing this
module performs no game input. A cached slot/grade never authorizes a change.
"""
from pathlib import Path
import hashlib,json,math,os,tempfile,threading,time,uuid

SLOTS=('무기','팔찌','반지','투구','허리띠','신발','장갑','갑옷','다리','귀걸이','목걸이')
class Hold(RuntimeError):pass

def _key(value):
 if not isinstance(value,str) or not value.strip():raise Hold('캐릭터 또는 장비 식별 정보 확인 필요')
 return value.strip()

class Journal:
 def __init__(self,root,character):
  identity=_key(character)
  name=hashlib.sha256(identity.encode('utf8')).hexdigest()[:24]
  self.path=Path(root)/'settings'/('owner-equip-upgrade-'+name+'.json')
  self.identity=identity
 def _under_lock(self,operation):
  import msvcrt
  self.path.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(str(self.path)+'.lock',os.O_RDWR|os.O_CREAT,0o600)
  try:
   if os.fstat(fd).st_size==0:os.write(fd,b'0')
   os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
  except OSError as exc:os.close(fd);raise Hold('장비 교체 기록 사용 중') from exc
  try:return operation()
  finally:
   os.lseek(fd,0,os.SEEK_SET)
   try:msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
   finally:os.close(fd)
 def read(self):
  if not self.path.exists():return {'version':1,'character':self.identity,'pending':None,'completed':[]}
  try:
   result=json.loads(self.path.read_text(encoding='utf8'))
   if not isinstance(result,dict) or result.get('version')!=1 or result.get('character')!=self.identity or not isinstance(result.get('completed'),list) or 'pending' not in result:raise ValueError()
   entry=result['pending']
   if entry is not None and (not isinstance(entry,dict) or entry.get('phase') not in ('prepared','sent') or not isinstance(entry.get('proof'),dict)):raise ValueError()
   return result
  except (ValueError,OSError,TypeError):raise Hold('장비 교체 기록 확인 필요')
 def _write(self,result):
  fd,tmp=tempfile.mkstemp(prefix='.equip-upgrade-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 def prepare(self,proof):
  def action():
   data=self.read()
   if data['pending'] is not None:raise Hold('이전 장비 교체 결과 확인 필요')
   data['pending']={'phase':'prepared','proof':proof};self._write(data)
  self._under_lock(action)
 def mark_sent(self):
  def action():
   data=self.read();entry=data['pending']
   if not entry or entry.get('phase')!='prepared':raise Hold('장비 교체 준비 기록 확인 필요')
   entry['phase']='sent';self._write(data)
  self._under_lock(action)
 def abort_prepared(self):
  def action():
   data=self.read();entry=data['pending']
   if entry and entry.get('phase')=='prepared':data['pending']=None;self._write(data)
  self._under_lock(action)
 def complete(self,proof,*,verified_as='same_item',result_frame_ids=None):
  def action():
   data=self.read();entry=data['pending']
   if not entry or entry.get('phase')!='sent' or entry['proof']!=proof:raise Hold('장비 교체 결과 기록 불일치')
   if verified_as not in ('same_item','slot_and_grade'):raise Hold('장비 확인 방식 오류')
   record=dict(proof,verified_as=verified_as)
   if verified_as=='slot_and_grade' or result_frame_ids is not None:
    if not isinstance(result_frame_ids,list) or len(result_frame_ids)!=2 or any(not isinstance(x,str) or not x for x in result_frame_ids) or result_frame_ids[0]==result_frame_ids[1]:raise Hold('착용 결과 증거 확인 필요')
    record.update(growth_request_id=uuid.uuid4().hex,growth_state='pending',result_frame_ids=list(result_frame_ids))
   if verified_as=='same_item' and result_frame_ids is not None:
    slots=data.setdefault('observed_slots',{})
    if isinstance(slots,dict):slots[proof['slot']]={'grade':proof.get('candidate_grade','희귀'),'item':proof['candidate_item'],'at':time.time(),'frame_ids':list(result_frame_ids)}
   data['completed'].append(record);data['pending']=None;self._write(data)
  self._under_lock(action)
 def remember_pair(self,first,second,*,clock=time.monotonic):
  """Persist display/scan hints only; never authorize an equipment input."""
  fields=('character','slot','current_grade','current_item','candidate_grade','candidate_item')
  if (not isinstance(first,dict) or not isinstance(second,dict) or any(first.get(k)!=second.get(k) for k in fields)
      or first.get('character')!=self.identity or first.get('slot') not in SLOTS
      or any(row.get('verified') is not True or row.get('identity_core_verified') is not True for row in (first,second))):return False
  now=clock()
  if any(type(row.get('captured_at')) not in (int,float) or not 0<=now-row['captured_at']<=2 for row in (first,second)):return False
  if first.get('frame_id')==second.get('frame_id') or second['captured_at']<=first['captured_at']:return False
  if any(first.get(k) not in ('일반','희귀','영웅') for k in ('current_grade','candidate_grade')):return False
  try:
   token=json.loads(first['candidate_item']);icon=token['icon_rgb']
   import base64
   if len(base64.b64decode(icon,validate=True))!=20*20*3:return False
  except (ValueError,TypeError,KeyError):return False
  def write():
   data=self.read();slots=data.setdefault('observed_slots',{});catalog=data.setdefault('candidate_catalog',{})
   if not isinstance(slots,dict) or not isinstance(catalog,dict):return False
   slots[first['slot']]={'grade':first['current_grade'],'item':first['current_item'],'at':time.time(),'frame_ids':[first['frame_id'],second['frame_id']]}
   key=hashlib.sha256((first['slot']+first['candidate_grade']+icon).encode()).hexdigest()
   catalog[key]={'slot':first['slot'],'grade':first['candidate_grade'],'icon_rgb':icon,'at':time.time()}
   if len(catalog)>128:
    for old in sorted(catalog,key=lambda k:catalog[k].get('at',0))[:-128]:del catalog[old]
   self._write(data);return True
  return self._under_lock(write)
 def growth_request(self):
  data=self.read()
  for row in data['completed']:
   if (isinstance(row,dict) and row.get('verified_as') in ('same_item','slot_and_grade') and row.get('growth_state')=='pending'
       and isinstance(row.get('growth_request_id'),str) and row.get('character')==self.identity
       and row.get('slot') in SLOTS and row.get('candidate_grade','희귀') in ('일반','희귀')
       and isinstance(row.get('frame_ids'),list) and len(row['frame_ids'])==2
       and all(isinstance(x,str) and x for x in row['frame_ids']) and row['frame_ids'][0]!=row['frame_ids'][1]
       and isinstance(row.get('result_frame_ids'),list) and len(row['result_frame_ids'])==2
       and all(isinstance(x,str) and x for x in row['result_frame_ids']) and len(set(row['frame_ids']+row['result_frame_ids']))==4):
    return dict(row)
  return None
 def mark_growth_dispatched(self,request_id):
  def action():
   data=self.read();matches=[row for row in data['completed'] if isinstance(row,dict) and row.get('growth_request_id')==request_id and row.get('growth_state') in ('pending','dispatching_unverified') and row.get('character')==self.identity and row.get('verified_as') in ('same_item','slot_and_grade')]
   if len(matches)!=1:raise Hold('장비 강화 요청 기록 확인 필요')
   matches[0]['growth_state']='dispatched_unverified';self._write(data)
  self._under_lock(action)
 def claim_growth_dispatch(self,request_id):
  """Durably claim ONE immediate visit before its native growth call.

  If execution is interrupted, ordinary timed growth will re-read the item.
  The immediate request is not replayed and this never claims enhancement0
  or successful growth, nor clears a resource input pending elsewhere.
  """
  def action():
   data=self.read();request=self.growth_request()
   if not request or request.get('growth_request_id')!=request_id:raise Hold('장착 후 성장 요청이 바뀌어 재확인 필요')
   matches=[row for row in data['completed'] if isinstance(row,dict) and row.get('growth_request_id')==request_id]
   if len(matches)!=1:raise Hold('장착 후 성장 요청 중복 확인 필요')
   matches[0].update(growth_state='dispatching_unverified',growth_dispatched_at_epoch=time.time());self._write(data)
  self._under_lock(action)

def paired(first,second,*,clock=time.monotonic):
 """Require independent fresh, exact identity and grade evidence."""
 if not isinstance(first,dict) or not isinstance(second,dict):raise Hold('장비 비교 화면 필요')
 now=clock();fields=('character','slot','current_item','current_grade','candidate_item','candidate_grade','target_bounds')
 for row in (first,second):
  if row.get('verified') is not True:raise Hold('장비 비교 판독 미확인')
  _key(row.get('frame_id'))
  t=row.get('captured_at')
  if type(t) not in (int,float) or not math.isfinite(t) or not 0<=now-t<=2:raise Hold('장비 비교 화면 만료')
 if first['frame_id']==second['frame_id'] or any(first.get(k)!=second.get(k) for k in fields):raise Hold('두 화면의 장비 정보 불일치')
 character=_key(first.get('character'));current=_key(first.get('current_item'));candidate=_key(first.get('candidate_item'))
 if first.get('slot') not in SLOTS or first.get('current_grade')!='일반' or first.get('candidate_grade')!='희귀':raise Hold('일반→희귀 교체 대상 아님')
 bounds=first.get('target_bounds')
 if not isinstance(bounds,(tuple,list)) or len(bounds)!=4 or any(type(v) is not int for v in bounds):raise Hold('장착 위치 미확인')
 x1,y1,x2,y2=bounds
 if not 0<=x1<x2<=897 or not 0<=y1<y2<=479:raise Hold('장착 위치 범위 오류')
 if second['captured_at']<=first['captured_at']:raise Hold('장비 비교 화면 순서 확인 필요')
 return {'character':character,'slot':first['slot'],'current_item':current,'candidate_item':candidate,
         'current_grade':first['current_grade'],'candidate_grade':first['candidate_grade'],
         'target_bounds':list(bounds),'frame_ids':[first['frame_id'],second['frame_id']],
         'captured_at':second['captured_at']}

def paired_initial(first,second,*,allowed_items,clock=time.monotonic):
 """Plan one initial item only after the exact slot is proven empty twice.

 ``allowed_items`` is the explicit user-authorized item/slot set, never a
 list inferred from image colour. Its real reader is not yet implemented.
 """
 if not isinstance(allowed_items,(set,frozenset)) or not allowed_items:raise Hold('초기 장비 허용 목록 확인 필요')
 if not isinstance(first,dict) or not isinstance(second,dict):raise Hold('초기 장비 두 화면 필요')
 now=clock();fields=('character','slot','empty','candidate_item','candidate_grade','target_bounds')
 for row in (first,second):
  if row.get('verified') is not True:raise Hold('초기 장비 판독 미확인')
  _key(row.get('frame_id'));t=row.get('captured_at')
  if type(t) not in (int,float) or not math.isfinite(t) or not 0<=now-t<=2:raise Hold('초기 장비 화면 만료')
 if first['frame_id']==second['frame_id'] or second['captured_at']<=first['captured_at'] or any(first.get(k)!=second.get(k) for k in fields):raise Hold('초기 장비 두 화면 불일치')
 character=_key(first.get('character'));slot=first.get('slot');candidate=_key(first.get('candidate_item'))
 if slot not in SLOTS or first.get('empty') is not True or first.get('candidate_grade') not in ('일반','희귀') or (slot,candidate) not in allowed_items:raise Hold('초기 장비 착용 조건 미충족')
 bounds=first.get('target_bounds')
 if not isinstance(bounds,(tuple,list)) or len(bounds)!=4 or any(type(v) is not int for v in bounds):raise Hold('초기 장비 입력 위치 미확인')
 x1,y1,x2,y2=bounds
 if not 0<=x1<x2<=897 or not 0<=y1<y2<=479:raise Hold('초기 장비 위치 범위 오류')
 return {'character':character,'slot':slot,'current_item':None,'candidate_item':candidate,
         'candidate_grade':first['candidate_grade'],'target_bounds':list(bounds),
         'frame_ids':[first['frame_id'],second['frame_id']],'captured_at':second['captured_at']}

def run_once(context,journal,read_pair,final_proof,click,*,clock=time.monotonic,initial_allowed=None):
 """Run one caller-provided verified click; no next attempt without result."""
 if not all(callable(v) for v in (read_pair,final_proof,click)):raise Hold('장비 화면 판독기 미구현')
 worker=threading.get_ident();context.checkpoint()
 if journal.read()['pending'] is not None:raise Hold('이전 장비 교체 결과 확인 필요')
 first,second=read_pair()
 proof=paired(first,second,clock=clock) if initial_allowed is None else paired_initial(first,second,allowed_items=initial_allowed,clock=clock)
 if proof['character']!=journal.identity:raise Hold('장비 교체 캐릭터 불일치')
 journal.prepare(proof)
 try:
  context.checkpoint()
  if threading.get_ident()!=worker or final_proof(proof) is not True:raise Hold('입력 직전 장비 비교 재확인 필요')
  context.checkpoint();journal.mark_sent();context.checkpoint()
  click(proof['target_bounds']);return 'pending_confirmation'
 finally:journal.abort_prepared()

def confirm(context,journal,read_result,*,clock=time.monotonic):
 """Require two new verified frames showing the exact candidate now worn."""
 context.checkpoint();entry=journal.read()['pending']
 if not entry or entry.get('phase')!='sent':raise Hold('확인할 장비 교체 기록 없음')
 a,b=read_result();now=clock();proof=entry['proof']
 if not isinstance(a,dict) or not isinstance(b,dict):raise Hold('착용 결과 미확인')
 for row in (a,b):
  t=row.get('captured_at')
  if row.get('verified') is not True or type(t) not in (int,float) or not math.isfinite(t) or not 0<=now-t<=2 or t<=proof['captured_at']:raise Hold('착용 결과 화면 미확인')
  _key(row.get('frame_id'))
  expected_grade=proof.get('candidate_grade','희귀')
  if row.get('character')!=proof['character'] or row.get('slot')!=proof['slot'] or row.get('item')!=proof['candidate_item'] or row.get('grade')!=expected_grade or row.get('worn') is not True:raise Hold('교체된 장비 착용 미확인')
 if a['frame_id']==b['frame_id'] or set(proof['frame_ids'])&{a['frame_id'],b['frame_id']} or b['captured_at']<=a['captured_at']:raise Hold('서로 다른 새 결과 화면 필요')
 journal.complete(proof,result_frame_ids=[a['frame_id'],b['frame_id']]);return 'confirmed'

def confirm_category(context,journal,read_result,*,clock=time.monotonic):
 """Confirm same slot and desired grade worn, without claiming instance ID."""
 context.checkpoint();entry=journal.read()['pending']
 if not entry or entry.get('phase')!='sent':raise Hold('확인할 장비 교체 기록 없음')
 a,b=read_result();now=clock();proof=entry['proof'];grade=proof.get('candidate_grade','희귀')
 if not isinstance(a,dict) or not isinstance(b,dict):raise Hold('착용 결과 미확인')
 for row in (a,b):
  t=row.get('captured_at')
  if row.get('verified') is not True or type(t) not in (int,float) or not math.isfinite(t) or not 0<=now-t<=2 or t<=proof['captured_at']:raise Hold('착용 결과 화면 미확인')
  _key(row.get('frame_id'))
  if row.get('character')!=proof['character'] or row.get('slot')!=proof['slot'] or row.get('grade')!=grade or row.get('worn') is not True:raise Hold('교체 부위·등급 착용 미확인')
 if a['frame_id']==b['frame_id'] or set(proof['frame_ids'])&{a['frame_id'],b['frame_id']} or b['captured_at']<=a['captured_at']:raise Hold('서로 다른 새 결과 화면 필요')
 journal.complete(proof,verified_as='slot_and_grade',result_frame_ids=[a['frame_id'],b['frame_id']]);return 'confirmed_category'
