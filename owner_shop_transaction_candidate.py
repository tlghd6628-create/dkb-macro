"""Independent, fail-closed shop planner and journal; performs no game input.

Observations must be produced by a separate, verified screen reader. No prices,
currencies, reset dates or purchase success are inferred by this module.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
import uuid
from pathlib import Path

SHOPS = ('town', 'remote')
FIELDS = ('character', 'shop', 'week', 'item', 'currency', 'unit_price',
          'remaining', 'balance')

class Hold(RuntimeError):
    """Evidence or durable state is insufficient; do not send a purchase."""

def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise Hold('이름 또는 식별 정보 확인 필요')
    return value.strip()

def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise Hold(name + ' 확인 필요')
    return value

def _pair(first, second, now, max_age):
    if type(now) not in (int, float) or not math.isfinite(now):
        raise Hold('시각 확인 필요')
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise Hold('두 화면의 증거 필요')
    for frame in (first, second):
        if frame.get('verified') is not True:
            raise Hold('검증되지 않은 화면')
        _text(frame.get('frame_id'))
        captured = frame.get('captured_at')
        if (type(captured) not in (int, float) or not math.isfinite(captured)
                or captured > now or now - captured > max_age):
            raise Hold('오래되었거나 시각이 잘못된 화면')
        for field in FIELDS:
            if field not in frame:
                raise Hold(field + ' 확인 필요')
    if first['frame_id'] == second['frame_id']:
        raise Hold('서로 다른 두 화면 필요')
    if any(first[k] != second[k] or type(first[k]) is not type(second[k]) for k in FIELDS):
        raise Hold('두 화면의 값이 다름')
    obs = {k: first[k] for k in FIELDS}
    for field in ('character', 'week', 'item', 'currency'):
        obs[field] = _text(obs[field])
    if obs['shop'] not in SHOPS:
        raise Hold('상점 종류 확인 필요')
    _integer(obs['unit_price'], '단가', 1)
    _integer(obs['remaining'], '남은 한도')
    _integer(obs['balance'], '잔액')
    return obs

class ShopJournal:
    def __init__(self, path, *, max_age=5.0, clock=time.time):
        self.path = Path(path)
        self.max_age = max_age
        self.clock = clock
        if (type(max_age) not in (int, float) or not math.isfinite(max_age)
                or max_age <= 0):
            raise ValueError('max_age')

    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name + '.lock')
        # The file is a stable lock identity, not proof that it is held.
        # Windows releases this byte-range lock if the process exits or crashes.
        import msvcrt
        fd = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.fstat(fd).st_size == 0:
                os.lseek(fd, 0, os.SEEK_SET); os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            os.close(fd)
            raise Hold('구매 기록이 사용 중이거나 점검 필요') from exc
        return fd, lock

    def _read(self):
        if not self.path.exists():
            return {'version': 1, 'transactions': []}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('transactions'), list):
                raise ValueError('invalid ledger')
            for entry in data['transactions']:
                if (not isinstance(entry, dict) or entry.get('state') not in ('pending', 'confirmed')
                    or not all(key in entry for key in ('id', 'character', 'shop', 'week', 'item',
                        'currency', 'unit_price', 'quantity', 'remaining', 'balance',
                        'minimum_balance', 'prepared_at', 'frame_ids'))):
                    raise ValueError('invalid transaction')
                for key in ('id', 'character', 'week', 'item', 'currency'):
                    _text(entry[key])
                if entry['shop'] not in SHOPS:
                    raise ValueError('invalid shop')
                for key in ('unit_price', 'quantity'):
                    _integer(entry[key], key, 1)
                for key in ('remaining', 'balance'):
                    _integer(entry[key], key)
                _integer(entry['minimum_balance'], 'minimum_balance')
                if (type(entry['prepared_at']) not in (int, float) or not math.isfinite(entry['prepared_at'])
                    or not isinstance(entry['frame_ids'], list) or len(entry['frame_ids']) != 2
                    or entry['frame_ids'][0] == entry['frame_ids'][1]):
                    raise ValueError('invalid evidence')
                for frame_id in entry['frame_ids']:
                    _text(frame_id)
            if len({entry['id'] for entry in data['transactions']}) != len(data['transactions']):
                raise ValueError('duplicate transaction')
            return data
        except (OSError, ValueError, TypeError, KeyError, Hold) as exc:
            raise Hold('구매 기록을 읽을 수 없어 중지') from exc

    def _write(self, data):
        fd, name = tempfile.mkstemp(prefix='.shop-journal-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def _under_lock(self, operation):
        fd, _ = self._lock()
        try:
            return operation()
        finally:
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            try: msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            finally: os.close(fd)

    def prepare(self, setting, minimum_balance, first, second):
        """Durably record intent, then return it. Caller must still revalidate before input."""
        def action():
            if not isinstance(setting, dict) or setting.get('enabled') is not True:
                raise Hold('구매가 설정된 품목이 아님')
            if setting.get('mode') not in ('quantity', 'max'):
                raise Hold('구매 수량 설정 확인 필요')
            _integer(minimum_balance, '최소 잔액')
            now = self.clock()
            if type(now) not in (int, float) or not math.isfinite(now): raise Hold('시각 확인 필요')
            obs = _pair(first, second, now, self.max_age)
            if setting.get('shop') != obs['shop'] or setting.get('name') != obs['item']:
                raise Hold('설정과 현재 상품 불일치')
            data = self._read(); records = data['transactions']
            match = lambda r: all(r[k] == obs[k] for k in ('character', 'shop', 'item'))
            if any(match(r) and r['state'] == 'pending' for r in records):
                raise Hold('이전 구매 결과 미확인 · 재구매 보류')
            purchased = sum(r['quantity'] for r in records if match(r) and r['week'] == obs['week'] and r['state'] == 'confirmed')
            target = obs['remaining'] if setting['mode'] == 'max' else max(0, _integer(setting.get('quantity'), '목표 수량', 1) - purchased)
            affordable = max(0, (obs['balance'] - minimum_balance) // obs['unit_price'])
            quantity = min(target, obs['remaining'], affordable)
            if quantity <= 0: raise Hold('남은 구매 한도·목표 수량 또는 최소 잔액 확인')
            entry = dict(obs, id=uuid.uuid4().hex, quantity=quantity, state='pending',
                         prepared_at=now, frame_ids=[first['frame_id'], second['frame_id']],
                         minimum_balance=minimum_balance)
            records.append(entry); self._write(data)
            return dict(entry)
        return self._under_lock(action)

    def revalidate(self, transaction_id, first, second):
        """Read-only final check before a future caller would act; no input occurs here."""
        def action():
            data = self._read()
            candidates = [e for e in data['transactions'] if e['id'] == transaction_id]
            if len(candidates) != 1 or candidates[0]['state'] != 'pending':
                raise Hold('대기 중 구매 기록 없음')
            entry = candidates[0]; now = self.clock()
            obs = _pair(first, second, now, self.max_age)
            if any(obs[k] != entry[k] for k in FIELDS):
                raise Hold('구매 전 상점 상태 변경')
            if any(frame['captured_at'] < entry['prepared_at'] for frame in (first, second)):
                raise Hold('기록 후 새 화면 필요')
            if set(entry['frame_ids']) & {first['frame_id'], second['frame_id']}:
                raise Hold('기록 후 새 화면 필요')
            if entry['balance'] - entry['unit_price'] * entry['quantity'] < entry['minimum_balance']:
                raise Hold('최소 잔액 미달')
            return dict(entry)
        return self._under_lock(action)

    def confirm(self, transaction_id, first, second):
        """Confirm only paired explicit receipt plus exact balance and limit movement."""
        def action():
            data = self._read()
            candidates = [e for e in data['transactions'] if e['id'] == transaction_id]
            if len(candidates) != 1 or candidates[0]['state'] != 'pending':
                raise Hold('대기 중 구매 기록 없음')
            entry = candidates[0]; now = self.clock()
            obs = _pair(first, second, now, self.max_age)
            if any(frame['captured_at'] < entry['prepared_at'] for frame in (first, second)):
                raise Hold('구매 기록 후 화면 필요')
            if any(frame.get('purchase_success') is not True or frame.get('purchased_quantity') != entry['quantity'] or type(frame.get('purchased_quantity')) is not int for frame in (first, second)):
                raise Hold('명확한 구매 완료 증거 필요')
            if any(obs[k] != entry[k] for k in ('character', 'shop', 'week', 'item', 'currency', 'unit_price')):
                raise Hold('구매 품목 또는 상점 불일치')
            if (obs['remaining'] != entry['remaining'] - entry['quantity'] or
                obs['balance'] != entry['balance'] - entry['unit_price'] * entry['quantity']):
                raise Hold('구매 수량·잔액·한도 불일치')
            if set(entry['frame_ids']) & {first['frame_id'], second['frame_id']}:
                raise Hold('구매 후 새 화면 필요')
            entry.update(state='confirmed', confirmed_at=now, confirmation_frame_ids=[first['frame_id'], second['frame_id']])
            self._write(data)
            return dict(entry)
        return self._under_lock(action)
