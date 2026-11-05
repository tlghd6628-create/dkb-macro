"""Candidate one-input fence. Not installed into native or live game.

The caller supplies trusted paired observations, a single native input step,
and a durable intent store. This adapter must not wrap a whole native batch.
"""
import threading,time,math
from owner_gear_decision_candidate import Observation, decide, reconcile


class Guard:
    def __init__(self, context, store, read_pair, *, clock=time.monotonic, fresh_seconds=1.5):
        self.context=context;self.store=store;self.read_pair=read_pair;self.fresh_seconds=fresh_seconds
        self.clock=clock;self.worker=threading.get_ident();self.lock=threading.Lock()

    def _worker_check(self):
        if threading.get_ident()!=self.worker:raise RuntimeError('다른 입력 작업자에서 실행 불가')
        self.context.checkpoint()

    def _fresh(self,a,b):
        if not isinstance(a,Observation) or not isinstance(b,Observation):return False
        now=self.clock()
        return (type(now) in (int,float) and math.isfinite(now) and
                type(a.captured_at) in (int,float) and type(b.captured_at) in (int,float) and
                0 <= now-a.captured_at <= self.fresh_seconds and 0 <= now-b.captured_at <= self.fresh_seconds)

    def _enhance_plan(self,a,b,target):
        if (not self._fresh(a,b) or type(a.sequence) is not int or type(b.sequence) is not int or
            b.sequence<=a.sequence or b.captured_at<=a.captured_at):return False
        for key in ('character','item','slot','grade'):
            if not isinstance(getattr(a,key),str) or not getattr(a,key).strip() or getattr(a,key)!=getattr(b,key):return False
        if (type(a.enhancement) is not int or a.enhancement<0 or a.enhancement!=b.enhancement or
            a.enhance_available is not True or b.enhance_available is not True):return False
        from owner_growth_reading import goal_state
        return goal_state(target,a.enhancement)=='below'

    def _eligible(self,a,b,target,kind):
        # Unknown breakthrough/awakening fields do not prevent a separately
        # verified enhancement; they still cannot authorize their own actions.
        if kind=='enhance':return self._enhance_plan(a,b,target)
        if kind not in ('breakthrough','awaken') or not self._fresh(a,b):return False
        if type(a.sequence) is not int or type(b.sequence) is not int or b.sequence<=a.sequence or b.captured_at<=a.captured_at:return False
        for key in ('character','item','slot','grade'):
            if not isinstance(getattr(a,key),str) or not getattr(a,key).strip() or getattr(a,key)!=getattr(b,key):return False
        field,available=('breakthrough','breakthrough_available') if kind=='breakthrough' else ('awakening','awaken_available')
        goal='breakthrough' if kind=='breakthrough' else 'awaken'
        value=getattr(a,field)
        if (not isinstance(target,dict) or target.get('enabled') is not True or
            type(target.get(goal)) is not int or target[goal]<0 or type(value) is not int or value<0 or
            value!=getattr(b,field) or value>=target[goal] or
            getattr(a,available) is not True or getattr(b,available) is not True):return False
        if kind=='breakthrough':
            if value==0:return type(a.enhancement) is int and a.enhancement>=50 and a.enhancement==b.enhancement
            # Initial50 unlock is already passed. Actual2→3 was observed
            # with a lower post-breakthrough enhancement label on2026-11-02.
            return a.enhancement==b.enhancement and (a.enhancement is None or type(a.enhancement) is int)
        # Awakening is independently available: breakthrough level is not a
        # prerequisite and may legitimately be unreadable on this screen.
        return True

    def run_one(self, kind, targets, one_native_input):
        self._worker_check()
        with self.lock:
            if self.store.pending() is not None:return 'hold_pending'
            if kind not in ('enhance','breakthrough','awaken'):return 'hold_unknown_action'
            data=self.read_pair()
            if not isinstance(data,dict) or data.get('screen_proof') is not True:return 'hold_screen_unverified'
            a,b=data.get('first'),data.get('second')
            if not self._fresh(a,b):return 'hold_observation'
            target=targets.get(a.grade) if isinstance(targets,dict) else None
            if not self._eligible(a,b,target,kind):return 'hold_policy'
            # Exact balance is optional for the explicitly allowed ordinary
            # enhancement flow. Native-active evidence still needs two frames.
            cost=data.get('cost');balance=data.get('balance')
            native_active=(data.get('resource_mode')=='native_active' and
                           data.get('active_pair_verified') is True and
                           (kind=='enhance' or data.get('action_mode')==kind))
            if not native_active and (data.get('cost_pair_verified') is not True or data.get('currency')!='엽전' or
                type(cost) is not int or cost<0 or type(balance) is not int or balance<cost):
                return 'hold_cost'
            self._worker_check()
            # Persist before the only permitted input. If cancelled, interrupted,
            # or the process dies, the record blocks retry until reconciliation.
            self.store.begin({'kind':kind,'before':a,'second':b,'cost':cost,'balance':balance,
                              'item_icon':data.get('item_icon')})
            try:
                self._worker_check()
                # Re-read at the boundary after the durable prepared record.
                latest=self.read_pair()
                if not isinstance(latest,dict) or latest.get('screen_proof') is not True:return 'hold_boundary_preinput'
                c,d=latest.get('first'),latest.get('second')
                if not self._fresh(c,d) or c.sequence<=b.sequence or c.captured_at<=b.captured_at:return 'hold_boundary_preinput'
                fields=('character','item','slot','grade','enhancement','breakthrough','awakening',
                        'enhance_available','breakthrough_available','awaken_available')
                latest_active=(native_active and latest.get('resource_mode')=='native_active' and
                               latest.get('active_pair_verified') is True and
                               (kind=='enhance' or latest.get('action_mode')==kind) and
                               latest.get('button_name')==data.get('button_name') and
                               latest.get('opening')==data.get('opening'))
                latest_exact=(not native_active and latest.get('cost_pair_verified') is True and
                              latest.get('currency')=='엽전' and type(latest.get('cost')) is int and
                              latest['cost']==cost and type(latest.get('balance')) is int and latest['balance']==balance)
                if (any(getattr(c,k)!=getattr(a,k) for k in fields) or not (latest_active or latest_exact) or
                    not self._eligible(c,d,target,kind)):return 'hold_boundary_preinput'
                self._worker_check()
                one_native_input(latest,self.store.mark_sent)
                return 'pending_confirmation'
            finally:
                # Only a record not marked sent is provably before any click.
                self.store.abort_prepared('최종 판독 또는 클릭 전 중단')

    def reconcile(self,*,before_complete=None,short_notice=None):
        self._worker_check()
        with self.lock:
            saved=self.store.pending()
            if saved is None:return 'nothing_pending'
            if saved.get('phase')=='prepared':
                self.store.abort_prepared('이전 실행의 입력 전 준비 기록');return 'preinput_aborted'
            # The game said the press had no coins behind it: nothing changed, and that is the answer.
            if callable(short_notice) and short_notice() is True:
                self._worker_check()
                self.store.complete('short_of_coins')
                return 'short_of_coins'
            data=self.read_pair()
            if not isinstance(data,dict) or data.get('screen_proof') is not True:return 'hold_result_unknown'
            if not self._fresh(data.get('first'),data.get('second')):return 'hold_result_unknown'
            before=saved['before'];a,b=data.get('first'),data.get('second')
            if saved['kind']=='breakthrough' and data.get('result_failed') is True:
                # Breakthrough is probabilistic. Only a paired explicit failure
                # window on the same item ends this input; unchanged never does.
                if not (all(getattr(a,k)==getattr(before,k)==getattr(b,k) for k in ('character','item','grade'))
                        and a.slot==b.slot and b.sequence>a.sequence):return 'hold_result_unknown'
                self._worker_check()
                if callable(before_complete) and before_complete() is not True:return 'hold_identity_or_settings'
                self.store.complete('observed_failure')
                return 'observed_failure'
            if saved['kind']=='enhance':
                same=(all(getattr(a,k)==getattr(before,k)==getattr(b,k) for k in ('character','item','grade'))
                      and a.slot==b.slot)
                changed=(type(a.enhancement) is int and type(b.enhancement) is int and
                         a.enhancement==b.enhancement and a.enhancement>before.enhancement)
                result=('observed_progress' if same and b.sequence>a.sequence and changed else 'hold_result_unknown')
            else:
                kind=saved['kind'];field={'breakthrough':'breakthrough','awaken':'awakening'}.get(kind)
                same=(all(getattr(a,k)==getattr(before,k)==getattr(b,k) for k in ('character','item','grade'))
                      and a.slot==b.slot)
                old=getattr(before,field,None) if field else None
                va=getattr(a,field,None) if field else None;vb=getattr(b,field,None) if field else None
                changed=(type(old) is int and type(va) is int and type(vb) is int and va==vb and va>old)
                result=('observed_progress' if same and b.sequence>a.sequence and changed else 'hold_result_unknown')
                if result!='observed_progress' and kind=='breakthrough' and same and b.sequence>a.sequence and old==va==vb:
                    # Same stage on the same item: that attempt failed.
                    self._worker_check()
                    if callable(before_complete) and before_complete() is not True:return 'hold_identity_or_settings'
                    self.store.complete('observed_failure')
                    return 'observed_failure'
            if result == 'observed_progress':
                self._worker_check()
                if callable(before_complete) and before_complete() is not True:return 'hold_identity_or_settings'
                self.store.complete(result)
            # Failure/unchanged retain the pending intent; a later rescan or an
            # explicit reviewed resolution is required before another input.
            return result
