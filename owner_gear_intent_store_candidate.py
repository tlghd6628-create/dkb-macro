"""Durable guard intent for candidate tests; independent of production."""
from dataclasses import asdict
import json,os,tempfile,time
from pathlib import Path
from owner_gear_decision_candidate import Observation


class IntentStore:
    def __init__(self,path):self.path=Path(path)
    def _read(self):
        if not self.path.exists():return {'version':1,'pending':None}
        try:
            obj=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(obj,dict) or obj.get('version')!=1 or 'pending' not in obj:raise ValueError()
            pending=obj['pending']
            if pending is not None:
                if not isinstance(pending,dict) or pending.get('kind') not in ('enhance','breakthrough','awaken'):raise ValueError()
                pending['before']=Observation(**pending['before']);pending['second']=Observation(**pending['second'])
            return obj
        except (ValueError,TypeError,KeyError,OSError) as exc:raise RuntimeError('강화 실행 기록 확인 필요') from exc
    def pending(self):return self._read()['pending']
    def _locked(self,callback):
        self.path.parent.mkdir(parents=True,exist_ok=True);lock=self.path.with_suffix(self.path.suffix+'.lock')
        import msvcrt
        fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600)
        if os.fstat(fd).st_size==0:
            os.lseek(fd,0,os.SEEK_SET);os.write(fd,b'0')
        os.lseek(fd,0,os.SEEK_SET)
        try:msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        except OSError as exc:
            os.close(fd);raise RuntimeError('강화 기록 잠금 확인 필요') from exc
        try:return callback()
        finally:
            os.lseek(fd,0,os.SEEK_SET)
            try:msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
            finally:os.close(fd)
    def _write(self,obj):
        p=obj['pending']
        if p is not None:
            p=dict(p);p['before']=asdict(p['before']);p['second']=asdict(p['second']);obj=dict(obj,pending=p)
        fd,tmp=tempfile.mkstemp(prefix='.gear-intent-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def begin(self,value):
        def action():
            obj=self._read()
            if obj['pending'] is not None:raise RuntimeError('이전 강화 결과 미확인')
            prepared=dict(value,phase='prepared',created_at_epoch=time.time())
            self._write(dict(obj,pending=prepared))
        return self._locked(action)
    def mark_sent(self):
        def action():
            obj=self._read();pending=obj['pending']
            if pending is None or pending.get('phase')!='prepared':raise RuntimeError('강화 기록 준비 상태 확인 필요')
            pending['phase']='sent';pending['sent_at_epoch']=time.time();self._write(obj)
        return self._locked(action)
    def abort_prepared(self,reason):
        def action():
            obj=self._read();pending=obj['pending']
            if pending is None:return False
            if pending.get('phase')!='prepared':return False
            obj['pending']=None;obj['last_result']='preinput_aborted';obj['last_reason']=str(reason)[:160]
            self._write(obj);return True
        return self._locked(action)
    def close_absent(self,reason):
        """Only for a sent record whose item is proved gone. The record stays readable."""
        def action():
            obj=self._read();pending=obj['pending']
            if pending is None or pending.get('phase')!='sent':return False
            kept=dict(pending);kept['before']=asdict(pending['before']);kept['second']=asdict(pending['second'])
            kept.pop('item_icon',None)
            obj['pending']=None;obj['last_result']='item_gone';obj['last_reason']=str(reason)[:160]
            obj['closed_absent']=(obj.get('closed_absent') or [])[-9:]+[dict(kept,closed_at_epoch=time.time())]
            self._write(obj);return True
        return self._locked(action)
    def complete(self,result):
        def action():
            obj=self._read()
            if obj['pending'] is None:raise RuntimeError('진행 중인 강화 기록이 없습니다')
            obj['pending']=None;obj['last_result']=result;self._write(obj)
        return self._locked(action)
