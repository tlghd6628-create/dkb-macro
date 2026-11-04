"""Offline-only event protocol and bounded local spool; no network or secrets."""
import json,os,re,tempfile,threading,uuid
from pathlib import Path
from datetime import datetime,timezone

MAX_EVENT=16384
TOKEN=re.compile(r'''(?i)(bearer\s+|(?:token|password|passwd|authorization|api[_-]?key|비밀번호|인증번호)["']?\s*[=:]\s*)(["'][^"'\r\n]*["']|[^\s,;]+)''')
BOT_TOKEN=re.compile(r'\b[0-9]{6,14}:[A-Za-z0-9_-]{25,}\b')
PEM=re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',re.S)
SENSITIVE=re.compile(r'(?i)token|password|passwd|authorization|api.?key|secret|credential|비밀번호|인증번호')
SAFE_KEY=re.compile(r'^[a-zA-Z0-9_.-]{1,48}$')
ID=re.compile(r'^[a-zA-Z0-9_-]{1,80}$')
KINDS={'info','warning','error'}

def redact(value):
 text=str(value)
 text=PEM.sub('[REDACTED PRIVATE KEY]',text)
 text=BOT_TOKEN.sub('[REDACTED BOT TOKEN]',text)
 return TOKEN.sub(lambda m:m.group(1)+'[REDACTED]',text)[:2048]

def envelope(device,alias,version,sequence,kind,message,context=None,*,event_id=None,at=None):
 for name,value,limit in (('device',device,80),('alias',alias,80),('version',version,48)):
  if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError(name)
 if not ID.fullmatch(device) or type(sequence) is not int or sequence<1 or kind not in KINDS:raise ValueError('identity, sequence or kind')
 eid=event_id or uuid.uuid4().hex
 if not isinstance(eid,str) or not ID.fullmatch(eid):raise ValueError('event id')
 moment=at or datetime.now(timezone.utc)
 if not isinstance(moment,datetime) or moment.tzinfo is None:raise ValueError('UTC time')
 if context is None:context={}
 if not isinstance(context,dict) or len(context)>30:raise ValueError('context')
 clean={}
 if len(str(message))>2048:clean['message_truncated']=True
 for key,value in context.items():
  if not isinstance(key,str) or not SAFE_KEY.fullmatch(key):raise ValueError('context key')
  if SENSITIVE.search(key):continue
  if type(value) not in (str,int,float,bool) and value is not None:raise ValueError('context value')
  clean[key]=redact(value) if isinstance(value,str) else value
 event={'schema':1,'id':eid,'device':device,'alias':redact(alias),'version':version,
        'sequence':sequence,'at':moment.astimezone(timezone.utc).isoformat(),
        'kind':kind,'message':redact(message),'context':clean}
 raw=json.dumps(event,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
 if len(raw)>MAX_EVENT:raise ValueError('event too large')
 return event

class Spool:
 """Local bounded queue: old ordinary entries can be dropped, never secret fields."""
 def __init__(self,path,*,max_bytes=512000,max_items=500):
  self.path=Path(path);self.max_bytes=max_bytes;self.max_items=max_items;self.lock=threading.Lock()
  if max_bytes<MAX_EVENT or max_items<1:raise ValueError('spool limits')
 def _read(self):
  if not self.path.exists():return []
  if self.path.stat().st_size>self.max_bytes:raise ValueError('spool exceeds limit')
  data=json.loads(self.path.read_text(encoding='utf8'))
  if not isinstance(data,list) or len(data)>self.max_items:raise ValueError('invalid spool')
  return data
 def _write(self,events):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  data=json.dumps(events,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
  fd,name=tempfile.mkstemp(prefix='.diagnostic-spool-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   os.replace(name,self.path)
  finally:
   if os.path.exists(name):os.unlink(name)
 def append(self,event):
  # Reject raw caller objects: revalidation/redaction is mandatory even when
  # the caller constructed or changed a dictionary outside envelope().
  try:moment=datetime.fromisoformat(event['at'])
  except (KeyError,TypeError,ValueError) as exc:raise ValueError('event time') from exc
  safe=envelope(event['device'],event['alias'],event['version'],event['sequence'],event['kind'],event['message'],event['context'],event_id=event['id'],at=moment)
  with self.lock:
   entries=self._read()
   if any(x.get('id')==safe['id'] for x in entries):return False
   entries.append(safe)
   while len(entries)>self.max_items or len(json.dumps(entries,ensure_ascii=False,separators=(',',':')).encode('utf8'))>self.max_bytes:
    idx=next((i for i,row in enumerate(entries[:-1]) if row.get('kind')!='error'),None)
    if idx is None:raise ValueError('spool full; errors retained')
    entries.pop(idx)
   self._write(entries);return True
 def batch(self,limit=50):
  if type(limit) is not int or not 1<=limit<=100:raise ValueError('batch limit')
  with self.lock:return self._read()[:limit]
 def acknowledge(self,ids):
  if not isinstance(ids,(list,tuple,set)) or any(not isinstance(i,str) or not ID.fullmatch(i) for i in ids):raise ValueError('ids')
  with self.lock:
   entries=self._read();remaining=[row for row in entries if row['id'] not in ids]
   self._write(remaining);return len(entries)-len(remaining)
