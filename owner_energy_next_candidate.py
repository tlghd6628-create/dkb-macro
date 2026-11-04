"""One next balanced essence trial; no direct game input on import.

Only a missing-confirmation result may follow a first untested reward: the
existing single-worker port captures the real receipt and leaves pending.
"""
import time,uuid
from owner_energy_box_runtime_candidate import Hold,proof,choose

TRIALS=('몽환','생명')
def run_next_trial(port,journal,selected,*,guard):
 state=journal.read()
 if state.get('pending') is not None:raise Hold('이전 수령 확인 필요')
 target=choose(selected,state)
 if target not in TRIALS:raise Hold('균등 다음 기운의 시범 수령 증거 필요')
 if state['confirmed'][target]!=0:raise Hold('해당 기운의 수령 결과부터 확인 필요')
 if guard() is not True:raise Hold('캐릭터 또는 설정 확인 필요')
 final=port.prepare_one(target,guard=guard)
 if (not proof(final) or final.get('name')!=target or final.get('quantity')!=1
     or type(final.get('boxes')) is not int or final['boxes']<1
     or (final.get('detail_boxes')!=final['boxes'] and not (final.get('detail_boxes') is None and final.get('detail_identity') is True))):
  raise Hold('기운 선택·1개·상자 개수 확인 필요')
 if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
 # Re-read durable state before preparing: changes never authorize a new click.
 state=journal.read()
 if state['pending'] is not None or choose(selected,state)!=target or state['confirmed'][target]!=0:raise Hold('기운 수령 순서 변경')
 operation=uuid.uuid4().hex
 state['pending']={'phase':'prepared','operation_id':operation,'name':target,'quantity':1,
                   'boxes_before':final['boxes'],'before_frame_ids':list(final['frame_ids']),'at':time.time()}
 journal.save(state);port.operation_id=operation
 def mark_sent():
  current=journal.read();item=current.get('pending')
  if not item or item.get('phase')!='prepared' or item.get('operation_id')!=operation or guard() is not True:raise Hold('수령 직전 재확인 필요')
  item['phase']='sent';journal.save(current)
 port.submit(final,mark_sent=mark_sent,guard=guard)
 if journal.read().get('pending',{}).get('phase')!='sent':raise Hold('입력 여부 확인 필요')
 # New-kind receipt is intentionally not promoted from an unvalidated image.
 # The port saves frames and nonce; the pending record blocks further claims.
 port.receipt(target,guard=guard)
 raise Hold('새 기운 수령 원본 확인 필요')

def attempt_next(adapter,context,inputs):
 """Optional owner-worker entry. Existing runtime stays untouched."""
 from owner_progression import state
 from owner_energy_box_runtime_candidate import Journal,fresh_character
 from owner_hunt_rules_candidate import configured_identity
 from owner_skill_goal import runtime_ledger
 from owner_starter_choice_candidate import Choices
 from owner_energy_generic_port_candidate import GenericPort
 context.checkpoint();progress=state(adapter);character=progress.character
 if not fresh_character(adapter,context,progress):raise Hold('캐릭터 최신 확인 필요')
 try:
  scope=configured_identity(adapter.project.root);receipt=runtime_ledger(adapter,character).receipt_key
  choices,revision=Choices(adapter.project.root,scope).snapshot()
 except (ValueError,OSError,TypeError) as exc:raise Hold('캐릭터 또는 기운 설정 확인 필요') from exc
 def guard():
  context.checkpoint();current=state(adapter)
  return (current.character==character and fresh_character(adapter,context,current)
          and configured_identity(adapter.project.root)==scope and Choices(adapter.project.root,scope).snapshot()[1]==revision)
 port=GenericPort(adapter,context,inputs);port.evidence_identity={'receipt_key':receipt,'character':character,'scope':scope}
 try:return run_next_trial(port,Journal(adapter.project.root,receipt),choices['energies'],guard=guard)
 finally:port.close_known()
