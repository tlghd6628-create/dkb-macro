"""Explicit same-worker receipt-only reconciliation; not installed on import."""
from pathlib import Path
from owner_gear_settings_candidate import Store
from owner_gear_intent_store_candidate import IntentStore

def run(adapter,context,inputs,identity,*,entry=None,service_factory=None):
    if not isinstance(identity,str) or not identity.strip():return {'state':'hold_identity'}
    path=Store(adapter.project.root,identity).path
    intent=IntentStore(path.with_name(path.stem+'-intent.json'))
    pending=intent.pending()
    if pending is None:return {'state':'no_pending'}
    if pending.get('kind')!='enhance':return {'state':'hold_unsupported'}
    from project_adapter import achievement_rewards as native
    from project_adapter.town_services import TownServices
    from owner_special_contexts import NAMES as SCENE_NAMES
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_startup_stage import scene
    names=list(dict.fromkeys(['체크_던전진행중','버튼_던전_나가기',*SCENE_NAMES,*AUTO_NAMES]))
    service=(service_factory or TownServices)(adapter,context,inputs,names)
    def field_pair():
        context.checkpoint();service.check();a=scene(service.detector,service.capture());context.wait(.12)
        context.checkpoint();service.check();b=scene(service.detector,service.capture())
        return a=='field' and b=='field'
    if not field_pair():return {'state':'hold_field'}
    old_values=adapter.values;old_flag=getattr(adapter,'_owner_growth_reconcile_only',None)
    had_flag=hasattr(adapter,'_owner_growth_reconcile_only')
    previous_hold=getattr(adapter,'_owner_growth_pending_hold',None);had_hold=hasattr(adapter,'_owner_growth_pending_hold')
    adapter.values=dict(old_values,**{'auto_growth.equipment.enabled':True,'auto_growth.blessing.enabled':False,'auto_growth.taoist.enabled':False})
    adapter._owner_growth_reconcile_only=True;adapter._owner_growth_pending_hold=False
    try:
        # Native entry normally opens the growth screen and returns immediately.
        # Its equipment-test branch calls the registered guarded equipment
        # worker and runs the established native exit path. Reconcile-only on
        # the adapter prevents this branch from sending a new growth action.
        context.checkpoint();(entry or native.run_growth_entry)(adapter,context,inputs,equipment_test=True)
        context.checkpoint()
        if not field_pair():raise RuntimeError('강화 결과 확인 후 필드 복귀 확인 필요')
        record=intent._read();remaining=record.get('pending')
        if remaining is not None or adapter._owner_growth_pending_hold:return {'state':'hold_result'}
        expected='observed_progress' if pending.get('phase')=='sent' else 'preinput_aborted'
        if record.get('last_result')!=expected:return {'state':'hold_result'}
        return {'state':expected}
    finally:
        adapter.values=old_values
        if had_flag:adapter._owner_growth_reconcile_only=old_flag
        else:del adapter._owner_growth_reconcile_only
        if had_hold:adapter._owner_growth_pending_hold=previous_hold
        else:del adapter._owner_growth_pending_hold
