"""The private edition is maintained locally; upstream update actions are inert."""
import threading


class DisabledUpdateBridge:
    def __init__(self,gui):
        self.gui=gui;self.worker=None;self.pending=None;self.handoff=None
        self.cancel=threading.Event()
    def busy(self):return False
    def stop(self):self.cancel.set()
    def check(self):
        self.gui.logger.info('이 버전은 로컬에서 개별 업데이트합니다. 기존 자동 업데이트 연결은 해제됐습니다.')
        return False
    def prepare(self):return False
    def poll(self):return None
    def discard(self):return None
