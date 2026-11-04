"""Opt-in per-PC diagnostics transport; never owns game input or screenshots."""
import base64,hashlib,io,json,logging,queue,re,threading,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from owner_telemetry_protocol import Spool,envelope

BASE='https://sihong-manager.duckdns.org/dkb-logs'
LOG=logging.getLogger('project_gui.DKB')

def request(path,data,token=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf8')
 # Fixed HTTPS destination, platform certificate verification, no redirects
 # carrying credentials to another host.
 from urllib.request import build_opener,HTTPRedirectHandler
 class NoRedirect(HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 with build_opener(NoRedirect()).open(Request(BASE+path,data=raw,headers=headers),timeout=8) as r:
  body=r.read(1048577)
  if len(body)>1048576:raise ValueError('response too large')
  return json.loads(body)

class Credentials:
 def __init__(self,root):self.path=Path(root)/'settings/diagnostic-device.dat'
 def read(self):
  if not self.path.exists():return None
  import win32crypt
  data=json.loads(win32crypt.CryptUnprotectData(self.path.read_bytes(),None,None,None,0)[1])
  if not isinstance(data,dict) or not all(isinstance(data.get(k),str) and data[k] for k in ('device','token','alias')):raise ValueError('device record')
  return data
 def write(self,data):
  import win32crypt,os
  raw=json.dumps(data).encode('utf8');sealed=win32crypt.CryptProtectData(raw,'DKB diagnostics device',None,None,None,0)
  self.path.parent.mkdir(parents=True,exist_ok=True)
  temp=self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
  try:temp.write_bytes(sealed);os.replace(temp,self.path)
  finally:
   if temp.exists():temp.unlink()

class Transport(logging.Handler):
 def __init__(self,root,*,credential_store=None,sender=request,start=True):
  super().__init__(logging.INFO)
  self.root=Path(root);self.credentials=credential_store or Credentials(root);self.sender=sender
  try:self.version=str(json.loads((Path(__file__).parent/'owner_release.json').read_text(encoding='utf-8'))['version'])[:80]
  except (OSError,ValueError,KeyError):self.version='r21-20261102'
  self.q=queue.Queue(1024);self.stop_event=threading.Event();self.lock_state=threading.RLock()
  self.spool=Spool(self.root/'settings/diagnostic-spool.json');self.last={};self.sequence=0
  self.pictures=queue.Queue(128);self.picture_path=self.root/'settings/diagnostic-picture-queue.json'
  try:self.pending_pictures=json.loads(self.picture_path.read_text(encoding='utf8'))[:100] if self.picture_path.exists() else []
  except (OSError,ValueError,TypeError):self.pending_pictures=[]
  self.device=None;self.state='미연결';self.last_sent=None;self.dropped=0;self.last_error=None;self.last_unknown_picture=-1e30
  try:self.device=self.credentials.read()
  except Exception:self.last_error='이 PC의 연결 정보를 다시 등록해 주세요.'
  if self.device:self.state='전송 대기'
  self.thread=threading.Thread(target=self.run,name='DKB-diagnostic-upload',daemon=True)
  if start:self.thread.start()
 def emit(self,record):
  # Do not record our own errors or start an upload loop from the logger.
  if not self.device or record.name.startswith('dkb.telemetry'):return
  try:
   message=record.getMessage()
   if '퀘스트 상태판정:' in message:return
   match=re.search(r'진행 진단 저장 완료 · (\d{8}T\d{6}Z-[0-9a-f]{8})',message)
   unknown=re.search(r'화면 자료 저장 · 미분류 화면 · (\d{8}T\d{6}-[0-9a-f]{8})',message)
   if match:self.pictures.put_nowait(('incident',match[1]))
   elif unknown and time.monotonic()-self.last_unknown_picture>=60:
    self.pictures.put_nowait(('unknown',unknown[1]));self.last_unknown_picture=time.monotonic()
   kind='error' if record.levelno>=logging.ERROR else 'warning' if record.levelno>=logging.WARNING else 'info'
   self.q.put_nowait((kind,message))
  except Exception:self.dropped+=1
 def enroll(self,code):
  if not isinstance(code,str) or not 20<=len(code.strip())<=100:raise ValueError('연결 코드를 확인해 주세요.')
  if self.device:raise ValueError('이미 연결된 PC입니다.')
  data=self.sender('/v1/enroll',{'code':code.strip()})
  if not isinstance(data,dict) or not all(isinstance(data.get(k),str) and data[k] for k in ('device','token','alias')):raise ValueError('연결 응답 확인 필요')
  self.credentials.write(data)
  with self.lock_state:self.device=data;self.state='전송 대기';self.last_error=None
  self.q.put_nowait(('info','프로그램 진단 수집 연결 완료'))
  return {'connected':True,'alias':data['alias']}
 def drain(self):
  device=self.device
  if not device:return
  for _ in range(100):
   try:kind,message=self.q.get_nowait()
   except queue.Empty:break
   now=time.monotonic();signature=(kind,message)
   if now-self.last.get(signature,-1e30)<60:continue
   self.last[signature]=now
   if len(self.last)>2048:self.last={k:v for k,v in self.last.items() if now-v<60}
   self.sequence+=1
   event=envelope(device['device'],device['alias'],self.version,self.sequence,kind,message)
   try:self.spool.append(event)
   except (OSError,ValueError):self.dropped+=1
 def flush(self):
  self.drain();device=self.device
  if not device:return False
  # An unavailable image store must not stop ordinary/error log uploads.
  try:self.flush_picture()
  except Exception:self.last_picture_error='문제 화면 전송 대기'
  batch=self.spool.batch(50)
  if not batch:return True
  if any(e['device']!=device['device'] for e in batch):raise ValueError('다른 PC의 대기 기록')
  result=self.sender('/v1/events',{'events':batch},device['token'])
  accepted=result.get('accepted') if isinstance(result,dict) else None
  sent={e['id'] for e in batch}
  if not isinstance(accepted,list) or not accepted or any(x not in sent for x in accepted):raise ValueError('서버 수신 확인 필요')
  self.spool.acknowledge(accepted);self.last_sent=time.time();self.state='연결됨';self.last_error=None
  return True
 def save_pictures(self):
  from owner_timetable import save
  save(self.picture_path,self.pending_pictures)
 def flush_picture(self):
  while len(self.pending_pictures)<100:
   try:entry=list(self.pictures.get_nowait())
   except queue.Empty:break
   if entry not in self.pending_pictures:self.pending_pictures.append(entry)
  self.save_pictures()
  if not self.pending_pictures:return
  category,identity=self.pending_pictures[0]
  if category not in ('incident','unknown') or not re.fullmatch(r'\d{8}T\d{6}Z?-[0-9a-f]{8}',identity):
   self.pending_pictures.pop(0);self.save_pictures();return
  folder=self.root/'logs'/('quest-incidents' if category=='incident' else 'scene-corpus')
  if category=='unknown':folder=folder/identity[:8]
  path=folder/identity/'screen.png'
  if not path.is_file():self.pending_pictures.pop(0);self.save_pictures();return
  from PIL import Image
  with Image.open(path) as image:
   # Only the existing canonical GAME frame. No new desktop/window capture.
   if image.size!=(897,479):self.pending_pictures.pop(0);self.save_pictures();return
   buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=78,optimize=False)
  raw=buffer.getvalue()
  if len(raw)>512*1024:raise ValueError('picture size')
  key=hashlib.sha256(raw).hexdigest()
  response=self.sender('/v1/attachment',{'sha256':key,'jpeg':base64.b64encode(raw).decode('ascii')},self.device['token'])
  if response.get('sha256')!=key or response.get('stored') is not True:raise ValueError('picture receipt')
  self.sequence+=1
  context={'incident_id':identity,'category':category,'screenshot_sha256':key,'game_frame_only':True}
  meta=path.with_name('incident.json')
  if category=='incident' and meta.exists():
   try:
    data=json.loads(meta.read_text(encoding='utf8'));context.update({k:str(data[k])[:300] for k in ('category','observed_reason','quest_title','mode') if data.get(k) is not None})
   except (OSError,ValueError):pass
  self.spool.append(envelope(self.device['device'],self.device['alias'],self.version,self.sequence,'warning','자동 진단 화면 첨부',context,event_id='img_'+key[:40]))
  self.pending_pictures.pop(0);self.save_pictures()
 def run(self):
  delay=1
  while not self.stop_event.wait(delay):
   try:self.flush();delay=15
   except Exception:
    self.state='재전송 대기';self.last_error='전송 지연 · PC에 보관 후 재시도';delay=60
 def close(self):self.stop_event.set()

def show(gui,*,parent=None,embedded=False):
 import tkinter as tk
 from tkinter import ttk
 service=gui._owner_telemetry
 w=ttk.Frame(parent) if embedded else tk.Toplevel(gui.root)
 if embedded:w.pack(fill='both',expand=True)
 else:w.title('진단 서버 연결');w.resizable(False,False)
 body=ttk.Frame(w,padding=16);body.pack(fill='both',expand=True)
 status=tk.StringVar(w,value=service.state);ttk.Label(body,textvariable=status).pack(anchor='w')
 ttk.Label(body,text='연결 코드').pack(anchor='w',pady=(12,3))
 code=ttk.Entry(body,width=36,show='•');code.pack(fill='x')
 ttk.Label(body,text='실행·오류 로그와 문제 게임 화면 자동 전송').pack(anchor='w',pady=8)
 def connect():
  value=code.get().strip();code.delete(0,'end');button.configure(state='disabled');status.set('연결 중')
  result=queue.Queue(1)
  def work():
   try:service.enroll(value);result.put('연결됨')
   except Exception:result.put('연결 실패 · 코드 또는 네트워크 확인')
  threading.Thread(target=work,daemon=True).start()
  def poll():
   if not w.winfo_exists():return
   try:text=result.get_nowait()
   except queue.Empty:w.after(100,poll);return
   status.set(text);button.configure(state='normal' if not service.device else 'disabled')
  w.after(100,poll)
 button=ttk.Button(body,text='연결',command=connect,state='disabled' if service.device else 'normal');button.pack(anchor='e')
 def update():
  if not w.winfo_exists():return
  if service.device:status.set(service.state+(' · '+time.strftime('%H:%M:%S',time.localtime(service.last_sent)) if service.last_sent else ''))
  w.after(2000,update)
 update()
 return w

def install(gui):
 if hasattr(gui,'_owner_telemetry'):return
 service=Transport(gui.project.root);gui._owner_telemetry=service;gui.logger.addHandler(service)
 def close(event):
  if event.widget is gui.root:gui.logger.removeHandler(service);service.close()
 gui.root.bind('<Destroy>',close,add='+')
