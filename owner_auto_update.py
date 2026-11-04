"""Signed release polling off Tk; cooperative stop and original-mode restart."""
from pathlib import Path
from functools import wraps
import json,logging,os,queue,shutil,subprocess,threading,time,urllib.request,urllib.error,uuid
from owner_update_core import load,save,verify_signed,verify_zip,MAX_ZIP,UpdateError
LOG=logging.getLogger('project_gui.DKB')
BASE='https://sihong-manager.duckdns.org/dkb-logs'

def resume_status(gui,snapshot):
    """An explicit one-shot TEST must never restart as a full macro."""
    test=getattr(gui,'_owner_reward_action_test',None)
    return 'stopped' if test is not None and test.active else snapshot['status']

def visible_log(message,level=logging.INFO):
    # The ordinary user-log filter rewrites technical update text. Supply the
    # explicit presentation field so the actual log window retains this line.
    LOG.log(level,message,extra={'gui_message':message,'state_transition':True})

def release_notice(cache,release):
    """A download alone is never reported as an applied update."""
    caption='현재 적용 버전 · '+str(release['sequence'])
    try:
        current=load((cache/'current.json').read_bytes())
        result=load((cache/'last-result.json').read_bytes())
        if (current.get('sequence')==release['sequence'] and current.get('version')==release['version']
            and result.get('ok') is True and result.get('sequence')==release['sequence']
            and (cache/'resume.json').is_file()):
            return '업데이트 완료 · 적용 버전 '+str(release['sequence'])
    except (OSError,ValueError,TypeError):pass
    return caption

def fetch(path,maximum,etag=None):
    headers={'User-Agent':'DKB-owner-update/1'}
    if etag:headers['If-None-Match']=etag
    request=urllib.request.Request(BASE+path,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            if not response.url.startswith(BASE+'/updates/'):raise UpdateError('update redirected outside release endpoint')
            raw=response.read(maximum+1)
            if len(raw)>maximum:raise UpdateError('update exceeds download bound')
            return raw,response.headers.get('ETag')
    except urllib.error.HTTPError as exc:
        if exc.code==304:return None,etag
        raise

class Bridge:
    def __init__(self,gui):
        self.gui=gui;self.root=Path(__file__).resolve().parent.parent;self.cache=self.root/'.owner-update'
        self.control=gui.project.root/'settings/owner-update-control.json';self.events=queue.SimpleQueue()
        self.cancel=threading.Event();self.internal=False;self.closing_for_update=False;self.updating=False;self.pending=None;self.helper=None
        self._pending_auto_start_epoch=None;self._submitting_resume=False
        self.trust=load((Path(__file__).parent/'owner_update_trust.json').read_bytes())
        self.release=load((Path(__file__).parent/'owner_release.json').read_bytes())
        self.sequence=self.release['sequence']
        if (self.cache/'current.json').exists():self.sequence=max(self.sequence,load((self.cache/'current.json').read_bytes())['sequence'])
        self.blocked=set()
        if (self.cache/'last-result.json').exists():
            last=load((self.cache/'last-result.json').read_bytes())
            if last.get('blocked_sequence'):self.blocked.add(last['blocked_sequence'])
        self.epoch=load(self.control.read_bytes()).get('epoch',0) if self.control.exists() else 0
        self.original_stop=gui.session.stop
        self._wire()
        threading.Thread(target=self._reader,name='dkb-update-reader',daemon=True).start()
        self.gui.root.after(250,self.announce_release)
        self.gui.root.after(300,self.poll);self.gui.root.after(500,self.resume)
    def announce_release(self):
        if not self.gui.closed.is_set():visible_log(release_notice(self.cache,self.release))
    def intent(self,desired,*,user_exit=False):
        self.epoch+=1;save(self.control,{'epoch':self.epoch,'desired':desired,'user_exit':user_exit,'at':time.time()})
    def _wire(self):
        session=self.gui.session
        for name,desired in [('start','running'),('resume','running'),('pause','paused'),('stop','stopped')]:
            original=getattr(session,name)
            def wrapped(*args,_original=original,_desired=desired,_name=name,**kwargs):
                if self.updating and _desired=='running':
                    LOG.info('업데이트 적용 중 · 완료 후 시작을 다시 눌러 주세요');return
                pending=getattr(self,'_pending_auto_start_epoch',None)
                if pending is not None and _name in ('start','resume'):
                    self._pending_auto_start_epoch=None
                    if pending!=self.epoch:
                        LOG.info('업데이트 자동 시작 취소 · 이후 사용자 중지·일시정지 우선');return
                result=_original(*args,**kwargs)
                if not self.internal and not self.closing_for_update:self.intent(_desired)
                return result
            setattr(session,name,wrapped)
        original_close=self.gui.close
        @wraps(original_close)
        def close(*args,**kwargs):
            result=original_close(*args,**kwargs)
            if self.gui.closed.is_set():
                if not self.internal and not self.closing_for_update:
                    self.intent('stopped',user_exit=True)
                    if self.pending:save(self.pending/'cancel',{})
                self.cancel.set()
            return result
        self.gui.close=close
        self.gui.root.protocol('WM_DELETE_WINDOW',close)
        original_start=self.gui.start_requested
        def start_requested():
            if not getattr(self,'_submitting_resume',False):self._pending_auto_start_epoch=None
            return original_start()
        self.gui.start_requested=start_requested
        original_mode=self.gui.set_execution_mode
        def change_mode(mode):
            result=original_mode(mode)
            if not self.internal:self.intent('stopped')
            return result
        self.gui.set_execution_mode=change_mode
    def check(self):self.events.put(('check',None));return True
    def _reader(self):
        etag=None;acknowledged=False
        while not self.cancel.is_set():
            try:
                raw,new_etag=fetch('/updates/latest.json',1024*1024,etag)
                if raw is not None:
                    # Old/current releases are ordinary no-ops, not failures.
                    document=verify_signed(raw,self.trust,0)
                    if not acknowledged:
                        visible_log('업데이트 확인 · 현재 '+str(self.sequence)+' / 최신 '+str(document['sequence']));acknowledged=True
                    if document['sequence']>self.sequence and document['sequence'] not in self.blocked:
                        bundle,_=fetch(document['bundle'],MAX_ZIP)
                        folder=self.cache/'downloads'/uuid.uuid4().hex;folder.mkdir(parents=True)
                        (folder/'release.json').write_bytes(raw);(folder/'bundle.zip').write_bytes(bundle)
                        verify_zip(folder/'bundle.zip',document)
                        self.events.put(('release',(folder,document)));return
                    etag=new_etag
            except Exception as exc:
                # Network/signature/download failure leaves the running task
                # untouched. No repeated GUI warning for an unchanged failure.
                LOG.debug('자동 업데이트 확인 보류 · %s',type(exc).__name__)
            self.cancel.wait(15)
    def poll(self):
        if self.gui.closed.is_set():self.cancel.set();return
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='release' and not self.updating:
                self.pending,self.doc=value
                try:self.begin(*value)
                except Exception as exc:self.fail_handoff(type(exc).__name__)
            elif kind=='check':LOG.info('자동 업데이트 서버 확인 중 · 최대 15초 내 확인')
        if self.updating:self.finish_handoff()
        self.gui.root.after(100,self.poll)
    def begin(self,folder,doc):
        from owner_hunt_rules_candidate import configured_identity
        snapshot=self.gui.session.snapshot();status=resume_status(self.gui,snapshot);self.was_running=status=='running'
        self.mode=self.gui.load_settings_model().mode;self.profile=configured_identity(self.gui.project.root)
        self.intent(status)
        self.pending=folder;self.doc=doc;self.helper=None;self.updating=True;self.stop_sent=False;self.began=time.monotonic()
        visible_log('업데이트 수신 · 적용 버전 '+str(doc['sequence'])+' · 현재 작업 정리 후 적용')
    def fail_handoff(self,reason):
        self.blocked.add(self.doc['sequence']);self.updating=False
        try:save(self.pending/'cancel',{})
        except OSError:pass
        LOG.warning('업데이트 보류 · %s · 현재 프로그램 유지',reason,
                    extra={'gui_message':'업데이트 보류 · 현재 프로그램 유지','state_transition':True})
        def retry_reader():
            if not self.cancel.wait(30):self._reader()
        threading.Thread(target=retry_reader,name='dkb-update-retry',daemon=True).start()
    def finish_handoff(self):
        try:
            if self.helper is None:
                helpers=self.pending/'helper';helpers.mkdir(exist_ok=True)
                for name in ['owner_update_core.py','owner_update_worker.py','owner_update_trust.json']:
                    shutil.copy2(Path(__file__).parent/name,helpers/name)
                pids=[os.getpid()]
                parent=os.environ.get('DKB_START_OWNER_PID','')
                if parent.isdigit() and int(parent)!=os.getpid():pids.append(int(parent))
                save(self.pending/'job.json',{'root':str(self.root),'wait_pids':pids,'was_running':self.was_running,
                    'epoch':self.epoch,'mode':self.mode,'profile':self.profile,'nonce':uuid.uuid4().hex})
                python=self.root/'vendor/BIOL_Runtime/1.1.0/python/pythonw.exe'
                self.helper=subprocess.Popen([str(python),str(helpers/'owner_update_worker.py'),str(self.pending/'job.json')],
                    cwd=str(helpers),creationflags=0x08000000)
                self.helper_at=time.monotonic();return
            ready=self.pending/'ready.json'
            if not ready.exists():
                if self.helper.poll() is not None or time.monotonic()-self.helper_at>15:self.fail_handoff('적용기 준비 미확인')
                return
            if load(ready.read_bytes()).get('pid')!=self.helper.pid or self.helper.poll() is not None:
                self.fail_handoff('적용기 종료 또는 식별 변경');return
            if not self.stop_sent:
                self.internal=True
                try:self.original_stop()
                finally:self.internal=False
                self.stop_sent=True;self.began=time.monotonic()
            snapshot=self.gui.session.snapshot()
            if snapshot['worker_alive']:
                if time.monotonic()-self.began>120:self.fail_handoff('기존 작업 정리 미확인 · 강제 종료 없음')
                return
            if snapshot.get('error'):self.was_running=False;self.intent('stopped')
            self.closing_for_update=True;self.internal=True
            try:self.gui.close(force=True)
            finally:self.internal=False
            self.cancel.set()
        except Exception as exc:self.fail_handoff(type(exc).__name__)
    def resume(self):
        if self.gui.closed.is_set():return
        token=self.cache/'resume.json'
        if not token.exists():return
        try:
            from owner_hunt_rules_candidate import configured_identity
            request=load(token.read_bytes())
            control=load(self.control.read_bytes()) if self.control.exists() else {}
            if (time.time()>request['expires'] or request['epoch']!=control.get('epoch')
                    or not request.get('resume') or control.get('desired')!='running'
                    or request.get('profile')!=configured_identity(self.gui.project.root)):
                token.unlink();visible_log('업데이트 후 중지·일시정지 상태 유지');return
            preparation=getattr(self.gui,'_paddle_preparation',None)
            busy=getattr(getattr(self.gui,'input_preparation',None),'busy',lambda:False)()
            ready=preparation is None or preparation.done.is_set()
            owner_preparation=getattr(self.gui,'_owner_ocr_readiness',None)
            if owner_preparation is not None:
                ready=ready and owner_preparation.done.is_set() and owner_preparation.error is None
            if not ready or busy or not getattr(self.gui.game_window,'hwnd',None):
                self.gui.root.after(500,self.resume);return
            if self.gui.session.snapshot()['worker_alive']:
                token.unlink();return
            token.unlink() # Consume once before submitting a Start.
            self.internal=True
            try:self.gui.set_execution_mode(request['mode'])
            finally:self.internal=False
            self._pending_auto_start_epoch=self.epoch;self._submitting_resume=True
            try:self.gui.start_requested()
            finally:self._submitting_resume=False
            visible_log('업데이트 후 이전 실행 모드로 자동 시작 요청')
        except Exception as exc:
            LOG.warning('업데이트 후 자동 시작 보류 · %s',type(exc).__name__)

def install(gui):
    if getattr(gui,'_owner_auto_update',None):return
    try:
        gui._owner_auto_update=Bridge(gui)
        LOG.info('자동 업데이트 연결 · 현재 릴리스 %s · 15초 간격 확인',gui._owner_auto_update.sequence)
    except Exception:LOG.exception('자동 업데이트 연결 실패 · 기존 프로그램 유지')
