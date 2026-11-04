"""Conservative selection-box coordinator; UI evidence adapter is required.

A port must provide current paired real-screen readings and verified clicks.
No port is installed by default; absent observations never authorize input.
"""
from pathlib import Path
import hashlib, json, logging, math, os, tempfile, time, uuid

LOG = logging.getLogger('project_gui.DKB')
NAMES = ('생명', '여명', '몽환', '홍염')

class Hold(RuntimeError):
    pass

class Journal:
    def __init__(self, root, identity):
        if not isinstance(identity, str) or not identity: raise Hold('캐릭터 확인 필요')
        key = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
        self.path = Path(root) / 'settings' / ('owner-energy-claim-' + key + '.json')
        self.identity = identity
    def read(self):
        try: value = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'version': 1, 'identity': self.identity, 'confirmed': {n: 0 for n in NAMES}, 'pending': None, 'receipts': [], 'manual_observations': []}
        if not isinstance(value, dict) or value.get('version') != 1 or value.get('identity') != self.identity: raise Hold('기운 상자 기록 확인 필요')
        if not isinstance(value.get('confirmed'), dict) or any(type(value['confirmed'].get(n)) is not int or value['confirmed'][n] < 0 for n in NAMES): raise Hold('기운 상자 균형 기록 확인 필요')
        if not isinstance(value.get('receipts'), list) or not isinstance(value.get('manual_observations'), list) or (value.get('pending') is not None and not isinstance(value['pending'], dict)): raise Hold('기운 상자 수령 기록 확인 필요')
        return value
    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.energy-claim-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def note_manual_event(self, *, event_id, name, quantity, source):
        """Explicit, character-scoped balancing note; never a claimed receipt."""
        if not isinstance(event_id,str) or not event_id or name not in NAMES or type(quantity) is not int or quantity<1 or not isinstance(source,str) or not source:
            raise ValueError('수동 기운 선택 관측 기록 확인 필요')
        value=self.read()
        if value.get('pending') is not None:raise Hold('수령 대기 중 수동 보정 불가')
        existing=[e for e in value['manual_observations'] if e.get('event_id')==event_id]
        if existing:
            if any((e.get('name'),e.get('quantity'),e.get('source'))!=(name,quantity,source) for e in existing):raise Hold('같은 수동 관측 기록 불일치')
            return False
        value['manual_observations'].append(dict(event_id=event_id,name=name,quantity=quantity,source=source,balancing_only=True))
        self.save(value);return True


def proof(value, *, now=None):
    """Two distinct capture IDs, agreeing state and <= 3 seconds old."""
    if not isinstance(value, dict) or value.get('verified') is not True: return False
    ids = value.get('frame_ids'); times = value.get('captured_at')
    now = time.monotonic() if now is None else now
    return (isinstance(ids, (list, tuple)) and len(ids) == 2 and all(isinstance(x, str) and x for x in ids) and ids[0] != ids[1]
            and isinstance(times, (list, tuple)) and len(times) == 2 and all(type(x) in (int,float) and math.isfinite(x) for x in times)
            and 0 <= times[1]-times[0] <= 2.5 and 0 <= now-times[0] <= 3)


def choose(selected, data):
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected) or any(x not in NAMES for x in selected): raise Hold('선택한 기운 확인 필요')
    totals = dict(data['confirmed'])
    # The manual observation is separate from verified automatic receipts.
    for event in data['manual_observations']:
        if event.get('balancing_only') is True and event.get('name') in NAMES and type(event.get('quantity')) is int and event['quantity'] > 0:
            totals[event['name']] += event['quantity']
    return min(selected, key=lambda n: (totals[n], NAMES.index(n)))

def fresh_character(adapter,context,progress):
    """Reuse the same-worker paired character and level preflight receipt."""
    receipt=getattr(adapter,'_owner_progression_observation',None)
    observed=getattr(progress,'observed',None)
    return bool(isinstance(receipt,tuple) and len(receipt)==3 and receipt[0] is context
        and receipt[1]==observed and receipt[2]==getattr(progress,'character',None)
        and progress.character and type(getattr(progress,'level',None)) is int
        and type(observed) in (int,float) and 0<=time.monotonic()-observed<=180)


def run(port, journal, selected, *, guard, trial_limit=1):
    """Run at most one claim. All input/recognition is delegated to a verified port.

    select_one must verify both frames after each action. final() proves exact
    chosen name, qty 1 and separately observed detail box count. submit() must
    call mark_sent immediately before input. Receipt requires a separately read
    paired box count AND an explicit same-name, one-item acquisition toast.
    """
    if trial_limit != 1: raise Hold('실제 수령 검증 전 1회 한도')
    data = journal.read()
    if data['pending'] is not None: raise Hold('이전 상자 수령 결과 확인 필요')
    if data.get('receipts'): raise Hold('1회 시험 완료 · 추가 사용 보류')
    target = choose(selected, data)
    if guard() is not True: raise Hold('캐릭터 또는 설정 확인 필요')
    final = port.prepare_one(target, guard=guard)
    if not proof(final) or final.get('name') != target or final.get('quantity') != 1 or type(final.get('boxes')) is not int or final['boxes'] < 1 or final.get('detail_boxes') != final['boxes']:
        raise Hold('선택 기운·수량·상자 개수 확인 필요')
    if guard() is not True: raise Hold('캐릭터 또는 설정 변경')
    operation_id=uuid.uuid4().hex
    data['pending'] = {'phase': 'prepared', 'operation_id': operation_id, 'name': target, 'quantity': 1, 'boxes_before': final['boxes'], 'before_frame_ids': list(final['frame_ids']), 'at': time.time()}
    journal.save(data)
    port.operation_id=operation_id
    def mark_sent():
        item = journal.read()
        if not item.get('pending') or item['pending'].get('phase') != 'prepared': raise Hold('상자 요청 상태 오류')
        if guard() is not True: raise Hold('캐릭터 또는 설정 변경')
        item['pending']['phase'] = 'sent'; journal.save(item)
    try: port.submit(final, mark_sent=mark_sent, guard=guard)
    except Exception:
        # Prepared may still represent input sent by an incorrect port; retain.
        raise
    current = journal.read()
    if current['pending']['phase'] != 'sent': raise Hold('상자 입력 여부 확인 필요')
    after = port.receipt(target, guard=guard)
    if (guard() is not True or not proof(after) or set(after['frame_ids']) & set(final['frame_ids']) or after.get('name') != target or after.get('quantity') != 1
        or after.get('toast_verified') is not True or after.get('boxes') != final['boxes'] - 1):
        raise Hold('기운 수령과 상자 차감 확인 필요')
    current['confirmed'][target] += 1
    current['receipts'].append({'name': target, 'quantity': 1, 'frame_ids': list(after['frame_ids']), 'at': time.time(),
                                'operation_id':operation_id,'evidence_dir':after.get('evidence_dir'),
                                'evidence_ids':after.get('evidence_ids'),'evidence_sha256':after.get('evidence_sha256')})
    current['pending'] = None; journal.save(current)
    return 'confirmed'


def run_after_inventory(adapter, context, inputs):
    """Only the existing single input worker may call this optional integration.

    The evidence port is not yet connected: absent port => no game input.
    """
    factory = getattr(adapter, '_owner_energy_box_port_factory', None)
    if not callable(factory):
        from owner_energy_box_port_candidate import factory
    from owner_progression import state
    from owner_hunt_rules_candidate import configured_identity
    from owner_skill_goal import runtime_ledger
    from owner_starter_choice_candidate import Choices
    context.checkpoint()
    progress = state(adapter); character = progress.character
    if not fresh_character(adapter,context,progress): return 'character_unknown'
    try:
        scope = configured_identity(adapter.project.root)
        receipt = runtime_ledger(adapter, character).receipt_key
        selected, revision = Choices(adapter.project.root, scope).snapshot()
    except (OSError,ValueError,TypeError) as exc:
        raise Hold('캐릭터 또는 기운 설정 확인 필요') from exc
    if not selected['energies']: return 'disabled'
    journal=Journal(adapter.project.root, receipt)
    notes=journal.read()['manual_observations']
    if not any(e.get('event_id')=='20261102-manual-life-one' and e.get('name')=='생명' and e.get('quantity')==1 and e.get('balancing_only') is True for e in notes):
        return 'trial_wait_character_scoped_manual_observation'
    pending=journal.read().get('pending')
    # Only the one historical pre-nonce dawn event is understood by the
    # legacy reconciler. Other operations must never open inventory here.
    if pending is not None:
        from owner_energy_legacy_reconcile_candidate import LEGACY_AT,LEGACY_BEFORE,LEGACY_CHARACTER,LEGACY_RECEIPT
        is_legacy=(not pending.get('operation_id') and pending.get('phase')=='sent'
                   and pending.get('name')=='여명' and pending.get('quantity')==1
                   and pending.get('boxes_before')==49 and pending.get('before_frame_ids')==LEGACY_BEFORE
                   and type(pending.get('at')) in (int,float) and abs(pending['at']-LEGACY_AT)<=.001
                   and character==LEGACY_CHARACTER and receipt==LEGACY_RECEIPT)
        if not is_legacy:return 'new_reward_evidence_pending'
    if pending is None and choose(selected['energies'],journal.read())!='여명':return 'trial_wait_dawn_selected'
    def guard():
        context.checkpoint()
        current = state(adapter)
        return (current.character == character and fresh_character(adapter,context,current)
                and configured_identity(adapter.project.root) == scope and Choices(adapter.project.root, scope).snapshot()[1] == revision)
    port = factory(adapter, context, inputs)
    port.evidence_identity={'receipt_key':receipt,'character':character,'scope':scope}
    try:
        if journal.read().get('pending') is not None:
            from owner_energy_legacy_reconcile_candidate import read_legacy
            current=port.current_detail(guard)
            try:return read_legacy(adapter.project.root,journal,current,character=character,guard=guard)
            except (OSError,ValueError,TypeError,KeyError) as exc:raise Hold('기존 수령 자료 확인 필요') from exc
        return run(port, journal, selected['energies'], guard=guard)
    finally: port.close_known()

def attempt(adapter,context,inputs):
    """Keep box work independent of the completed starter-equipment receipt."""
    if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return 'disabled'
    try:
        result=run_after_inventory(adapter,context,inputs)
        if result not in ('disabled','character_unknown'):
            LOG.info('기운 선택상자 · %s',result)
        return result
    except Hold as exc:
        LOG.info('기운 선택상자 확인 보류 · %s',str(exc))
        return 'held'
