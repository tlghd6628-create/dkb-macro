"""Proposed bounded balanced loop; never installed without validated readers."""
import time,uuid
from owner_energy_box_runtime_candidate import Hold,choose,proof

def abort_own_prepared(journal,expected):
 """Audit only this protocol's provably pre-input preparation; sent survives."""
 if (not isinstance(expected,dict) or expected.get('phase')!='prepared'
     or expected.get('protocol') not in ('energy-balanced-v2','energy-batch-v3')):return False
 state=journal.read()
 if state.get('pending')!=expected:return False
 op=expected.get('operation_id');ids=expected.get('before_frame_ids')
 if (not isinstance(op,str) or len(op)!=32 or any(c not in '0123456789abcdef' for c in op)
     or not isinstance(ids,list) or len(ids)!=2 or len(set(ids))!=2
     or type(expected.get('quantity')) is not int or type(expected.get('boxes_before')) is not int
     or not 1<=expected['quantity']<=expected['boxes_before']
     or (expected['protocol']=='energy-balanced-v2' and expected['quantity']!=1)):return False
 state['receipts'].append({'operation_id':op,'name':expected.get('name'),'quantity':0,'result':'preinput_aborted','at':time.time()})
 state['pending']=None;journal.save(state);return True

def run_balanced(port,journal,selected,*,guard,validated_targets,max_claims=3,max_seconds=30):
 if type(max_claims) is not int or not 1<=max_claims<=3 or type(max_seconds) not in (int,float) or not 0<max_seconds<=30:raise ValueError('기운 상자 실행 한도 확인 필요')
 if not isinstance(validated_targets,(set,frozenset)):raise Hold('검증된 수령 판독기 확인 필요')
 start=time.monotonic();completed=[]
 def bounded_guard():return guard() is True and time.monotonic()-start<max_seconds
 for _ in range(max_claims):
  if time.monotonic()-start>=max_seconds:return completed
  if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
  state=journal.read()
  if state['pending'] is not None:raise Hold('이전 상자 수령 결과 확인 필요')
  target=choose(selected,state)
  if target not in validated_targets:raise Hold('선택 기운 수령 판독 미검증')
  final=port.prepare_one(target,guard=bounded_guard)
  if (not proof(final) or final.get('name')!=target or final.get('quantity')!=1 or type(final.get('boxes')) is not int or final['boxes']<1
      or (final.get('detail_boxes')!=final['boxes'] and not (final.get('detail_boxes') is None and final.get('detail_identity') is True))):raise Hold('기운 상자 1개 선택 확인 필요')
  if guard() is not True or time.monotonic()-start>=max_seconds:raise Hold('시각 또는 설정 변경')
  state=journal.read()
  if state['pending'] is not None or choose(selected,state)!=target:raise Hold('기운 선택 순서 변경')
  operation=uuid.uuid4().hex
  state['pending']={'phase':'prepared','operation_id':operation,'name':target,'quantity':1,'boxes_before':final['boxes'],'before_frame_ids':list(final['frame_ids']),'protocol':'energy-balanced-v2','at':time.time()}
  journal.save(state);port.operation_id=operation
  def mark_sent():
   value=journal.read();pending=value.get('pending')
   if not pending or pending.get('phase')!='prepared' or pending.get('operation_id')!=operation or bounded_guard() is not True:raise Hold('확정 직전 설정 변경')
   pending['phase']='sent';journal.save(value)
  try:port.submit(final,mark_sent=mark_sent,guard=bounded_guard)
  finally:
   # Only our current protocol writes sent before the first commit input.
   # Cancellation before that boundary is audited as no-input, not receipt.
   latest=journal.read();pending=latest.get('pending')
   if pending and pending.get('operation_id')==operation:abort_own_prepared(journal,pending)
  after=port.receipt(target,guard=guard)
  state=journal.read();pending=state.get('pending')
  if (not pending or pending.get('operation_id')!=operation or pending.get('phase')!='sent' or guard() is not True
      or not proof(after) or after.get('name')!=target or after.get('quantity')!=1 or after.get('toast_verified') is not True
      or after.get('boxes')!=final['boxes']-1 or set(after['frame_ids'])&set(final['frame_ids'])
      or not isinstance(after.get('evidence_sha256'),list) or len(after['evidence_sha256'])!=4
      or not isinstance(after.get('evidence_ids'),list) or len(set(after['evidence_ids']))!=4):raise Hold('해당 기운 1개 수령 결과 확인 필요')
  state['confirmed'][target]+=1;state['pending']=None
  state['receipts'].append({'name':target,'quantity':1,'operation_id':operation,'frame_ids':list(after['frame_ids']),
                            'boxes_before':final['boxes'],'boxes_after':after['boxes'],
                            'evidence_dir':after.get('evidence_dir'),'evidence_ids':after['evidence_ids'],'sha256':after['evidence_sha256'],'at':time.time()})
  journal.save(state);completed.append(target)
  # Native inventory path expects a normal field before the next operation.
  # Unknown/Stop/close failures propagate rather than starting another claim.
  port.close_known()
 return completed
