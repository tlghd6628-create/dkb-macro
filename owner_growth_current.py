"""Last verified values for display; NEVER an execution authority.

The action-side observers retain their own strict frame lifetimes. A20minute
growth appointment must not make the settings table blank after120seconds.
"""
import threading,time,json,os,tempfile,logging,math,base64
from copy import deepcopy
from pathlib import Path

_LOCK=threading.RLock()
_READINGS={}
_VALUES={}
_LOADED=set()
_FIELDS={'enhancement':'enhance','opening':'opening','breakthrough':'breakthrough','awakening':'awaken'}
_SECTIONS=('skills','individual','blessings','energies')
_VALUE_FIELDS=('enhance','opening','breakthrough','awaken','stage')

def _path(root):return Path(root)/'settings/owner-growth-current.json'

def _valid_scope(value):return isinstance(value,str) and bool(value.strip()) and len(value)<=256

def _valid_icon(value):
 try:return isinstance(value,str) and len(base64.b64decode(value,validate=True))==18*18*3
 except (ValueError,TypeError):return False

def _load(root):
 key=str(Path(root).resolve())
 if key in _LOADED:return key
 _LOADED.add(key);path=_path(root)
 try:
  if path.stat().st_size>1024*1024:return key
  data=json.loads(path.read_text(encoding='utf8'))
 except (OSError,ValueError):return key
 if not isinstance(data,dict) or data.get('version')!=1:return key
 for section in ('equipment','values'):
  entries=data.get(section,[])
  if not isinstance(entries,list) or len(entries)>4096:continue
  for row in entries:
   if not isinstance(row,dict) or not _valid_scope(row.get('character')):continue
   values=row.get('values');at=row.get('at_epoch')
   if (not isinstance(values,dict) or not values or any(k not in _VALUE_FIELDS or type(v) is not int or not 0<=v<=9999 for k,v in values.items())
       or type(at) not in (int,float) or not math.isfinite(at) or not 0<at<10**12):continue
   saved_times=row.get('field_at',{})
   field_at={k:v for k,v in saved_times.items() if k in values and type(v) in (int,float) and math.isfinite(v) and 0<v<10**12} if isinstance(saved_times,dict) else {}
   if section=='equipment':
    if not _valid_scope(row.get('item')) or row.get('grade') not in ('일반','희귀','영웅'):continue
    _READINGS.setdefault((key,row['character']),{})[row['item']]={'grade':row['grade'],'slot':row.get('slot'),'values':dict(values),'at_epoch':at,'field_at':field_at,
        'item_icon':row.get('item_icon') if _valid_icon(row.get('item_icon')) else None}
   else:
    if row.get('section') not in _SECTIONS or not _valid_scope(row.get('key')):continue
    _VALUES[(key,row['character'],row['section'],row['key'])]={'values':dict(values),'at_epoch':at,'field_at':field_at,
        'item_identity':row.get('item_identity') if _valid_scope(row.get('item_identity')) else None}
 return key

def _persist(root):
 key=str(Path(root).resolve());document={'version':1,'purpose':'display_only_last_verified','equipment':[],'values':[]}
 for (r,character),items in _READINGS.items():
  if r!=key:continue
  for item,row in items.items():document['equipment'].append({'character':character,'item':item,'slot':row.get('slot'),'grade':row['grade'],'values':row['values'],'at_epoch':row['at_epoch'],'field_at':row.get('field_at',{}),'item_icon':row.get('item_icon')})
 for (r,character,section,k),row in _VALUES.items():
  if r==key:document['values'].append({'character':character,'section':section,'key':k,'values':row['values'],'at_epoch':row['at_epoch'],'field_at':row.get('field_at',{}),'item_identity':row.get('item_identity')})
 path=_path(root);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.growth-current-',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf8') as stream:json.dump(document,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def _save_display(root):
 try:_persist(root)
 except (OSError,ValueError,TypeError):logging.getLogger('project_gui.DKB').debug('성장 최근값 표시 저장 보류',exc_info=True)

def observe_value(root,character,section,key,values,*,verified=False,item_identity=None):
 if verified is not True or not _valid_scope(character) or section not in _SECTIONS:return False
 if not isinstance(key,str) or not key or not isinstance(values,dict):return False
 if item_identity is not None and not _valid_scope(item_identity):return False
 if not values or any(field not in ('enhance','breakthrough','awaken','stage') or type(value) is not int or value<0 for field,value in values.items()):return False
 with _LOCK:
  ident=(_load(root),character,section,key);prior=_VALUES.get(ident,{})
  # A new blessing in the same worn slot must not inherit the previous
  # item's unobserved breakthrough value. Skill/energy keys remain stable.
  keep=item_identity is None or prior.get('item_identity')==item_identity
  merged=dict(prior.get('values',{})) if keep else {};merged.update(values)
  at=time.time();field_at=dict(prior.get('field_at',{})) if keep else {};field_at.update({name:at for name in values})
  _VALUES[ident]={'values':merged,'at':time.monotonic(),'at_epoch':at,'field_at':field_at,
                 'item_identity':item_identity if item_identity is not None else prior.get('item_identity')};_save_display(root)
 return True

def current_value(root,character,section,key,field,*,now=None):
 now=time.monotonic() if now is None else now
 with _LOCK:row=_VALUES.get((_load(root),character,section,key))
 if not row or field not in row['values']:return '—'
 return str(row['values'][field])

def observe(root,row):
 if (not isinstance(row,dict) or not _valid_scope(row.get('character')) or not _valid_scope(row.get('item_identity'))
     or row.get('grade') not in ('일반','희귀','영웅')):return False
 proof=set(row.get('verified_fields',()))
 values={dst:row[src] for src,dst in _FIELDS.items() if src in proof and type(row.get(src)) is int and row[src]>=0}
 if not values:return False
 with _LOCK:
  key=(_load(root),row['character']);items=_READINGS.setdefault(key,{})
  prior=items.get(row['item_identity'],{});keep=prior.get('grade')==row['grade'] and row.get('replace_values') is not True
  merged=dict(prior.get('values',{})) if keep else {};merged.update(values)
  at=time.time();field_at=dict(prior.get('field_at',{})) if keep else {};field_at.update({name:at for name in values})
  icon=row.get('item_icon') if _valid_icon(row.get('item_icon')) else prior.get('item_icon')
  items[row['item_identity']]={'grade':row.get('grade'),'slot':row.get('slot',prior.get('slot')),'values':merged,'at':time.monotonic(),'at_epoch':at,'field_at':field_at,'item_icon':icon};_save_display(root)
 return True

def current(root,character,grade,field,*,now=None):
 now=time.monotonic() if now is None else now
 with _LOCK:rows=list(_READINGS.get((_load(root),character),{}).values())
 values=sorted({r['values'][field] for r in rows if r['grade']==grade and field in r['values']})
 if not values:return '—'
 return str(values[0]) if len(values)==1 else str(values[0])+'~'+str(values[-1])

def last_observed_at(root,character):
 """Wall time for a UI hint; this value NEVER authorizes game input."""
 with _LOCK:
  scope=_load(root);times=[row['at_epoch'] for (r,c),items in _READINGS.items() if r==scope and c==character for row in items.values()]
  times.extend(row['at_epoch'] for (r,c,_,_),row in _VALUES.items() if r==scope and c==character)
 return max(times) if times else None

def display_snapshot(root,character):
 """Atomic detached copy for PC/Telegram. No capture, OCR or game input."""
 if not _valid_scope(character):raise ValueError('캐릭터 확인 필요')
 with _LOCK:
  scope=_load(root)
  values={section:{} for section in _SECTIONS}
  for (r,c,section,key),row in _VALUES.items():
   if r==scope and c==character:values[section][key]=deepcopy(row)
  equipment=deepcopy(_READINGS.get((scope,character),{}))
 return {'character':character,'values':values,'equipment':equipment,'display_only':True}

def equipped_rows(root,character):
 """Per-slot last verified display values, never enhancement permissions."""
 from owner_equipment_boxes import SLOTS
 with _LOCK:items=list(_READINGS.get((_load(root),character),{}).values())
 result=[]
 for slot in SLOTS:
  rows=[r for r in items if r.get('slot')==slot]
  row=max(rows,key=lambda r:r['at_epoch']) if rows else {}
  values=row.get('values',{})
  result.append((slot,row.get('grade','미확인'),*(str(values[k]) if k in values else '미확인' for k in ('enhance','opening','breakthrough','awaken'))))
 return result

def invalidate_item(root,character,item_identity,*,grade=None):
 """After a separately VERIFIED replacement, remove only old display data.

 This deliberately never edits any resource/quest/gear intent or receipt. It
 cannot make a pending action eligible for replay on a replacement item.
 """
 if not _valid_scope(character) or not isinstance(item_identity,str) or not item_identity or len(item_identity)>8192:return False
 with _LOCK:
  items=_READINGS.get((_load(root),character),{})
  chosen=item_identity if item_identity in items and (grade is None or items[item_identity].get('grade')==grade) else None
  if chosen is None:
   # Tooltip and inventory render the same icon at20 and18px respectively.
   # Only one extremely close cache match may be invalidated. No match or a
   # tie keeps the old diagnostic value; neither case affects game authority.
   try:
    import cv2,numpy as np
    token=json.loads(item_identity);raw=base64.b64decode(token['icon_rgb'],validate=True)
    icon=np.frombuffer(raw,np.uint8).reshape((20,20,3));ref=cv2.resize(icon,(18,18),interpolation=cv2.INTER_AREA)
   except (ValueError,TypeError,KeyError):return False
   matches=[]
   for key,row in items.items():
    if grade is not None and row.get('grade')!=grade:continue
    if not _valid_icon(row.get('item_icon')):continue
    other=np.frombuffer(base64.b64decode(row['item_icon']),np.uint8).reshape((18,18,3))
    score=float(cv2.matchTemplate(ref,other,cv2.TM_CCOEFF_NORMED)[0,0])
    if math.isfinite(score) and score>=.97:matches.append(key)
   if len(matches)!=1:return False
   chosen=matches[0]
  del items[chosen];_save_display(root)
 return True
