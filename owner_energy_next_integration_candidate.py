"""Bounded balanced energy claims on the existing inventory worker."""
import logging
from owner_energy_box_runtime_candidate import Hold,Journal,fresh_character
LOG=logging.getLogger('project_gui.DKB')
class NavigationError(RuntimeError):pass

def attempt(adapter,context,inputs):
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 from owner_skill_goal import runtime_ledger
 from owner_starter_choice_candidate import Choices
 from owner_energy_box_runtime_candidate import attempt as established
 from owner_energy_generic_port_candidate import GenericPort
 from owner_energy_nonce_reconcile_candidate import reconcile,READERS
 from owner_energy_balanced_runner_candidate import abort_own_prepared
 from owner_energy_batch_runner_candidate import run_batched
 from owner_energy_allocation_candidate import weights
 if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return 'disabled'
 context.checkpoint();progress=state(adapter);character=progress.character
 if not fresh_character(adapter,context,progress):return 'character_unknown'
 outcome={'state':'starting','confirmed':[]};adapter._owner_energy_box_outcome=outcome
 try:
  scope=configured_identity(adapter.project.root)
  receipt=runtime_ledger(adapter,character).receipt_key
  choices,revision=Choices(adapter.project.root,scope).snapshot()
  journal=Journal(adapter.project.root,receipt);data=journal.read()
  pending=data['pending']
  confirmation_only=getattr(adapter,'_owner_energy_box_reconcile_only',False) is True
  if not choices['energies'] and (not pending or not confirmation_only):outcome['state']='disabled';return 'disabled'
  if confirmation_only and pending is None:outcome['state']='nothing_pending';return 'nothing_pending'
  if pending and pending.get('phase')=='prepared' and abort_own_prepared(journal,pending):pending=None
  if pending is not None:
   if not pending.get('operation_id'):
    # The one historical pre-nonce event retains its exact reconciler.
    outcome['state']='legacy_reconciliation';return established(adapter,context,inputs)
   op=pending.get('operation_id')
   if (pending.get('name') not in READERS or pending.get('phase')!='sent'
       or not isinstance(op,str) or len(op)!=32 or any(c not in '0123456789abcdef' for c in op)):
    outcome['state']='pending_review';return 'new_reward_evidence_pending'
  if pending is None and any(value>0 and name not in READERS for name,value in weights(choices).items()):
   raise Hold('선택한 기운의 묶음 수령 판독 확인 필요')
  def guard():
   context.checkpoint();current=state(adapter)
   from owner_schedule_priority import hold_reason
   return (current.character==character and fresh_character(adapter,context,current)
           and configured_identity(adapter.project.root)==scope
           and Choices(adapter.project.root,scope).snapshot()[1]==revision
           and hold_reason(adapter) is None)
  if guard() is not True:outcome['state']='deferred';return 'held'
  factory=getattr(adapter,'_owner_energy_generic_port_factory',None)
  port=factory(adapter,context,inputs) if callable(factory) else GenericPort(adapter,context,inputs)
  port.evidence_identity={'receipt_key':receipt,'character':character,'scope':scope}
  try:
   if pending is not None:
    current=port.current_detail(guard)
    status=reconcile(adapter.project.root,journal,current,character=character,scope=scope,
                     guard=guard,refresh_current=lambda:port.current_detail(guard))
    if status!='confirmed':outcome['state']=status;return status
    outcome['confirmed'].append({'name':pending['name'],'quantity':pending['quantity']});port.close_known()
    if confirmation_only:
     remaining=pending['boxes_before']-pending['quantity']
     outcome.update(state='confirmed',remaining=remaining,
                    needs_recheck=bool(choices['energies'] and remaining>0),retry_after_seconds=60)
     return 'confirmed'
   try:
    done=run_batched(port,journal,choices,guard=guard,
                     validated_targets=set(READERS),max_batches=3,max_seconds=90)
   except (Hold,OSError,ValueError,TypeError) as exc:
    # A failed cleanup below replaces this reason, and it was the only record of what went wrong.
    LOG.info('기운 선택상자 중단 사유 · %s',exc);raise
   outcome['confirmed'].extend(done);outcome['state']='confirmed' if done else 'no_claim'
   latest=journal.read();last=latest['receipts'][-1] if latest['receipts'] else {}
   remaining=last.get('boxes_after')
   outcome.update(remaining=remaining,needs_recheck=type(remaining) is int and remaining>0,
                  retry_after_seconds=60)
   return outcome['state']
  finally:
   from biol_base.session import Cancelled
   try:port.close_known()
   except Cancelled:raise
   except (Hold,RuntimeError,OSError) as exc:
    # A resource hold is optional only AFTER its known UI has been closed.
    # Never let an uncleared modal fall through to the next shop/quest input.
    outcome.update(state='cleanup_blocked',reason=str(exc))
    raise NavigationError('기운 선택창 종료 미확인 · 다음 작업 입력 차단 · '+str(exc)) from exc
 except (Hold,OSError,ValueError,TypeError) as exc:
  outcome['state']='held';outcome['reason']=str(exc)
  if 'journal' in locals():
   try:
    pending=journal.read().get('pending') or {};op=pending.get('operation_id')
    if (pending.get('phase')=='sent' and pending.get('name') in READERS
        and isinstance(op,str) and len(op)==32 and all(c in '0123456789abcdef' for c in op)):
     outcome.update(needs_recheck=True,reconcile_only=True,pending_operation=op,retry_after_seconds=60)
   except (Hold,OSError,ValueError,TypeError):pass
  LOG.info('기운 선택상자 확인 보류 · %s',str(exc));return 'held'
 finally:
  if outcome['state']=='starting':outcome['state']='interrupted_unverified'
  # A safely closed UI with unreadable evidence is incomplete, not processed.
  # Any sent/unknown intent changes the *next* visit into result-only recovery.
  if outcome['state'] not in ('disabled','nothing_pending','confirmed','cleanup_blocked','interrupted_unverified'):
   outcome.update(retryable=True,retry_mode='recheck')
   if 'journal' in locals():
    try:
     outstanding=journal.read().get('pending')
     if outstanding is not None:
      outcome.update(retry_mode='reconcile',reconcile_only=True)
    except (Hold,OSError,ValueError,TypeError):
     outcome.update(retry_mode='reconcile',reconcile_only=True)
   outcome.setdefault('reason','기운 상자 판독 또는 수령 결과 미확인')
  LOG.info('기운 선택상자 결과 · %s',outcome)
