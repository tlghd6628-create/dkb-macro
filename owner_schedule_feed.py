"""Bounded log queue + independent SQLite worker. No capture/OCR/input."""
from datetime import datetime,timedelta
from pathlib import Path
import copy,json,logging,queue,threading,time
from owner_schedule import Book,parse_line,events_for,project,now_kst,KST,game_day


def read_json(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError,TypeError):return default


class LogFeed(logging.Handler):
    def __init__(self,collector):super().__init__();self.collector=collector;self.last_quest={}
    def emit(self,record):
        try:
            message=record.getMessage()
            if not message.startswith(('자동 기능 ','필드','영기 수련','문파협력 예약','문파 신청','퀘스트 상태판정','퀘스트 전투 보류','승천','보물찾기','일일 임무','주간 임무','만귀비경','사냥터 이동','전래동화 비경','비경')):return
            if message.startswith('퀘스트 상태판정'):
                now=time.monotonic()
                if now-self.last_quest.get(message,-1e30)<30:return
                if len(self.last_quest)>64:self.last_quest.clear()
                self.last_quest[message]=now
            at=datetime.fromtimestamp(record.created,KST).replace(microsecond=int(record.msecs)*1000)
            self.collector.enqueue(('log',at,message))
        except Exception:pass


class Collector:
    def __init__(self,root,logger,replay=True):
        self.root=Path(root);self.logger=logger;self.replay=replay
        self.queue=queue.Queue(maxsize=1024);self.closed=threading.Event();self.lock=threading.RLock()
        self.pending=None;self.latest=None;self.latest_today=None;self.issue='기존 기록을 불러오는 중';self.dropped=0
        self.handler=LogFeed(self);logger.addHandler(self.handler)
        self.worker=threading.Thread(target=self._work,name='dkb-schedule-ledger',daemon=True);self.worker.start()

    def enqueue(self,value):
        if self.closed.is_set():return False
        try:self.queue.put_nowait(value);return True
        except queue.Full:self.dropped+=1;return False

    def request(self,status,day=None,task=''):
        with self.lock:self.pending=(status,day,str(task)[:100])

    def snapshot(self,*,today=False):
        with self.lock:
            result=copy.deepcopy(self.latest_today if today else self.latest)
            if result:result.update(issue=self.issue,dropped=self.dropped)
            return result

    def identity(self):
        data=read_json(self.root/'settings/manager_identity.json',{})
        return '%s / %s'%(str(data.get('server_name') or '서버 미설정')[:40],str(data.get('character_name') or '캐릭터 미설정')[:40])

    def restore_logs(self,book,identity):
        today=now_kst().date();truncated=False
        for offset in range(8, -1,-1):
            path=self.root/'logs'/((today-timedelta(days=offset)).isoformat()+'.log')
            if not path.exists():continue
            with path.open('rb') as stream:
                size=path.stat().st_size
                if size>8*1024*1024:stream.seek(size-8*1024*1024);stream.readline();truncated=True
                for raw in stream:
                    if self.closed.is_set():return
                    parsed=parse_line(raw.decode('utf-8',errors='replace').strip())
                    if parsed:book.ingest(identity,*parsed,source='기존 PC 로그·캐릭터 일치 미검증')
            book.flush()
        self.issue='큰 로그는 최근 8MiB만 복원했습니다. 누락 기록은 미확인으로 표시합니다.' if truncated else ''

    def _work(self):
        book=None
        try:
            book=Book(self.root/'settings/owner-schedule.sqlite3')
            identity=self.identity()
            if self.replay:self.restore_logs(book,identity)
            else:self.issue=''
            last_flush=time.monotonic();view=('stopped',None,'')
            while not self.closed.is_set() or not self.queue.empty():
                try:job=self.queue.get(timeout=.2)
                except queue.Empty:job=None
                identity=self.identity()
                if job:
                    kind,*args=job
                    if kind=='log':book.ingest(identity,*args)
                    elif kind in ('manual','unmark'):
                        key,at=args
                        book.apply(identity,key,kind,at,'게임에서 완료 확인' if kind=='manual' else '사용자 완료 확인 취소',source='사용자 확인')
                        book.flush()
                if time.monotonic()-last_flush>=1:
                    book.flush();last_flush=time.monotonic()
                    with self.lock:pending=self.pending;self.pending=None
                    if pending:view=pending
                    status,day,task=view;when=now_kst()
                    if day and day!=game_day(when).isoformat():
                        when=datetime.fromisoformat(day).replace(hour=12,tzinfo=KST)
                    model=read_json(self.root/'settings/auto-settings.json',{})
                    model=dict(model,runtime_task=task)
                    # The native custom tab stores prefixed values.
                    if model.get('mode')=='custom':
                        values=model.get('values',{})
                        model=dict(model,values={**values,**{k[7:]:v for k,v in values.items() if k.startswith('custom.')}})
                    snapshot=project(book,identity,self.root,model,status,when)
                    current=snapshot if snapshot['day']==game_day(now_kst()).isoformat() else project(book,identity,self.root,model,status)
                    with self.lock:self.latest=snapshot;self.latest_today=current
        except Exception as exc:
            self.issue='스케줄 기록을 읽거나 저장하지 못했습니다. 기존 파일을 보존했습니다. ('+type(exc).__name__+')'
        finally:
            if book:
                try:book.close()
                except Exception:pass

    def close(self):
        self.logger.removeHandler(self.handler);self.closed.set()
        self.worker.join(.4)
