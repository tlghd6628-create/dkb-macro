"""Dedicated Telegram bot: encrypted local settings and single-owner commands."""
from __future__ import annotations
import ctypes
from dataclasses import dataclass,field,asdict
import io
import json
import os
from pathlib import Path
import queue
import re
import secrets
import threading
import time
from urllib import request,error
from email.utils import parsedate_to_datetime

TOKEN=re.compile(r'[0-9]{5,20}:[A-Za-z0-9_-]{20,200}')
KEYBOARD={'keyboard':[['시작','일시정지','중지'],['현재 화면','상태','성장현황'],['스케줄표','오늘 일정','이번 주 일정']],
          'resize_keyboard':True,'is_persistent':True}
COMMANDS={'시작':'start','/실행':'start','/run':'start','/시작':'start',
          '일시정지':'pause','/pause':'pause','/일시정지':'pause',
          '계속':'start','재개':'start','/resume':'start',
          '중지':'stop','정지':'stop','/stop':'stop','/중지':'stop',
          '현재 화면':'screen','현재화면':'screen','/screen':'screen',
          '상태':'status','/status':'status','/start':'menu','/menu':'menu',
          '성장현황':'growth','성장 현황':'growth','현재값':'growth','/growth':'growth','/성장':'growth',
          '스케줄표':'schedule','스케줄':'schedule','/schedule':'schedule','/일정':'schedule',
          '오늘 일정':'schedule_today','오늘일정':'schedule_today','/today':'schedule_today',
          '이번 주 일정':'schedule_week','이번주일정':'schedule_week','주간일정':'schedule_week','/week':'schedule_week'}


def protect(raw,decrypt=False):
    if os.name!='nt':raise ValueError('Windows 사용자 보호 저장소가 필요합니다.')
    class Blob(ctypes.Structure):
        _fields_=[('size',ctypes.c_uint32),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,
                      ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
    function.restype=ctypes.c_int
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise ValueError('텔레그램 설정의 Windows 사용자 보호 처리를 완료하지 못했습니다.')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


@dataclass
class Config:
    token:str=field(default='',repr=False)
    enabled:bool=False
    bot_id:int=0
    username:str=''
    chat_id:int=0
    user_id:int=0
    offset:int=0

    def validate(self):
        if type(self.enabled) is not bool:raise ValueError('텔레그램 사용 설정이 올바르지 않습니다.')
        if self.token and not TOKEN.fullmatch(self.token):raise ValueError('BotFather에서 받은 봇 토큰을 확인해 주세요.')
        if self.enabled and not self.token:raise ValueError('봇 토큰을 입력해 주세요.')
        if any(type(v) is not int or v<0 for v in (self.bot_id,self.chat_id,self.user_id,self.offset)):
            raise ValueError('텔레그램 연결 정보가 올바르지 않습니다.')
        if bool(self.chat_id)!=bool(self.user_id) or self.chat_id!=self.user_id:
            raise ValueError('개인 대화 연결 정보가 올바르지 않습니다.')
        if self.bot_id and self.token and int(self.token.split(':',1)[0])!=self.bot_id:
            raise ValueError('봇 연결 정보를 다시 확인해 주세요.')


class Store:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock();self.value=Config()
        if self.path.exists():
            try:self.value=Config(**json.loads(protect(self.path.read_bytes(),True).decode('utf-8')));self.value.validate()
            except Exception:raise ValueError('텔레그램 설정을 읽지 못했습니다. 연결 설정을 다시 확인해 주세요.') from None

    def snapshot(self):
        with self.lock:return Config(**asdict(self.value))

    def update(self,**fields):
        with self.lock:
            value=Config(**dict(asdict(self.value),**fields));value.validate()
            raw=protect(json.dumps(asdict(value),ensure_ascii=False).encode('utf-8'))
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            temp.write_bytes(raw);temp.replace(self.path)
            self.value=value
            return self.snapshot()

    def acknowledge(self,ident):
        with self.lock:
            if ident<self.value.offset:return False
            self.update(offset=ident+1)
            return True


class ApiError(ValueError):
    def __init__(self,code=0,retry=3):
        self.code=code;self.retry=max(1,min(60,retry))
        hints={401:'봇 토큰을 확인해 주세요.',403:'봇 대화에서 시작을 누르고 차단 여부를 확인해 주세요.',
               409:'같은 봇을 다른 프로그램이 사용 중입니다. 도깨비 전용 봇으로 연결해 주세요.',
               429:'요청이 많습니다. 잠시 후 다시 시도합니다.'}
        super().__init__(hints.get(code,'텔레그램 연결을 확인해 주세요.'))


class Client:
    def __init__(self,opener=None):
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        self.opener=opener or request.build_opener(NoRedirect).open
        self.server_clock=None

    def server_now(self):
        clock=self.server_clock
        return None if clock is None else clock[0]+max(0,time.monotonic()-clock[1])

    def call(self,token,method,fields=None,photo=None,timeout=10):
        if not TOKEN.fullmatch(token):raise ValueError('봇 토큰 형식을 확인해 주세요.')
        if method not in ('getMe','getWebhookInfo','getUpdates','sendMessage','sendPhoto'):
            raise ValueError('지원하지 않는 요청입니다.')
        fields=fields or {}
        headers={}
        if photo is None:
            body=json.dumps(fields,ensure_ascii=False).encode('utf-8');headers['Content-Type']='application/json'
        else:
            if method!='sendPhoto' or not isinstance(photo,bytes) or not 0<len(photo)<=9_000_000:
                raise ValueError('게임 화면 파일을 확인해 주세요.')
            boundary='DKB'+secrets.token_hex(16);parts=[]
            for key,value in fields.items():
                text=json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value)
                parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+text+'\r\n').encode())
            parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="photo"; filename="DKB_screen.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+photo+b'\r\n')
            parts.append(('--'+boundary+'--\r\n').encode());body=b''.join(parts)
            headers['Content-Type']='multipart/form-data; boundary='+boundary
        req=request.Request('https://api.telegram.org/bot'+token+'/'+method,data=body,headers=headers,method='POST')
        try:
            with self.opener(req,timeout=timeout) as response:
                # Telegram message dates and a PC's wall clock need not agree.
                # Keep the official HTTPS response clock on a monotonic anchor.
                try:
                    headers=getattr(response,'headers',None)
                    value=headers.get('Date') if headers is not None else None
                    if value:
                        stamp=parsedate_to_datetime(value)
                        if stamp.tzinfo is not None:self.server_clock=(stamp.timestamp(),time.monotonic())
                except (ValueError,TypeError,OverflowError):pass
                data=json.loads(response.read(1_048_576))
            if data.get('ok') is not True:raise ApiError(int(data.get('error_code',0)))
            return data['result']
        except error.HTTPError as exc:
            retry=3
            try:retry=int(json.loads(exc.read(65536)).get('parameters',{}).get('retry_after',3))
            except Exception:pass
            raise ApiError(exc.code,retry) from None
        except ApiError:raise
        except Exception:raise ApiError() from None  # Never expose a URL containing the token.


class Router:
    def __init__(self,store,started=None):
        self.store=store;self.started=time.time() if started is None else started
        self.started_tick=time.monotonic();self.clock_source='pc_fallback'
        self.token=store.snapshot().token
        self.code='';self.expires=0.;self.lock=threading.RLock()

    def sync_server_clock(self,server_now):
        if server_now is not None:
            self.started=server_now-max(0,time.monotonic()-self.started_tick)
            self.clock_source='telegram_https_date'

    def issue_code(self):
        with self.lock:
            self.code=secrets.token_urlsafe(9);self.expires=time.monotonic()+300
            return self.code

    def handle(self,update,now=None):
        with self.store.lock:
            return self._handle_locked(update,now)

    def _handle_locked(self,update,now=None):
        now=time.time() if now is None else now
        ident=update.get('update_id');cfg=self.store.snapshot()
        if not cfg.enabled or cfg.token!=self.token or type(ident) is not int:return None
        # Persist acknowledgement before returning any action: no restart replay.
        if not self.store.acknowledge(ident):return None
        msg=update.get('message',{})
        if not isinstance(msg,dict):return None
        chat=msg.get('chat',{});sender=msg.get('from',{})
        if not isinstance(chat,dict) or not isinstance(sender,dict):return None
        if (chat.get('type')!='private' or type(chat.get('id')) is not int or chat['id']<=0
            or sender.get('id')!=chat['id'] or sender.get('is_bot') is True
            or any(k in msg for k in ('forward_origin','forward_date','via_bot'))):return None
        stamp=msg.get('date')
        if type(stamp) is not int or stamp<int(self.started) or not -5<=now-stamp<=60:return None
        text=msg.get('text','')
        if not isinstance(text,str) or len(text)>300:return None
        text=text.strip()
        if cfg.chat_id and (cfg.chat_id!=chat['id'] or cfg.user_id!=sender['id']):return None
        if not cfg.chat_id:
            if text.startswith('/연결 '):
                supplied=text.split(maxsplit=1)[1].strip()
                with self.lock:
                    if self.code and time.monotonic()<self.expires and secrets.compare_digest(supplied,self.code):
                        self.store.update(chat_id=chat['id'],user_id=sender['id'])
                        self.code='';self.expires=0.
                        return {'kind':'paired','chat_id':chat['id'],'update_id':ident,'date':stamp}
            return {'kind':'pair_help','chat_id':chat['id'],'update_id':ident,'date':stamp,
                    'reason':'invalid_code' if text.startswith('/연결 ') else 'needs_pairing'}
        command=COMMANDS.get(text)
        growth_page=None
        if command is None:
            match=re.fullmatch(r'(?:성장현황|성장 현황|현재값|/growth)\s+([1-9]\d?)',text)
            if match:command='growth';growth_page=int(match[1])
        if not command:return None
        result={'kind':command,'chat_id':chat['id'],'update_id':ident,'date':stamp,
                'queued_at':time.monotonic(),'clock_source':self.clock_source,'age_seconds':round(now-stamp,3)}
        if growth_page is not None:result['page']=growth_page
        return result


class Service:
    def __init__(self,store,events,client=None):
        self.store=store;self.events=events;self.client=client or Client()
        self.router=Router(store);self.stop=threading.Event();self.outbox=queue.Queue(maxsize=16)
        self.token=store.snapshot().token
        self.reader=threading.Thread(target=self._read,name='dkb-telegram-poll',daemon=True)
        self.sender=threading.Thread(target=self._send,name='dkb-telegram-send',daemon=True)

    def start(self):self.reader.start();self.sender.start()
    def close(self):self.stop.set()

    def reply(self,chat,text,photo=None):
        if self.stop.is_set():return
        try:self.outbox.put_nowait((chat,text,photo))
        except queue.Full:self.status('텔레그램 응답이 밀리고 있습니다. 잠시 후 다시 요청해 주세요.')

    def status(self,text):self.events.put(('status',(self,text)))

    def _active(self):
        cfg=self.store.snapshot()
        return not self.stop.is_set() and cfg.enabled and cfg.token==self.token

    def _read(self):
        while self._active():
            try:
                cfg=self.store.snapshot()
                updates=self.client.call(self.token,'getUpdates',{'offset':cfg.offset,'limit':50,'timeout':20,'allowed_updates':['message']},timeout=25)
                if not self._active():break
                server_now=getattr(self.client,'server_now',lambda:None)()
                self.router.sync_server_clock(server_now)
                self.status('연결됨' if cfg.chat_id else '연결 코드 입력 대기')
                for update in updates:
                    if not self._active():break
                    item=self.router.handle(update,now=getattr(self.client,'server_now',lambda:None)())
                    if not item:continue
                    if item['kind']=='pair_help':
                        self.reply(item['chat_id'],'연결 코드가 다르거나 만료됐습니다. PC 설정에서 다시 발급해 주세요.'
                                   if item.get('reason')=='invalid_code' else 'PC 프로그램의 텔레그램 설정에 표시된 /연결 명령을 보내 주세요.')
                    else:self.events.put(('command',(self,item)))
                if not updates:self.stop.wait(.1)
            except ApiError as exc:
                self.status(str(exc))
                if exc.code==401:break
                self.stop.wait(max(exc.retry,5 if exc.code==409 else 2))
            except Exception:
                self.status('텔레그램 설정 저장 또는 연결을 확인해 주세요.')
                self.stop.wait(5)

    def _send(self):
        while self._active():
            try:chat,text,photo=self.outbox.get(timeout=.5)
            except queue.Empty:continue
            cfg=self.store.snapshot()
            if not self._active() or (cfg.chat_id and chat!=cfg.chat_id):continue
            fields={'chat_id':chat}
            if cfg.chat_id:fields['reply_markup']=KEYBOARD
            fields['caption' if photo else 'text']=text[:900 if photo else 3500]
            if getattr(text,'telegram_html',False) and not photo:fields['parse_mode']='HTML'
            try:self.client.call(self.token,'sendPhoto' if photo else 'sendMessage',fields,photo=photo,timeout=12)
            except ApiError as exc:self.status(str(exc))


def jpeg(image):
    image=image.copy().convert('RGB');image.thumbnail((1920,1080))
    output=io.BytesIO();image.save(output,format='JPEG',quality=90)
    return output.getvalue()
