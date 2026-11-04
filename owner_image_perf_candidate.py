"""Opt-in diagnostic aggregation; never captures, reads text, or sends input.

Caller explicitly instruments operations with these helpers. Events contain
only allowlisted stage/outcome categories, durations and optional frame age.
All disk I/O is on a daemon worker; an overloaded queue drops data, never
waits for the game worker. This module is not installed into the application.
"""
from __future__ import annotations

import json
import logging
import math
import queue
import threading
import time
from collections import defaultdict
from pathlib import Path

STAGES = frozenset(('capture', 'template_match', 'ocr', 'ocr_workflow', 'mission_open',
                    'mission_scroll', 'mission_select', 'reward_open',
                    'reward_check', 'condition_wait', 'other_wait'))
OUTCOMES = frozenset(('ok', 'no_match', 'unreadable', 'timeout', 'stale', 'blocked', 'error', 'cancelled'))
BUCKETS_MS = (1, 5, 10, 20, 50, 100, 250, 500, 1000, 2000, 5000, 10000)
LOG=logging.getLogger('project_gui.DKB')

def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def _bucket(value):
    for limit in BUCKETS_MS:
        if value <= limit: return str(limit)
    return '>10000'

def summarize(events, dropped=0):
    groups = {}
    for stage, outcome, duration_ms, age_ms in events:
        key = stage + '/' + outcome
        row = groups.setdefault(key, {'count':0, 'duration_ms_buckets':defaultdict(int),
                                      'frame_age_ms_buckets':defaultdict(int)})
        row['count'] += 1
        row['duration_ms_buckets'][_bucket(duration_ms)] += 1
        if age_ms is not None: row['frame_age_ms_buckets'][_bucket(age_ms)] += 1
    return {'version':1, 'dropped_events':dropped, 'groups':groups}

class ImagePerf:
    def __init__(self, path, *, interval=5.0, capacity=4096, clock=time.monotonic, start=True, max_bytes=16*1024*1024):
        if type(capacity) is not int or capacity < 1 or not _number(interval) or interval == 0:
            raise ValueError('invalid performance aggregation options')
        if type(max_bytes) is not int or max_bytes < 1024:raise ValueError('invalid performance file limit')
        self.path = Path(path); self.interval=interval; self.clock=clock
        self.max_bytes=max_bytes;self.file_limit_reached=False
        self.queue=queue.Queue(maxsize=capacity); self.closed=threading.Event()
        self._dropped=0; self._drop_lock=threading.Lock(); self.io_errors=0
        self.thread=None
        if start:
            self.thread=threading.Thread(target=self._worker, name='dkb-image-perf', daemon=True)
            self.thread.start()

    def mark(self):
        return self.clock()

    def record(self, stage, outcome, start, *, frame_at=None):
        """Return immediately; invalid data is discarded, never disrupts callers."""
        if (self.closed.is_set() or not isinstance(stage,str) or not isinstance(outcome,str)
                or stage not in STAGES or outcome not in OUTCOMES):
            return False
        end=self.clock()
        if not _number(start) or not _number(end) or start>end:
            return False
        if frame_at is not None and (not _number(frame_at) or frame_at>end):
            return False
        event=(stage,outcome,(end-start)*1000,
               (end-frame_at)*1000 if frame_at is not None else None)
        try:
            self.queue.put_nowait(event); return True
        except queue.Full:
            with self._drop_lock:self._dropped+=1
            return False

    def _take_dropped(self):
        with self._drop_lock:
            value=self._dropped; self._dropped=0
        return value

    def _emit(self, events):
        dropped=self._take_dropped()
        if not events and not dropped:return
        payload=summarize(events,dropped)
        payload['window_end_unix']=int(time.time())
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                if not self.file_limit_reached:
                    LOG.warning('임무 성능 기록 용량 한도 도달 · 기존 파일을 보존하고 새 기록을 중지합니다')
                self.file_limit_reached=True
                return
            with self.path.open('a',encoding='utf-8') as output:
                output.write(json.dumps(payload,ensure_ascii=True,separators=(',',':'))+'\n')
        except OSError:
            self.io_errors+=1
            if self.io_errors==1:LOG.warning('임무 성능 기록 저장 실패 · 기록 경로를 확인하세요')

    def _worker(self):
        events=[]; deadline=self.clock()+self.interval
        while not self.closed.is_set() or not self.queue.empty():
            timeout=max(0.001,min(.25,deadline-self.clock()))
            try: events.append(self.queue.get(timeout=timeout))
            except queue.Empty: pass
            if len(events)>=4096 or self.clock()>=deadline:
                self._emit(events);events=[];deadline=self.clock()+self.interval
        self._emit(events)

    def close(self, timeout=0):
        """Stop accepting events. Optional bounded join; no product thread wait required."""
        self.closed.set()
        if self.thread is not None and timeout>0:self.thread.join(timeout)
        return self.thread is None or not self.thread.is_alive()
