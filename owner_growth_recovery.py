"""Reconcile a prior sent enhancement once after the current start preflight.

This path confirms an old result only. It does not enhance, change targets,
reset timetable attempts, or mark the whole growth task complete.
"""
from pathlib import Path
from types import SimpleNamespace
import logging,time
LOG=logging.getLogger('project_gui.DKB')

def pending(root,identity):
 from owner_gear_settings_candidate import Store
 from owner_gear_intent_store_candidate import IntentStore
 path=Store(root,identity).path
 return IntentStore(path.with_name(path.stem+'-intent.json')).pending()

def recover(adapter,context,inputs):
 if getattr(adapter,'_owner_growth_recovery_context',None) is context:return 'already_checked'
 if getattr(adapter,'values',{}).get('auto_growth.equipment.enabled') is not True:return 'disabled'
 from owner_progression import state
 current=state(adapter);receipt=getattr(adapter,'_owner_progression_observation',None)
 if (not isinstance(receipt,tuple) or len(receipt)!=3 or receipt[0] is not context
     or receipt[1]!=current.observed or receipt[2]!=current.character or not current.character
     or type(current.level) is not int or not 0<=time.monotonic()-current.observed<=180):return 'hold_identity'
 from owner_program_runtime import gear_identity
 identity=gear_identity(SimpleNamespace(adapter=adapter))
 if not identity:return 'hold_identity'
 try:item=pending(adapter.project.root,identity)
 except (OSError,ValueError,TypeError,RuntimeError) as exc:
  LOG.warning('이전 강화 기록 점검 보류 · %s',str(exc));return 'hold_history'
 if item is None:
  adapter._owner_growth_recovery_context=context;return 'no_pending'
 before=item.get('before')
 # A press by way of the bag settles when its worn item is next read there.
 if str(getattr(before,'slot','')).startswith('worn:'):
  adapter._owner_growth_recovery_context=context;return 'no_pending'
 if (item.get('phase')!='sent' or item.get('kind')!='enhance'
     or getattr(before,'character',None)!=identity):return 'hold_history'
 context.checkpoint()
 if getattr(context,'input_depth',0) or getattr(inputs,'held',()):return 'hold_input'
 from owner_gear_reconcile_entry_candidate import run
 adapter._owner_growth_recovery_context=context
 LOG.info('이전 강화 결과 재확인 시작 · 새 강화 입력 없음')
 result=run(adapter,context,inputs,identity)
 status=result.get('state','hold_unknown') if isinstance(result,dict) else 'hold_unknown'
 LOG.info('이전 강화 결과 재확인 · %s · 현재 퀘스트로 복귀',status)
 return status
