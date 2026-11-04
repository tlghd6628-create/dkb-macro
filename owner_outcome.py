"""One result vocabulary for scheduled work; never an input authority.

Native callers keep their True/False contracts. A job reports what really
happened here, and the timetable decides retries from that alone:

 done / goal_met    finished for this period
 waiting_condition  a proven game condition; recheck without using an attempt
 not_attempted      held before any resource input; retry without using an attempt
 sent_unconfirmed   input was sent, result unknown; result check only, no new input
 failed             attempted and failed; limited retries, then a later cycle
"""
from dataclasses import dataclass

DONE='done';GOAL_MET='goal_met';WAITING='waiting_condition'
NOT_ATTEMPTED='not_attempted';SENT_UNCONFIRMED='sent_unconfirmed';FAILED='failed'
# Most cautious first. Combining partial results never hides sent input.
_ORDER=(SENT_UNCONFIRMED,FAILED,NOT_ATTEMPTED,WAITING,DONE,GOAL_MET)
FINISHED=frozenset((DONE,GOAL_MET))
# run_energy_entry reasons returned before any energy input was attempted.
ENERGY_NOT_ATTEMPTED=('캐릭터 확인 필요','설정 확인 필요','진입 버튼 확인 필요')


@dataclass(frozen=True)
class Outcome:
    kind:str
    reason:str=''
    stage:str=''
    unverified:bool=False
    def __post_init__(self):
        if self.kind not in _ORDER:raise ValueError('알 수 없는 작업 결과: '+str(self.kind))


def worst(*outcomes):
    found=[row for row in outcomes if isinstance(row,Outcome)]
    return min(found,key=lambda row:_ORDER.index(row.kind)) if found else None


def report(adapter,key,outcome):
    """Record one part of a job. Several parts combine to the most cautious."""
    rows=getattr(adapter,'_owner_job_outcomes',None)
    if not isinstance(rows,dict):
        rows={};adapter._owner_job_outcomes=rows
    rows[key]=worst(rows.get(key),outcome)
    return rows[key]


def take(adapter,key):
    rows=getattr(adapter,'_owner_job_outcomes',None)
    return rows.pop(key,None) if isinstance(rows,dict) else None


def clear(adapter,key):take(adapter,key)


def growth_pending(adapter,suffix='-intent.json'):
    """The durable growth intent. An unreadable ledger is never treated as clear."""
    from owner_hunt_rules_candidate import configured_identity
    from owner_gear_settings_candidate import Store
    from owner_gear_intent_store_candidate import IntentStore
    try:
        root=adapter.project.root
        path=Store(root,configured_identity(root)).path
    except (ValueError,OSError,TypeError,AttributeError):return None
    try:return IntentStore(path.with_name(path.stem+suffix)).pending()
    except RuntimeError:return {'phase':'unreadable'}


def classify(key,adapter,result):
    """Explicit result for this finished job, or None for ordinary handling."""
    explicit=take(adapter,key)
    if key in ('gear','growth'):
        pending=growth_pending(adapter,'-intent.json' if key=='gear' else '-energy-intent.json')
        if isinstance(pending,dict) and pending.get('phase') in ('sent','unreadable'):
            return Outcome(SENT_UNCONFIRMED,'이전 성장 입력 결과 확인 필요',stage='result',unverified=True)
    if explicit is not None:return explicit
    if key=='gear':
        if getattr(adapter,'_owner_growth_preflight_hold',False) is True:
            return Outcome(NOT_ATTEMPTED,'캐릭터·레벨 재확인 필요',stage='identity')
        if getattr(adapter,'_owner_growth_pending_hold',False) is True:
            return Outcome(NOT_ATTEMPTED,'이전 성장 기록 확인 보류',stage='result')
    if key=='growth':
        energy=getattr(adapter,'_owner_energy_outcome',None)
        if isinstance(energy,dict) and energy.get('status')=='held':
            return Outcome(NOT_ATTEMPTED,str(energy.get('reason') or '기운 작업 보류'),stage='identity')
        if energy in ENERGY_NOT_ATTEMPTED:
            return Outcome(NOT_ATTEMPTED,energy,stage='precondition')
    return None
