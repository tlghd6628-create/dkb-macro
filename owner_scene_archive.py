"""Passive, local game-screen corpus; classification never authorizes inputs.

Reuse observed runtime frames. No extra screen capture, OCR, credentials, upload,
or automatic training. A bounded queue keeps compression and matching off ticks.
"""
from collections import deque
from datetime import datetime
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,logging,queue,re,sqlite3,sys,threading,time,uuid

LOCAL=threading.local()
REVISION='quest-growth-r12-diagnostics'
SCHEMA='dkb-scene-corpus-v1'


@contextmanager
def capture_scope(adapter,context,source='runtime_capture'):
    """Observe existing captures on this worker; never capture or input here."""
    previous=getattr(LOCAL,'owner',None);old_source=getattr(LOCAL,'source',None)
    LOCAL.owner=(adapter,context);LOCAL.source=source
    try:yield
    finally:
        LOCAL.owner=previous;LOCAL.source=old_source


def fingerprint(frame):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.fromarray(frame).convert('L').resize((96,54)),dtype='uint8').copy()


def similar(a,b):
    import numpy as np
    delta=np.abs(a.astype('int16')-b.astype('int16'))
    # Both a broad transition and a small high-contrast dialog change matter.
    return float(delta.mean())<=3 and float((delta>24).mean())<=.005


class SceneArchive(logging.Handler):
    def __init__(self,gui,folder=None,classifier=None,clock=time.monotonic,max_bytes=24*1024**3):
        super().__init__(logging.INFO)
        self.gui=gui;self.folder=Path(folder or gui.project.root/'logs/scene-corpus')
        self.clock=clock;self.max_bytes=max_bytes;self.classifier=classifier
        self.pending=queue.Queue(maxsize=8);self.ending=threading.Event()
        self.recent=deque(maxlen=30);self.stats_lock=threading.Lock();self.next_sample=0.;self.last_forced=-1e30
        self.activity_epoch=0;self.quest_state=None
        self.stats={'schema':SCHEMA,'revision':REVISION,'offered':0,'saved':0,'duplicates':0,
            'dropped_busy':0,'errors':0,'storage_full':False,'paused_or_stopped_collection':False,
            'automatic_upload':False,'automatic_training':False,'sample_interval_seconds':1,
            'max_bytes':max_bytes,'last_error':None,'routine_suppressed':0,
            'routine_same_activity_interval_seconds':15,'stored_bytes':0}
        self.worker=threading.Thread(target=self._loop,name='dkb-scene-corpus',daemon=True)
        self.worker.start()

    def emit(self,record):
        if record.name!='project_gui.DKB':return
        from owner_incidents import safe
        message=safe(record.getMessage(),800)
        if message.startswith('화면 자료'):return
        with self.stats_lock:
            if message.startswith(('자동 기능 시작 · ','실전 TEST 시작 · ')):self.activity_epoch+=1
            if message.startswith('퀘스트 상태판정:'):
                state=message.split(' matches=',1)[0]
                if state!=self.quest_state:self.activity_epoch+=1;self.quest_state=state
            self.recent.append({'time':datetime.fromtimestamp(record.created).isoformat(timespec='milliseconds'),
                                'level':record.levelname,'message':message})

    def offer(self,frame,adapter,context,source='runtime_capture',force=False):
        """No disk/matching/OCR here; only one bounded RGB copy per sample."""
        if self.ending.is_set() or context.stop.is_set() or context.pause.is_set():return False
        now=self.clock()
        with self.stats_lock:
            if self.stats['storage_full'] or (not force and now<self.next_sample):return False
            if force and now-self.last_forced<.25:return False
            if force:self.last_forced=now
            self.next_sample=now+1
            if self.pending.full():self.stats['dropped_busy']+=1;return False
            self.stats['offered']+=1
            recent=list(self.recent);activity_epoch=self.activity_epoch
        try:
            if getattr(frame,'ndim',None)!=3 or frame.shape[2]!=3 or min(frame.shape[:2])<=0 or frame.size>96_000_000:
                raise ValueError('invalid RGB frame')
            status=self.gui.session.snapshot()
            if status.get('status')!='running':return False
            snapshot=dict(getattr(self.gui,'_owner_stage_snapshot',{}))
            receipt={'schema':SCHEMA,'revision':REVISION,'observed_at':datetime.now().isoformat(timespec='milliseconds'),
                'source':source,'mode':str(adapter.mode),'last_stage_observation':snapshot,
                'session':{k:status.get(k) for k in ('status','generation','worker_alive')},
                'resume_epoch':getattr(self.gui,'_owner_stage_epoch',None),'recent_events':recent,
                'width':int(frame.shape[1]),'height':int(frame.shape[0]),'game_only':True,
                'game_input':False,'automatic_upload':False,'automatic_training':False,
                'classification_status':'unreviewed','confirmed_location':None,'reviewed_label':None,
                'forced_evidence':bool(force),'activity_epoch':activity_epoch}
            # Plain pixels: a frame that keeps its real screen sends every check of this worker to the word reader,
            # which the input worker's reads then queue behind.
            import numpy as np
            self.pending.put_nowait((np.array(frame),receipt))
            return True
        except queue.Full:
            with self.stats_lock:self.stats['dropped_busy']+=1
        except Exception as exc:
            with self.stats_lock:self.stats['errors']+=1;self.stats['last_error']=type(exc).__name__
        return False

    def _classifier(self):
        from owner_startup_stage import scene,DUNGEON,EXIT,MENU
        from owner_special_contexts import NAMES
        from project_adapter.secret_exploration import AUTO_NAMES
        from roi_runtime import RoiDetector
        names=list(dict.fromkeys([DUNGEON,EXIT,MENU,'체크_보스진입','체크_레이드진입',*AUTO_NAMES,*NAMES]))
        detector=RoiDetector(self.gui.project.root/'profiles'/self.gui.project.code,names)
        # This detector belongs to this worker only. Never share native state
        # with the action worker or infer activity from a stale UI caption.
        from owner_diagnostic_repairs import sleeping_hunt
        return lambda frame:'sleep_hunt' if sleeping_hunt(frame) else scene(detector,frame)

    def _status(self):
        with self.stats_lock:stats=dict(self.stats)
        stats.update(updated_at=datetime.now().isoformat(timespec='seconds'),queue_pending=self.pending.qsize())
        try:
            temp=self.folder/'collector-status.tmp'
            temp.write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(self.folder/'collector-status.json')
        except OSError:pass

    def _loop(self):
        connection=None;last_status=-1e30
        try:
            import numpy as np
            from PIL import Image
            self.folder.mkdir(parents=True,exist_ok=True)
            connection=sqlite3.connect(self.folder/'index.sqlite3')
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('''CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,observed_at TEXT,last_seen TEXT,predicted_kind TEXT,
                classification_status TEXT,reviewed_label TEXT,relative_dir TEXT,sha256 TEXT,
                width INTEGER,height INTEGER,occurrences INTEGER,fingerprint BLOB,revision TEXT)''')
            connection.commit()
            recent=deque(maxlen=256)
            for row in reversed(connection.execute('SELECT id,predicted_kind,fingerprint,relative_dir FROM scenes ORDER BY observed_at DESC LIMIT 256').fetchall()):
                # Deleted historical images remain valid log/index evidence,
                # but must not suppress the first new retained example.
                if len(row[2])==96*54 and (self.folder/row[3]/'screen.png').is_file():
                    recent.append((row[0],row[1],np.frombuffer(row[2],dtype='uint8').reshape(54,96)))
            total=sum(p.stat().st_size for p in self.folder.rglob('*') if p.is_file() and not p.is_symlink())
            with self.stats_lock:self.stats['stored_bytes']=total
            routine_saved={}
            classify=self.classifier or self._classifier()
            while not self.ending.is_set() or not self.pending.empty():
                try:frame,receipt=self.pending.get(timeout=.2)
                except queue.Empty:
                    if self.clock()-last_status>=5:self._status();last_status=self.clock()
                    continue
                try:
                    started=self.clock()
                    try:kind=classify(frame)
                    except Exception as exc:
                        kind='unknown';receipt['classification_error']=type(exc).__name__
                    receipt['predicted_kind']=kind;receipt['recognized_by_current_rules']=kind!='unknown'
                    receipt['classification_ms']=round((self.clock()-started)*1000,3)
                    signature=fingerprint(frame)
                    previous=next((ident for ident,k,fp in reversed(recent) if k==kind and similar(signature,fp)),None)
                    if previous:
                        connection.execute('UPDATE scenes SET last_seen=?,occurrences=occurrences+1 WHERE id=?',(receipt['observed_at'],previous))
                        connection.commit()
                        with self.stats_lock:self.stats['duplicates']+=1
                        continue
                    routine_key=(kind,receipt['mode'],receipt.get('activity_epoch',0))
                    routine=(kind in ('field','dungeon','sleep_hunt')
                             and receipt['source']=='runtime_capture' and not receipt.get('forced_evidence'))
                    if routine and self.clock()-routine_saved.get(routine_key,-1e30)<15:
                        with self.stats_lock:self.stats['routine_suppressed']+=1
                        continue
                    ident=datetime.now().strftime('%Y%m%dT%H%M%S-')+uuid.uuid4().hex[:8]
                    day=self.folder/datetime.now().strftime('%Y%m%d');day.mkdir(exist_ok=True)
                    temporary=day/('.pending-'+ident);temporary.mkdir()
                    image_path=temporary/'screen.png'
                    Image.fromarray(frame,'RGB').save(image_path,format='PNG',compress_level=3)
                    receipt.update(id=ident,image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest())
                    meta_path=temporary/'observation.json'
                    meta_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
                    size=image_path.stat().st_size+meta_path.stat().st_size
                    if total+size>self.max_bytes:
                        # Only our two freshly written, unpublished files. No
                        # existing capture is removed when the budget is hit.
                        image_path.unlink();meta_path.unlink();temporary.rmdir()
                        with self.stats_lock:self.stats['storage_full']=True
                        self.gui.logger.warning('화면 자료 저장공간 한도 도달 · 기존 자료 유지 · 추가 수집 보류')
                        continue
                    final=day/ident;temporary.replace(final);total+=size
                    if routine:
                        if len(routine_saved)>256:routine_saved.clear()
                        routine_saved[routine_key]=self.clock()
                    connection.execute('INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (ident,receipt['observed_at'],receipt['observed_at'],kind,'unreviewed',None,
                         str(final.relative_to(self.folder)),receipt['image_sha256'],receipt['width'],receipt['height'],1,signature.tobytes(),REVISION))
                    connection.commit();recent.append((ident,kind,signature))
                    with self.stats_lock:
                        self.stats['saved']+=1;self.stats['last_saved_at']=receipt['observed_at'];self.stats['last_saved_kind']=kind
                        self.stats['stored_bytes']=total
                    # Log each new unidentified screenshot; known screens are
                    # still archived as classification examples without spam.
                    if kind=='unknown':self.gui.logger.info('화면 자료 저장 · 미분류 화면 · %s',ident)
                except Exception as exc:
                    with self.stats_lock:self.stats['errors']+=1;self.stats['last_error']=type(exc).__name__
                    self.gui.logger.warning('화면 자료 저장 실패 · %s',type(exc).__name__)
                finally:
                    self.pending.task_done()
                    if self.clock()-last_status>=5:self._status();last_status=self.clock()
        except Exception as exc:
            with self.stats_lock:self.stats['errors']+=1;self.stats['last_error']=type(exc).__name__
            self.gui.logger.warning('화면 자료 수집기 초기화 실패 · %s',type(exc).__name__)
        finally:
            if connection is not None:connection.close()
            self._status()

    def flush(self,timeout=2):
        end=time.monotonic()+timeout
        while self.pending.unfinished_tasks and time.monotonic()<end:time.sleep(.01)

    def close(self):
        self.ending.set()
        if threading.current_thread() is not self.worker:self.worker.join(.3)
        super().close()


def append_to_bundle(path,folder):
    """Add recent unreviewed screens to the existing explicit local export."""
    import zipfile
    folder=Path(folder)
    files=sorted(folder.glob('????????/????????T??????-????????/observation.json'),reverse=True)
    count=0;total=0
    with zipfile.ZipFile(path,'a',zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            if item.is_symlink() or item.parent.is_symlink():continue
            image=item.with_name('screen.png')
            if not image.is_file() or image.is_symlink():continue
            size=item.stat().st_size+image.stat().st_size
            if count>=30 or total+size>60*1024**2:continue
            for source in (item,image):archive.write(source,'scene-corpus/'+source.relative_to(folder).as_posix())
            total+=size;count+=1
        archive.writestr('scene-corpus/export.json',json.dumps({'screens':count,'bytes':total,'local_export':True}))


def unknown_observed(gui,adapter,context,frame,source):
    """Preserve an exact unknown observation, even between periodic samples."""
    recorder=getattr(gui,'_owner_scene_archive',None)
    if recorder is not None:
        try:recorder.offer(frame,adapter,context,source=source,force=True)
        except Exception:pass


def install(gui):
    if getattr(gui,'_owner_scene_archive',None) is not None:return
    import runtime_capture,diagnostic_bundle
    from project_adapter._entry import Adapter
    recorder=SceneArchive(gui);gui._owner_scene_archive=recorder;gui.logger.addHandler(recorder)
    original_capture=runtime_capture.capture
    @wraps(original_capture)
    def capture(*a,**k):
        frame=original_capture(*a,**k);owner=getattr(LOCAL,'owner',None)
        if owner is not None:
            try:recorder.offer(frame,*owner,source=getattr(LOCAL,'source',None) or 'runtime_capture')
            except Exception:pass
        return frame
    runtime_capture.capture=capture
    for name,module in tuple(sys.modules.items()):
        if name.startswith('project_adapter') and module is not None:
            for key,value in tuple(vars(module).items()):
                if value is original_capture:setattr(module,key,capture)
    original_run=Adapter.run
    @wraps(original_run)
    def run(adapter,context,inputs):
        with capture_scope(adapter,context):return original_run(adapter,context,inputs)
    Adapter.run=run
    original_bundle=diagnostic_bundle.create_bundle
    def bundle(target):
        path=original_bundle(target)
        if target is gui:recorder.flush();append_to_bundle(path,recorder.folder)
        return path
    diagnostic_bundle.create_bundle=bundle
    def close(event):
        if event.widget is gui.root:gui.logger.removeHandler(recorder);recorder.close()
    gui.root.bind('<Destroy>',close,add='+')
