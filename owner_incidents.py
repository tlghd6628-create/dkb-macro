"""Local quest-failure receipts. Capture once before fallback; encode off-thread."""
from __future__ import annotations
from collections import deque
from datetime import datetime,timezone
import hashlib
import json
import logging
from pathlib import Path
import queue
import re
import shutil
import threading
import time
import uuid
import zipfile

TOKEN=re.compile(r'\b\d{5,20}:[A-Za-z0-9_-]{20,200}\b')
SECRET=re.compile(r'(?i)(token|password|authorization|api[_-]?key|비밀번호)\s*[:=]\s*\S+')


def safe(value,limit=1200):
    text=TOKEN.sub('[토큰 제외]',str(value))
    return SECRET.sub(r'\1=[제외]',text)[:limit]


def classify(message,level=logging.INFO):
    """Observed signals only; a timeout is not a proved equipment defect."""
    if message.startswith('진행 진단'):return None
    if '사망 확정' in message or '사망확정' in message or '부수 작업 중 사망 화면' in message:return 'character_death'
    if '퀘스트 진행 반복 누적' in message or ('퀘' in message and '나가기' in message and '반복' in message):
        return 'repeated_action'
    failure=any(word in message for word in ('실패','불가','부족','못함','할 수 없','not enough','failed'))
    if any(word in message for word in ('재료','골드','재화','레벨','자원')) and failure:
        return 'condition_unmet'
    if any(word in message for word in ('강화','장비','스킬','성장','제작','Action ')) and failure:
        return 'action_failure'
    if any(word in message for word in ('퀘','서사')) and any(word in message for word in ('진행 불가','막힘','진행 지연','전환','중간 처리 생략')):
        # Ordinary manual mode changes are not incidents.
        if not message.startswith('실행 모드 변경'):
            return 'quest_fallback' if any(w in message for w in ('전환','다음 단계','다른 퀘','중간 처리')) else 'progress_timeout'
    if any(word in message for word in ('자동 동작 오류','연속 실패로 자동 정지','자동 동작 종료:')):
        return 'automation_error'
    if level>=logging.WARNING and any(word in message for word in ('퀘스트','튜토리얼','Quest','Tutorial')):
        return 'quest_error'
    return None


class IncidentRecorder(logging.Handler):
    def __init__(self,gui,capture=None,folder=None,clock=time.monotonic):
        super().__init__(logging.INFO)
        self.gui=gui;self.clock=clock
        self.folder=Path(folder or gui.project.root/'logs/quest-incidents')
        if capture is None:
            from owner_controls import capture_current
            capture=lambda:capture_current(gui)
        self.capture=capture
        self.recent=deque(maxlen=50);self.context={}
        self.last={};self.last_capture=-1e30;self.suppressed=0;self.dropped=0
        self.pending=queue.Queue(maxsize=4);self.ending=threading.Event()
        self.capture_thread=None
        self.in_emit=threading.local();self.worker=threading.Thread(target=self._write_loop,name='dkb-quest-diagnostics',daemon=True)
        self.worker.start()

    def emit(self,record):
        if self.ending.is_set() or getattr(self.in_emit,'active',False):return
        self.in_emit.active=True
        try:
            message=safe(record.getMessage())
            snapshot=self.gui.session.snapshot()
            if snapshot['status'] not in ('running','error'):return
            if message.startswith('상태:') or message=='사용자 정지':return
            match=re.search(r'mode=(\w+) selected=(\w+)',message)
            if match:self.context.update(mode=match[1],selected=match[2])
            if any(w in message for w in ('퀘','서사','강화','장비','스킬','성장','Action ','Tutorial','자동 동작')):
                self.recent.append({'time':datetime.fromtimestamp(record.created,timezone.utc).isoformat(),
                                    'level':record.levelname,'message':message})
            category=classify(message,record.levelno)
            if category is None:return
            mode=getattr(getattr(self.gui,'adapter',None),'mode',self.context.get('mode','unknown'))
            key=(category,str(mode),self.context.get('selected','unknown'))
            now=self.clock()
            if now-self.last.get(key,-1e30)<120 or now-self.last_capture<3:
                self.suppressed+=1;return
            if self.pending.full():self.dropped+=1;return
            self.last[key]=now;self.last_capture=now
            receipt={'schema':'dkb-quest-incident-v1','id':datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8],
                'observed_at':datetime.fromtimestamp(record.created,timezone.utc).isoformat(),
                'category':category,'observed_reason':message,
                'cause_status':'unconfirmed' if category in ('quest_fallback','progress_timeout','repeated_action') else 'reported_by_runtime',
                'root_cause_confirmed':False,'quest_title':None,
                'mode':safe(mode,100),'last_decision':dict(self.context),
                'session':{k:snapshot.get(k) for k in ('status','generation','worker_alive')},
                'recent_events':list(self.recent),'suppressed_duplicates':self.suppressed,'dropped_busy_events':self.dropped,
                'game_input':False,'automatic_upload':False,'capture_budget_ms':150}
            if record.exc_info:
                receipt['exception']={'type':record.exc_info[0].__name__,'message':safe(record.exc_info[1])}
            self.suppressed=0;self.dropped=0
            image=None;started=self.clock()
            try:
                # Freeze the game before the caller returns to its fallback.
                # Only PNG compression/disk I/O is deferred, never this frame.
                image,meta=self.freeze_frame()
                receipt['capture']={'success':True,'metadata':meta}
            except Exception as exc:
                receipt['capture']={'success':False,'error_type':type(exc).__name__,'error':safe(exc)}
            receipt['capture_ms']=round((self.clock()-started)*1000,3)
            self.pending.put_nowait((receipt,image))
        except Exception:
            # Diagnostics cannot change the automation outcome.
            self.dropped+=1
        finally:self.in_emit.active=False

    def freeze_frame(self):
        # PrintWindow can stall inside Windows. Never hold the action/logging
        # thread beyond this small incident-only budget; one daemon at a time.
        if self.capture_thread is not None and self.capture_thread.is_alive():
            raise RuntimeError('이전 화면 캡처가 응답하지 않아 이번 캡처를 생략했습니다.')
        result=queue.Queue(maxsize=1)
        def work():
            try:
                image,metadata=self.capture()
                result.put((image.copy(),metadata,None))
            except Exception as exc:result.put((None,None,exc))
        self.capture_thread=threading.Thread(target=work,name='dkb-incident-frame',daemon=True)
        self.capture_thread.start()
        try:image,metadata,error=result.get(timeout=.15)
        except queue.Empty:raise TimeoutError('150ms 안에 화면을 받지 못했습니다. 전환 후의 화면으로 대체하지 않습니다.')
        if error is not None:raise error
        return image,metadata

    def _write_loop(self):
        while not self.ending.is_set() or not self.pending.empty():
            try:receipt,image=self.pending.get(timeout=.1)
            except queue.Empty:continue
            try:
                self.folder.mkdir(parents=True,exist_ok=True)
                temporary=self.folder/('.pending-'+receipt['id']);temporary.mkdir()
                if image is not None:
                    frame=temporary/'screen.png'
                    image.save(frame,format='PNG',compress_level=1)
                    receipt['capture']['sha256']=hashlib.sha256(frame.read_bytes()).hexdigest()
                (temporary/'incident.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
                temporary.replace(self.folder/receipt['id'])
                self.prune()
                self.gui.logger.info('진행 진단 저장 완료 · %s',receipt['id'])
            except Exception as exc:
                self.gui.logger.warning('진행 진단 저장 실패 · %s',type(exc).__name__)
            finally:self.pending.task_done()

    def prune(self):
        if not self.folder.exists() or self.folder.is_symlink():return
        directories=sorted((p for p in self.folder.iterdir() if p.is_dir() and not p.is_symlink()
            and re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}',p.name)),reverse=True)
        total=0
        for index,path in enumerate(directories):
            files=[p for p in path.iterdir() if p.is_file() and not p.is_symlink()]
            total+=sum(p.stat().st_size for p in files)
            if index>=200 or total>200*1024*1024 or time.time()-path.stat().st_mtime>30*86400:
                if path.resolve().parent==self.folder.resolve() and {p.name for p in path.iterdir()} <= {'screen.png','incident.json'}:
                    shutil.rmtree(path)

    def flush(self):
        # Bounded wait is used only for explicit ZIP export/shutdown, not ticks.
        if not hasattr(self,'pending') or threading.current_thread() is self.worker:return
        deadline=time.monotonic()+2
        while self.pending.unfinished_tasks and time.monotonic()<deadline:time.sleep(.02)

    def close(self):
        if hasattr(self,'ending'):
            self.ending.set()
            if threading.current_thread() is not self.worker:self.worker.join(.3)
        super().close()


def append_to_bundle(path,folder):
    """Explicit local export only; never include settings or credentials."""
    folder=Path(folder)
    directories=sorted(folder.iterdir(),reverse=True) if folder.is_dir() and not folder.is_symlink() else []
    with zipfile.ZipFile(path,'a',zipfile.ZIP_DEFLATED) as archive:
        total=0;count=0
        for directory in directories:
            if directory.is_symlink() or not directory.is_dir() or not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}',directory.name):continue
            candidates=[directory/name for name in ('incident.json','screen.png')]
            files=[p for p in candidates if p.is_file() and not p.is_symlink()]
            size=sum(p.stat().st_size for p in files)
            if count>=20 or total+size>40*1024*1024:continue
            for source in files:archive.write(source,'quest-incidents/'+directory.name+'/'+source.name)
            total+=size;count+=1
        archive.writestr('quest-incidents/index.json',json.dumps({'incidents':count,'bytes':total,'local_export':True}))


def install(gui):
    if getattr(gui,'_owner_incidents',None) is not None:return
    recorder=IncidentRecorder(gui);gui._owner_incidents=recorder
    gui.logger.addHandler(recorder)
    # Existing local bundle stays authoritative; add only our bounded receipts.
    import diagnostic_bundle
    original=diagnostic_bundle.create_bundle
    def create_bundle(target):
        path=original(target)
        if target is gui:
            recorder.flush();append_to_bundle(path,recorder.folder)
        return path
    diagnostic_bundle.create_bundle=create_bundle
    def close(event):
        if event.widget is gui.root:
            gui.logger.removeHandler(recorder);recorder.close()
    gui.root.bind('<Destroy>',close,add='+')
