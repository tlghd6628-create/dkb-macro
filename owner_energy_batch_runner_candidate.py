"""Durable per-energy grouped claims; every resource input is reconciled."""
import time,uuid
from owner_energy_allocation_candidate import NAMES,allocation,fingerprint,weights
from owner_energy_box_runtime_candidate import Hold,proof
from owner_energy_balanced_runner_candidate import abort_own_prepared

def ensure_plan(journal,settings,available):
 state=journal.read()
 if state['pending'] is not None:raise Hold('이전 묶음 수령 확인 필요')
 stamp=fingerprint(settings);old=state.get('energy_batch_plan')
 if old is not None:
  if (not isinstance(old,dict) or old.get('version')!=1 or not isinstance(old.get('remaining'),dict)
      or any(type(old['remaining'].get(n)) is not int or old['remaining'][n]<0 for n in NAMES)):
   raise Hold('저장된 기운 분배 계획 확인 필요')
  left=sum(old['remaining'].values())
  if old.get('weights')==stamp and left:
   if left==available:return old
   # Quests keep paying out boxes between batches, and a plan for the old count then held them all for good.
   if left<available:
    extra,rounding_after=allocation(available-left,settings,dict(state,energy_ratio_rounding=old.get('rounding_after')))
    for name in NAMES:
     old['remaining'][name]+=extra[name];old['allocated'][name]=old['allocated'].get(name,0)+extra[name]
    old['rounding_after']=rounding_after;old['boxes_before']=old.get('boxes_before',0)+available-left
    journal.save(state);return old
  history=state.setdefault('energy_batch_history',[])
  history.append(dict(old,archived_at=time.time(),reason='settings_changed' if old.get('weights')!=stamp else 'count_changed' if left else 'completed'))
  state['energy_batch_history']=history[-64:]
 values,rounding_after=allocation(available,settings,state)
 plan={'version':1,'id':uuid.uuid4().hex,'weights':stamp,'boxes_before':available,
       'allocated':dict(values),'remaining':dict(values),'rounding_after':rounding_after,'at':time.time()}
 state['energy_batch_plan']=plan;journal.save(state);return plan

def commit_result(state,pending):
 """Called only after independently verified quantity and stack decrement."""
 name,quantity=pending['name'],pending['quantity'];plan=state.get('energy_batch_plan')
 if (not isinstance(plan,dict) or plan.get('id')!=pending.get('plan_id')
     or plan.get('remaining',{}).get(name)!=quantity):raise Hold('묶음 수령과 분배 계획 연결 확인 필요')
 plan['remaining'][name]=0;state['confirmed'][name]+=quantity
 if sum(plan['remaining'].values())==0:
  plan['completed_at']=time.time();state['energy_ratio_rounding']=plan['rounding_after']

def run_batched(port,journal,settings,*,guard,validated_targets,max_batches=3,max_seconds=90):
 if type(max_batches) is not int or not 1<=max_batches<=3 or type(max_seconds) not in (int,float) or not 0<max_seconds<=120:
  raise ValueError('묶음 개봉 실행 한도 확인 필요')
 value=weights(settings);selected={n for n in NAMES if value[n]>0}
 if not selected:return []
 if not selected.issubset(validated_targets):raise Hold('선택한 기운의 묶음 수령 판독 확인 필요')
 start=time.monotonic();done=[]
 def active():return guard() is True and time.monotonic()-start<max_seconds
 for _ in range(max_batches):
  if not active():return done
  if journal.read()['pending'] is not None:raise Hold('이전 묶음 수령 결과 확인 필요')
  opened=port.open_selection(active)
  if not proof(opened) or type(opened.get('boxes')) is not int or opened['boxes']<1:raise Hold('기운 상자 잔량 확인 필요')
  plan=ensure_plan(journal,settings,opened['boxes'])
  target=next((n for n in NAMES if plan['remaining'][n]>0),None)
  if target is None:return done
  quantity=plan['remaining'][target]
  final=port.prepare_batch(target,quantity,active)
  if (not proof(final) or final.get('name')!=target or final.get('quantity')!=quantity
      or final.get('boxes')!=sum(plan['remaining'].values())
      or (final.get('detail_boxes')!=final['boxes'] and not (final.get('detail_boxes') is None and final.get('detail_identity') is True))):
   raise Hold('묶음 기운·수량·잔량 확인 필요')
  if not active():raise Hold('묶음 확정 전 시간 또는 설정 변경')
  state=journal.read()
  if state['pending'] is not None or state.get('energy_batch_plan')!=plan:raise Hold('묶음 분배 계획 변경')
  operation=uuid.uuid4().hex
  pending={'phase':'prepared','protocol':'energy-batch-v3','operation_id':operation,'plan_id':plan['id'],
           'name':target,'quantity':quantity,'boxes_before':final['boxes'],'before_frame_ids':list(final['frame_ids']),'at':time.time()}
  state['pending']=pending;journal.save(state);port.operation_id=operation
  def mark_sent():
   state=journal.read();item=state.get('pending')
   if not item or item!=pending or not active():raise Hold('묶음 확정 직전 기록 또는 설정 변경')
   item['phase']='sent';journal.save(state)
  try:port.submit(final,mark_sent=mark_sent,guard=active)
  finally:
   state=journal.read();item=state.get('pending')
   if item and item.get('operation_id')==operation:abort_own_prepared(journal,item)
  after=port.receipt(target,guard=guard)
  state=journal.read();pending=state.get('pending')
  if (not pending or pending.get('operation_id')!=operation or pending.get('phase')!='sent' or guard() is not True
      or not proof(after) or after.get('name')!=target or after.get('quantity')!=quantity
      or after.get('toast_verified') is not True or after.get('boxes')!=final['boxes']-quantity
      or set(after['frame_ids'])&set(final['frame_ids']) or not isinstance(after.get('evidence_sha256'),list)
      or len(after['evidence_sha256'])!=4 or not isinstance(after.get('evidence_ids'),list) or len(set(after['evidence_ids']))!=4):
   raise Hold('묶음 기운 수령 수량과 상자 차감 확인 필요')
  commit_result(state,pending)
  state['receipts'].append({'operation_id':operation,'plan_id':plan['id'],'name':target,'quantity':quantity,
    'boxes_before':final['boxes'],'boxes_after':after['boxes'],'frame_ids':list(after['frame_ids']),
    'evidence_dir':after.get('evidence_dir'),'evidence_ids':after['evidence_ids'],'sha256':after['evidence_sha256'],'at':time.time()})
  state['pending']=None;journal.save(state);done.append({'name':target,'quantity':quantity})
  if after['boxes']==0:return done
 return done
