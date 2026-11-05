"""Single-worker energy box adapter. Candidate; receipt OCR not yet proved."""
from pathlib import Path
import json,logging,queue,threading,time,uuid
from PIL import Image
from owner_energy_box_runtime_candidate import Hold
from owner_energy_box_detail_candidate import detail,detail_screen,generic_box_detail,box_candidates,stable_box_candidates
from owner_energy_choice_reader_candidate import read_pair,read_open_pair,layout_screen

class Port:
 def __init__(self,adapter,context,inputs):
  from project_adapter import market_inventory
  from project_adapter.town_services import TownServices
  self.adapter=adapter;self.context=context;self.service=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES)
  self.opened=False;self.last_target=None;self.view='field';self.inventory_reference=None;self._last_pair=None
 def pair(self,reader):
  self.context.checkpoint();self.service.check();a=self.service.capture().copy();ta=time.monotonic()
  self.context.wait(.12);self.context.checkpoint();self.service.check();b=self.service.capture().copy();tb=time.monotonic()
  if tb-ta>2.5:return None
  value=reader(a,b)
  if value is None:return None
  self._last_pair=(a,b)
  return value,[uuid.uuid4().hex,uuid.uuid4().hex],[ta,tb]
 def same_inventory_background(self,frame):
  """Strict evidence for a previously observed, unoccluded inventory.

  Any changed central pixel blocks the ambiguous recovery path, rather than
  treating a new unknown overlay as a normal screen. Moving scenery can hold.
  """
  import numpy as np
  refs=getattr(self,'inventory_reference',None)
  if not refs or getattr(frame,'shape',None)!=(479,897,3):return False
  crop=frame[30:416,205:700]
  return any(np.array_equal(crop,ref[30:416,205:700]) for ref in refs)
 def wait_pair(self,reader,seconds=3):
  end=time.monotonic()+seconds
  while True:
   result=self.pair(reader)
   if result is not None:return result
   if time.monotonic()>=end:return None
   self.context.wait(.15)
 def ensure_inventory(self):
  """Idempotent navigation: an already-open inventory is not toggled again."""
  from owner_progression import inventory_parts,open_inventory_by_key
  def opened(a,b):
   return True if all(inventory_parts(f)==(True,True) and not generic_box_detail(f) and not layout_screen(f) for f in (a,b)) else None
  if self.pair(opened):return True
  # Reuse the original I path, which also normalizes a proved partial panel.
  if open_inventory_by_key(self.service) is False:return False
  return self.wait_pair(opened) is not None
 def click(self,x,y,guard,predicate,on_sent=None):
  self.context.checkpoint();self.service.check()
  first=self.service.capture();t=time.monotonic();self.context.wait(.12)
  self.context.checkpoint();self.service.check();second=self.service.capture()
  if time.monotonic()-t>2.5 or guard() is not True or not predicate(first) or not predicate(second):raise Hold('상자 입력 직전 화면 변경')
  if on_sent is not None:on_sent()
  self.service.click_hit((x,y,(x-4,y-4,x+5,y+5)));self.context.wait(.2)
 def open_detail(self,guard):
  from project_adapter import market_inventory
  if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
  if self.ensure_inventory() is False:raise Hold('인벤토리 열기 확인 필요')
  self.opened=True;self.view='inventory'
  pair=self.pair(stable_box_candidates)
  if not pair:raise Hold('기운 선택상자 아이콘 확인 필요')
  self.inventory_reference=tuple(f.copy() for f in self._last_pair)
  def same_detail(a,b):
   p,q=detail(a),detail(b)
   return p if p is not None and p==q else None
  count=None
  for x,y in pair[0][:5]:
   self.click(x,y,guard,lambda f:(x,y) in (box_candidates(f) or ()),on_sent=lambda:setattr(self,'view','pending_detail'))
   shown=self.pair(same_detail)
   if shown:count=shown[0];self.view='detail';break
   generic=self.pair(lambda a,b:True if generic_box_detail(a) and generic_box_detail(b) else None)
   if not generic:raise Hold('상자 상세 화면 확인 필요')
   self.view='detail'
   self.click(510,106,guard,generic_box_detail)
   self.view='inventory'
  if count is None:raise Hold('기운 상자 상세 및 개수 확인 필요')
  return count,shown
 def current_detail(self,guard):
  count,pair=self.open_detail(guard)
  return dict(verified=True,boxes=count,frame_ids=pair[1],captured_at=pair[2])
 def prepare_one(self,name,guard):
  count,_=self.open_detail(guard)
  self.click(450,363,guard,lambda f:detail(f)==count,on_sent=lambda:setattr(self,'view','pending_selection'))
  pair=self.wait_pair(read_open_pair)
  if not pair:raise Hold('기운 선택 화면 확인 필요')
  self.view='selection'
  state=pair[0]
  if state.get('available_count')!=count or state.get('quantity')!=1:raise Hold('상자 수량 일치 확인 필요')
  if state.get('selected')!=name:
   index=('생명','여명','몽환','홍염').index(name);y=(152,188,224,260)[index]+17
   def old_screen(f):return read_open_pair(f,f.copy())==state
   self.click(450,y,guard,old_screen)
   pair=self.wait_pair(read_pair)
   if not pair:raise Hold('선택 후 기운 확인 필요')
   state=pair[0]
  if state.get('selected')!=name or state.get('quantity')!=1 or state.get('available_count')!=count:raise Hold('선택 기운·수량 확인 필요')
  self.last_target=name;self.expected_boxes_before=count
  return dict(verified=True,name=name,quantity=1,boxes=count,detail_boxes=count,frame_ids=pair[1],captured_at=pair[2])
 def submit(self,before,mark_sent,guard):
  self.context.checkpoint();self.service.check();pair=self.pair(read_pair)
  wanted=before.get('quantity')
  if type(wanted) is not int or not 1<=wanted<=before['boxes']:raise Hold('확정할 상자 수량 확인 필요')
  if not pair or pair[0].get('selected')!=before['name'] or pair[0].get('quantity')!=wanted or pair[0].get('available_count')!=before['boxes'] or guard() is not True:
   raise Hold('확정 직전 선택 상태 재확인 필요')
  # No guessed result: a possible delivery remains durable sent/pending.
  mark_sent();self.context.checkpoint();self.service.check()
  if guard() is not True:raise Hold('확정 전 설정 변경')
  state=pair[0]
  def matches(f):return read_pair(f,f.copy())==state
  self.click(449,356,guard,matches,on_sent=lambda:setattr(self,'view','pending_receipt'))
 def receipt(self,name,guard):
  # Capture promptly on the existing owning worker. Disk encoding/writing is
  # bounded and separate; it never calls game input or game capture itself.
  # Until toast+box-count readers are validated, the sent intent stays pending.
  expected=getattr(self,'expected_quantity',1)
  if type(expected) is not int or expected<1:raise Hold('수령할 상자 수량 확인 필요')
  root=Path(self.adapter.project.root)/'logs'/'energy-claim-evidence'/uuid.uuid4().hex
  root.mkdir(parents=True,exist_ok=True)
  pending=queue.Queue(maxsize=32);records=[];errors=[];finished=threading.Event();rewards=[];detail_rows=[]
  def write_frames():
   while True:
    try:job=pending.get(timeout=.1)
    except queue.Empty:
     if finished.is_set():break
     continue
    row,frame=job
    try:Image.fromarray(frame).save(root/row['file']);row['saved']=True
    except Exception as exc:row['saved']=False;errors.append(type(exc).__name__)
   try:(root/'capture-manifest.json').write_text(json.dumps({'version':2,'target':name,'quantity':expected,'operation_id':getattr(self,'operation_id',None),'identity':getattr(self,'evidence_identity',None),'frames':records,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
   except OSError:logging.getLogger('project_gui.DKB').exception('기운 수령 자료 목록 저장 실패')
  worker=threading.Thread(target=write_frames,name='dkb-energy-evidence',daemon=True);worker.start()
  end=time.monotonic()+5;index=0
  try:
   while time.monotonic()<end and index<32:
    self.context.checkpoint();self.service.check();frame=self.service.capture().copy()
    row={'frame_id':uuid.uuid4().hex,'file':'after-%02d.png'%index,'captured_monotonic':time.monotonic(),'captured_at':time.time(),'saved':False}
    records.append(row)
    from owner_energy_reward_candidate import READERS,matches
    if name in READERS:
     from owner_energy_box_detail_candidate import evidence_detail
     from owner_ui_foreground import inventory_header
     character=(getattr(self,'evidence_identity',None) or {}).get('character')
     if character and inventory_header(frame,character) is not None:
      reward_now=matches(frame,name,expected)
      if reward_now:
       rewards.append(row);detail_rows=[]
      elif len(rewards)>=2 and evidence_detail(frame)==getattr(self,'expected_boxes_before',0)-expected:detail_rows.append(row)
    try:pending.put_nowait((row,frame))
    except queue.Full:errors.append('queue_full');break
    index+=1;self.context.wait(.18)
    if len(rewards)>=2 and len(detail_rows)>=2:break
  finally:
   finished.set()
   worker.join(timeout=2)
   if worker.is_alive():logging.getLogger('project_gui.DKB').warning('기운 수령 자료가 아직 저장 중입니다')
  if (worker.is_alive() or errors or guard() is not True or len(rewards)<2 or len(detail_rows)<2
      or not all(row.get('saved') is True for row in rewards[-2:]+detail_rows[-2:])):return None
  chosen=detail_rows[-2:];selected_rewards=rewards[-2:]
  if not (selected_rewards[0]['captured_at']<selected_rewards[1]['captured_at']<chosen[0]['captured_at']<chosen[1]['captured_at']):return None
  import hashlib
  evidence=selected_rewards+chosen
  self.view='detail'
  return {'verified':True,'name':name,'quantity':expected,'boxes':getattr(self,'expected_boxes_before',0)-expected,
          'toast_verified':True,'frame_ids':[r['frame_id'] for r in chosen],
          'captured_at':[r['captured_monotonic'] for r in chosen],
          'evidence_dir':root.name,'evidence_ids':[r['frame_id'] for r in evidence],
          'evidence_sha256':[hashlib.sha256((root/r['file']).read_bytes()).hexdigest() for r in evidence]}
 def close_known(self):
  if not self.opened:return
  from owner_equipment_boxes import close_inventory
  from owner_progression import inventory_parts
  self.context.checkpoint();self.service.check();frame=self.service.capture();strict_background=False
  selected=bool(layout_screen(frame))
  if selected:
   self.click(534,115,lambda:True,lambda f:bool(layout_screen(f)))
   # The dialog fades back into the box popup; reading at once saw neither and blocked the next job.
   self.view='inventory';self.context.wait(.8);frame=self.service.capture()
  if generic_box_detail(frame):
   self.click(510,106,lambda:True,generic_box_detail)
   self.view='inventory';frame=self.service.capture()
  elif self.view!='inventory':
   same=self.pair(lambda a,b:True if inventory_parts(a)==inventory_parts(b)==(True,True)
                  and not layout_screen(a) and not layout_screen(b)
                  and not generic_box_detail(a) and not generic_box_detail(b)
                  and self.same_inventory_background(a) and self.same_inventory_background(b) else None)
   if not same:raise RuntimeError('기운 상자 화면 위치가 불명확해 임무를 재개하지 않습니다')
   self.view='inventory';strict_background=True
  verified=self.pair(lambda a,b:True if inventory_parts(a)==inventory_parts(b)==(True,True) and not generic_box_detail(a) and not generic_box_detail(b) else None)
  if not verified:raise RuntimeError('인벤토리 상태를 확인하지 못했습니다')
  close_inventory(self.service)
  self.context.wait(.15);self.context.checkpoint();self.service.check()
  from owner_movement import field_hud
  # This is a read-only return-to-field proof. GenericPort.pair additionally
  # hashes the inventory-header name; that position contains the map name
  # after closing I, so using the resource-action reader here rejects every
  # otherwise-proved normal field. Inventory/selection actions above retain
  # their original per-character checks. No input is authorized by this pair.
  field=Port.pair(self,lambda a,b:True if inventory_parts(a)==inventory_parts(b)==(False,False)
                  and field_hud(a) and field_hud(b)
                  and (not strict_background or
                       (self.same_inventory_background(a) and self.same_inventory_background(b))) else None)
  if not field:raise RuntimeError('기운 상자 창 종료 후 일반 화면 확인 필요')
  self.opened=False;self.view='field'

def factory(adapter,context,inputs):return Port(adapter,context,inputs)
