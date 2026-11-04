"""Explicit diagnostic snapshot/upload. No game input, captures, or Tk in worker."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import base64,hashlib,io,json,os,queue,re,threading,time,uuid,zipfile
from owner_telemetry_protocol import envelope,PEM,BOT_TOKEN,TOKEN,SENSITIVE

MAX_LOG=32*1024*1024
STAMP=re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (DEBUG|INFO|WARNING|ERROR|CRITICAL) (.*)$')
KST=timezone(timedelta(hours=9))

def clean(text):
 text=PEM.sub('[REDACTED PRIVATE KEY]',str(text));text=BOT_TOKEN.sub('[REDACTED BOT TOKEN]',text)
 return TOKEN.sub(lambda m:m.group(1)+'[REDACTED]',text)

def safe_metadata(value):
 if isinstance(value,dict):return {k:('[REDACTED]' if SENSITIVE.search(str(k)) else safe_metadata(v)) for k,v in value.items()}
 if isinstance(value,list):return [safe_metadata(v) for v in value]
 if isinstance(value,str):return clean(value)
 return value

def save(path,value):
 from owner_timetable import save as atomic
 atomic(path,value)

def create_snapshot(root,summary,device,*,moment=None):
 root=Path(root);moment=moment or datetime.now(timezone.utc)
 identity=moment.strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8]
 directory=root.parent.parent/'진단자료';directory.mkdir(parents=True,exist_ok=True)
 target=directory/('diagnostic-send-'+identity+'.zip');temp=target.with_suffix('.preparing')
 paths=sorted((root/'logs').glob('????-??-??.log'))
 today=root/'logs'/(moment.astimezone(KST).strftime('%Y-%m-%d')+'.log')
 source=today if today.is_file() else paths[-1] if paths else root/'logs/gui.log'
 raw=b'';truncated=False
 if source.is_file():
  if source.is_symlink() or source.resolve().parent!=(root/'logs').resolve():raise ValueError('진단 로그 경로')
  with source.open('rb') as stream:
   size=stream.seek(0,2);start=max(0,size-MAX_LOG);stream.seek(start);raw=stream.read(MAX_LOG)
  truncated=start>0
  if truncated:raw=raw.partition(b'\n')[2]
 text=clean(raw.decode('utf8',errors='replace'))
 # Ignore the final unfinished log line while the program is writing it.
 text=text[:text.rfind('\n')+1] if '\n' in text else text
 logs=[];level='info';at=moment
 for index,line in enumerate(text.splitlines(),1):
  match=STAMP.match(line)
  if match:
   when,severity,message=match.groups();at=datetime.strptime(when,'%Y-%m-%d %H:%M:%S,%f').replace(tzinfo=KST)
   level='error' if severity in ('ERROR','CRITICAL') else 'warning' if severity=='WARNING' else 'info'
  else:message=line
  stable=source.name+'|'+str(index)+'|'+at.isoformat()+'|'+line
  logs.append(envelope(device['device'],device['alias'],'diagnostic-log-v1',index,level,message,
   {'source':source.name,'source_line':index,'manual_history':True},event_id='log_'+hashlib.sha256(stable.encode()).hexdigest()[:40],at=at))
 pictures=[];incidents=[];details=[];reviewed=0;folder=root/'logs/quest-incidents'
 candidates=sorted(folder.iterdir(),reverse=True) if folder.is_dir() else []
 try:
  with zipfile.ZipFile(temp,'x',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
   for path in candidates:
    if reviewed>=20:break
    if path.is_symlink() or not path.is_dir() or not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}',path.name):continue
    reviewed+=1
    photo=path/'screen.png';meta=path/'incident.json'
    if photo.is_file() and not photo.is_symlink() and photo.stat().st_size<=4*1024*1024:
     from PIL import Image
     with Image.open(photo) as image:
      if image.size!=(897,479):continue
      buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=78)
     jpeg=buffer.getvalue()
     if len(jpeg)>512*1024:continue
     entry='images/'+path.name+'.jpg';digest=hashlib.sha256(jpeg).hexdigest()
     archive.writestr(entry,jpeg);pictures.append({'entry':entry,'sha256':digest,'incident_id':path.name})
    if meta.is_file() and not meta.is_symlink() and meta.stat().st_size<=1024*1024:
     try:value=json.dumps(safe_metadata(json.loads(meta.read_text(encoding='utf8'))),ensure_ascii=False,indent=2)
     except (ValueError,OSError):continue
     entry='incidents/'+path.name+'.json'
     archive.writestr(entry,value);incidents.append(path.name)
     details.append({'entry':entry,'incident_id':path.name,'parts':max(1,(len(value.encode('utf8'))+1199)//1200)})
   from owner_scene_diagnostics import append_scenes
   scene_evidence=append_scenes(root,archive,pictures,details,safe_metadata)
   receipt={'contract':'dkb-manual-diagnostic-v1','id':identity,'created_at':moment.isoformat(),
    'device':device['device'],'alias':device['alias'],'summary':summary,'log_source':source.name,
    'log_lines':len(logs),'log_truncated_32mb':truncated,'pictures':pictures,'incidents':incidents,'details':details,
    'scene_evidence':scene_evidence}
   archive.writestr('summary.json',json.dumps(receipt,ensure_ascii=False))
   archive.writestr('recent-log.txt',text)
   archive.writestr('events.jsonl','\n'.join(json.dumps(e,ensure_ascii=False,separators=(',',':')) for e in logs))
  os.replace(temp,target)
 finally:
  if temp.exists():temp.unlink()
 state={'id':identity,'device':device['device'],'phase':'pending','log_cursor':0,'picture_cursor':0,'detail_cursor':0,'detail_part':0,
  'created_at':receipt['created_at'],'logs':len(logs),'pictures':len(pictures),'retry_at':0,'summary':summary}
 job=root/'settings/manual-diagnostics'/(identity+'.json');save(job,state)
 return job,target

def send_step(root,job,device,sender):
 root=Path(root);job=Path(job)
 if job.parent.resolve()!=(root/'settings/manual-diagnostics').resolve() or job.is_symlink():raise ValueError('진단 작업 경로')
 state=json.loads(job.read_text(encoding='utf8'));identity=state['id']
 if job.name!=identity+'.json' or not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}',identity) or state['device']!=device['device']:raise ValueError('진단 PC 정보')
 target=root.parent.parent/'진단자료'/('diagnostic-send-'+identity+'.zip')
 if target.is_symlink() or not target.is_file():raise ValueError('로컬 진단 자료 확인 필요')
 with zipfile.ZipFile(target) as archive:
  if sum(i.file_size for i in archive.infolist())>128*1024*1024:raise ValueError('진단 자료 크기')
  receipt=json.loads(archive.read('summary.json'))
  if receipt['id']!=identity or receipt['device']!=device['device']:raise ValueError('진단 자료 정보')
  cursor=state['log_cursor'];rows=[]
  with archive.open('events.jsonl') as stream:
   for index,line in enumerate(stream):
    if index<cursor:continue
    rows.append(json.loads(line))
    if len(rows)==100:break
  if rows:
   result=sender('/v1/events',{'events':rows},device['token'])
   if not isinstance(result,dict) or set(result.get('accepted',[]))!={e['id'] for e in rows}:raise ValueError('서버 로그 수신 확인 필요')
   state['log_cursor']+=len(rows)
  elif state.get('detail_cursor',0)<len(receipt.get('details',[])):
   number=state.get('detail_cursor',0);part=state.get('detail_part',0);detail=receipt['details'][number]
   if not re.fullmatch(r'incidents/\d{8}T\d{6}Z-[a-f0-9]{8}\.json',detail['entry']):raise ValueError('진단 정보 경로')
   # JSON has already been recursively redacted in the local snapshot.
   # Encode its chunks so the text-log sanitizer cannot damage JSON quotes.
   value=archive.read(detail['entry']);chunk=base64.b64encode(value[part*1200:(part+1)*1200]).decode('ascii')
   e=envelope(device['device'],device['alias'],'diagnostic-manual-v1',part+1,'info',chunk,
    {'diagnostic_id':identity,'incident_id':detail['incident_id'],'part':part,'parts':detail['parts'],'diagnostic_metadata':True,'encoding':'base64_utf8_json'},
    event_id='manualmeta_'+identity+'_'+str(number)+'_'+str(part),at=datetime.fromisoformat(state['created_at']))
   ack=sender('/v1/events',{'events':[e]},device['token'])
   if set(ack.get('accepted',[]))!={e['id']}:raise ValueError('진단 정보 수신 확인 필요')
   if part+1>=detail['parts']:state['detail_cursor']=number+1;state['detail_part']=0
   else:state['detail_part']=part+1
  elif state['picture_cursor']<len(receipt['pictures']):
   photo=receipt['pictures'][state['picture_cursor']];entry=photo['entry']
   if not re.fullmatch(r'images/\d{8}T\d{6}Z-[a-f0-9]{8}\.jpg',entry):raise ValueError('진단 화면 경로')
   raw=archive.read(entry)
   if len(raw)>512*1024 or hashlib.sha256(raw).hexdigest()!=photo['sha256']:raise ValueError('진단 화면 무결성')
   result=sender('/v1/attachment',{'sha256':photo['sha256'],'jpeg':base64.b64encode(raw).decode('ascii')},device['token'])
   if not isinstance(result,dict) or result.get('sha256')!=photo['sha256'] or result.get('stored') is not True:raise ValueError('서버 화면 수신 확인 필요')
   # A stable link event is acknowledged before the picture cursor advances.
   e=envelope(device['device'],device['alias'],'diagnostic-manual-v1',state['picture_cursor']+1,'info','수동 진단 화면 첨부',
    {'diagnostic_id':identity,'incident_id':photo['incident_id'],'screenshot_sha256':photo['sha256']},
    event_id='manualimg_'+identity+'_'+str(state['picture_cursor']),at=datetime.fromisoformat(state['created_at']))
   ack=sender('/v1/events',{'events':[e]},device['token'])
   if set(ack.get('accepted',[]))!={e['id']}:raise ValueError('화면 연결 기록 수신 확인 필요')
   state['picture_cursor']+=1
  else:
   e=envelope(device['device'],device['alias'],'diagnostic-manual-v1',1,'info','수동 진단 전송 완료',
    {'diagnostic_id':identity,'log_source':receipt['log_source'],'log_lines':state['logs'],'pictures':state['pictures'],
     'incidents':len(receipt['incidents']),'log_truncated_32mb':receipt['log_truncated_32mb'],'session_status':str(state['summary'].get('status',''))},
    event_id='manualdone_'+identity,at=datetime.fromisoformat(state['created_at']))
   ack=sender('/v1/events',{'events':[e]},device['token'])
   if set(ack.get('accepted',[]))!={e['id']}:raise ValueError('최종 수신 확인 필요')
   state.update(phase='sent',sent_at=datetime.now(timezone.utc).isoformat())
 state.update(retry_at=0,error=None);save(job,state)
 return state

class ManualUpload:
 def __init__(self,root,transport):
  self.root=Path(root);self.transport=transport;self.stop=threading.Event();self.wake=threading.Event()
  self.commands=queue.Queue(1);self.status={'phase':'idle'}
  self.worker=threading.Thread(target=self.run,name='DKB-manual-diagnostics',daemon=True);self.worker.start()
 def request(self,summary):
  if not self.transport.device:raise ValueError('세부설정 > 진단 서버에서 먼저 연결해 주세요.')
  if self.status['phase'] in ('preparing','sending'):return False
  self.status={'phase':'preparing'};self.commands.put_nowait(dict(summary));self.wake.set();return True
 def run(self):
  while not self.stop.is_set():
   self.wake.wait(.1 if self.status.get('phase')=='sending' else 15);self.wake.clear()
   if self.stop.is_set():break
   device=self.transport.device
   if not device:continue
   try:
    try:summary=self.commands.get_nowait()
    except queue.Empty:summary=None
    if summary is not None:
     job,target=create_snapshot(self.root,summary,device)
     self.status={'phase':'sending','id':job.stem,'local_zip':str(target)}
    jobs=sorted((self.root/'settings/manual-diagnostics').glob('*.json'))
    for job in jobs:
     state=json.loads(job.read_text(encoding='utf8'))
     if state.get('phase')=='sent' or state.get('retry_at',0)>time.time() or state.get('device')!=device['device']:continue
     try:
      state=send_step(self.root,job,device,self.transport.sender)
      self.status={'phase':'sent' if state['phase']=='sent' else 'sending','id':state['id'],
       'logs_sent':state['log_cursor'],'logs':state['logs'],'pictures_sent':state['picture_cursor'],'pictures':state['pictures']}
     except Exception:
      state.update(phase='pending',retry_at=time.time()+60,error='네트워크 또는 서버 수신 확인 실패');save(job,state)
      self.status={'phase':'waiting','id':state['id'],'local_saved':True}
     break
   except Exception:
    self.status={'phase':'failed','local_saved':False}
 def close(self):self.stop.set();self.wake.set()

def log_transfer(logger,state):
 import logging
 phase=state['phase']
 if phase=='sent':notice='진단 전송 완료 · 서버 수신 확인 · 로그 %d줄 · 화면 %d장 · %s'%(state['logs'],state['pictures'],state['id'])
 elif phase=='waiting':notice='진단 전송 대기 · 로컬 자료 보존 · 60초 후 재시도 · '+str(state['id'])
 elif phase=='failed':notice='진단 전송 실패 · 자료 준비 오류 · 기존 로그와 진단자료는 보존됩니다.'
 else:return
 logger.log(logging.INFO if phase=='sent' else logging.WARNING,notice,extra={'gui_message':notice,'state_transition':True})

def transfer_caption(state):
 phase=state['phase']
 if phase=='sent':return '진단 전송 완료'
 if phase=='preparing':return '진단 수집 중'
 if phase=='sending':return '전송 중 · 로그 %s/%s · 화면 %s/%s'%(state.get('logs_sent',0),state.get('logs',0),state.get('pictures_sent',0),state.get('pictures',0))
 if phase=='waiting':return '전송 대기 · 재시도 예정'
 if phase=='failed':return '진단 준비 실패'
 return '진단 전송'

def install_button(gui):
 if hasattr(gui,'_owner_manual_diagnostics'):return
 from tkinter import messagebox
 from owner_telemetry import install as install_transport
 install_transport(gui)
 upload=ManualUpload(gui.project.root,gui._owner_telemetry);gui._owner_manual_diagnostics=upload
 def send():
  try:
   state=gui.session.snapshot()
   if upload.request({'project':'DKB','version':str(gui.project.version),'status':state['status'],
                      'worker_alive':bool(state['worker_alive']),'session_error_present':bool(state.get('error'))}):
    notice='진단 전송 시작 · 오늘 로그와 최근 진단 화면 수집 중'
    gui.logger.info(notice,extra={'gui_message':notice,'state_transition':True})
  except (ValueError,OSError,queue.Full) as exc:messagebox.showinfo('진단 전송',str(exc),parent=gui.root)
 gui.export_diagnostics=send
 def bind():
  view=getattr(gui,'visual_view',None);buttons=[getattr(gui,'log_send_button',None)]
  for mapping in (getattr(view,'widgets',{}),getattr(view,'originals',{})):
   buttons.append(mapping.get('log_send'))
  for b in buttons:
   if b is not None and b.winfo_exists():b.configure(text=transfer_caption(upload.status),command=send,state='disabled' if upload.status['phase'] in ('preparing','sending') else 'normal')
  status=upload.status;phase=status['phase']
  label='' if phase=='idle' else transfer_caption(status)
  notes=[getattr(gui,'log_note',None),getattr(view,'widgets',{}).get('log_note')]
  for note in notes:
   if note is not None and note.winfo_exists():note.configure(text=label)
 from owner_main import MainPanel
 from functools import wraps
 old=MainPanel.layout
 @wraps(old)
 def layout(panel):
  result=old(panel)
  if panel.gui is gui:bind()
  return result
 MainPanel.layout=layout
 last=[None]
 def poll():
  if gui.closed.is_set():return
  bind();state=dict(upload.status)
  if state!=last[0]:
   last[0]=state
   log_transfer(gui.logger,state)
   if state['phase'] in ('sent','waiting','failed'):
    def reveal_result():
     if not gui.closed.is_set() and getattr(gui,'log',None) is not None:gui.log.see('end')
    gui.root.after(400,reveal_result)
  gui.root.after(300,poll)
 gui.root.bind('<Destroy>',lambda e:upload.close() if e.widget is gui.root else None,add='+');bind();poll()
