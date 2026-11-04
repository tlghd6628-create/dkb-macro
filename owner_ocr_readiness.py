"""Warm existing OCR clients without game input; Stop never waits for a model."""
from pathlib import Path
from functools import wraps
import logging
import threading
import time

LOG = logging.getLogger('project_gui.DKB')


class Warmup:
    def __init__(self, root, load=None):
        self.root = Path(root)
        self.done = threading.Event()
        self.error = None
        self.load = load or warm_existing_clients
        self.thread = threading.Thread(target=self._run, name='owner-ocr-ready', daemon=True)
        self.thread.start()

    def _run(self):
        started = time.monotonic()
        try:
            self.load(self.root)
        except Exception as exc:
            self.error = str(exc)
            LOG.error('인식 준비 실패 · 게임 입력 없음 · %s', self.error)
        finally:
            self.done.set()
            LOG.info('인식 준비 종료 · %.1f초 · %s', time.monotonic()-started,
                     '완료' if self.error is None else '실패')

    def wait(self, context):
        context.checkpoint()
        if not self.done.is_set():
            LOG.info('인식 준비 중 · 게임 입력 대기 · 중지 가능')
        while not self.done.wait(.1):
            # Context.wait drives native idle callbacks. Do NOT call it here:
            # a callback could open an inventory while OCR is still cold.
            context.checkpoint()
        context.checkpoint()
        if self.error is not None:
            raise RuntimeError('인식 준비 실패 · 게임 입력 차단 · '+self.error)


def warm_existing_clients(root):
    import numpy as np
    from tools.ocr_support import get_paddle_engine
    blank = np.zeros((32, 64, 3), dtype=np.uint8)
    for language in ('number', 'korean'):
        get_paddle_engine(root, language=language).predict(blank)


def install(gui):
    if getattr(gui, '_owner_ocr_readiness', None) is not None:
        return gui._owner_ocr_readiness
    job = Warmup(gui.project.root)
    gui._owner_ocr_readiness = job
    from project_adapter._entry import Adapter
    if not getattr(Adapter.run, '_owner_ocr_readiness', False):
        original = Adapter.run

        @wraps(original)
        def run(adapter, context, inputs):
            job.wait(context)
            return original(adapter, context, inputs)

        run._owner_ocr_readiness = True
        Adapter.run = run
    return job
