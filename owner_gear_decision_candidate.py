"""Pure planning candidate for observed equipment; never sends game input."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    sequence: int
    captured_at: float
    character: str
    item: str
    slot: str
    grade: str
    enhancement: int
    breakthrough: int
    awakening: int
    enhance_available: object
    breakthrough_available: object
    awaken_available: object
    explicit_failure: object = None


def pair(a, b):
    if not isinstance(a, Observation) or not isinstance(b, Observation): return False
    if type(a.sequence) is not int or type(b.sequence) is not int or b.sequence <= a.sequence: return False
    try:
        if not (math.isfinite(a.captured_at) and math.isfinite(b.captured_at) and 0 < b.captured_at-a.captured_at <= 1.5): return False
    except TypeError: return False
    for field in ('character','item','slot','grade'):
        x = getattr(a, field)
        if not isinstance(x,str) or not x.strip() or x != getattr(b,field): return False
    for field in ('enhancement','breakthrough','awakening'):
        x = getattr(a,field)
        if type(x) is not int or x < 0 or x != getattr(b,field): return False
    for field in ('enhance_available','breakthrough_available','awaken_available','explicit_failure'):
        x,y = getattr(a,field),getattr(b,field)
        if x is not None and type(x) is not bool: return False
        if x != y: return False
    return True


def decide(a,b,target,pending_action=None):
    """Advisory labels only; 'plan_*' is never authority to click."""
    if not pair(a,b): return 'hold_unverified_observation'
    if pending_action is not None: return 'hold_pending_result'
    if not isinstance(target,dict) or target.get('enabled') is not True: return 'disabled'
    for k in ('enhance','breakthrough','awaken'):
        if type(target.get(k)) is not int or target[k] < 0: return 'hold_invalid_target'
    if a.grade not in ('일반','희귀','영웅'): return 'hold_unknown_grade'
    # User-specified system: only 50강 equipment can begin breakthroughs;
    # if a custom level contradicts that gate, don't reinterpret their target.
    if target['breakthrough'] > 0 and target['enhance'] < 50 and a.enhancement < 50 and a.breakthrough==0:
        return 'hold_target_conflict'
    if a.awakening < target['awaken']:
        if a.awaken_available is True: return 'plan_awaken'
        if a.awaken_available is None: return 'hold_awaken_availability_unknown'
    if a.breakthrough>0 and a.breakthrough<target['breakthrough']:
        if a.breakthrough_available is True:return 'plan_breakthrough'
        return 'hold_breakthrough_material' if a.breakthrough_available is False else 'hold_breakthrough_availability_unknown'
    if a.enhancement < target['enhance']:
        if a.enhance_available is True: return 'plan_enhance'
        return 'hold_enhance_material' if a.enhance_available is False else 'hold_enhance_availability_unknown'
    if a.breakthrough < target['breakthrough']:
        if a.breakthrough==0 and a.enhancement < 50: return 'hold_breakthrough_gate'
        if a.breakthrough_available is True: return 'plan_breakthrough'
        return 'hold_breakthrough_material' if a.breakthrough_available is False else 'hold_breakthrough_availability_unknown'
    if a.awakening < target['awaken']: return 'hold_awaken_material'
    return 'targets_met'


def reconcile(before, after_a, after_b, kind):
    """Stable fresh post-attempt readings: unchanged is unknown, never failure."""
    if not isinstance(before, Observation) or not pair(after_a,after_b): return 'hold_result_unknown'
    if kind not in ('enhance','breakthrough','awaken'): return 'hold_result_unknown'
    if (after_a.sequence <= before.sequence or after_a.captured_at <= before.captured_at or
        any(getattr(before,k) != getattr(after_a,k) for k in ('character','item','slot','grade'))):
        return 'hold_result_unknown'
    field={'enhance':'enhancement','breakthrough':'breakthrough','awaken':'awakening'}[kind]
    old, new = getattr(before,field), getattr(after_a,field)
    if type(old) is not int or old < 0: return 'hold_result_unknown'
    if new > old: return 'observed_progress'
    if new == old and after_a.explicit_failure is True: return 'observed_failure'
    return 'hold_result_unknown'
