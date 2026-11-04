"""Per-character hunt rules storage; candidate until connected to settings UI."""
from pathlib import Path
import json,os,tempfile,hashlib
from owner_growth_policy_candidate import choose_hunt_rule

class HuntRules:
 def __init__(self,root,character):
  if not isinstance(character,str) or not character.strip():raise ValueError('캐릭터 확인 필요')
  self.path=Path(root)/'settings/owner-hunt-rules.json';self.character=character
  self.data=json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else {'version':1,'characters':{}}
  if not isinstance(self.data,dict) or self.data.get('version')!=1 or not isinstance(self.data.get('characters'),dict) or not isinstance(self.data.get('stationary',{}),dict):raise ValueError('사냥터 설정 형식 오류')
 def read(self):
  return self.stored() if self.enabled() else []
 def enabled(self):
  value=self.data.get('enabled',{}).get(self.character,True)
  if type(value) is not bool:raise ValueError('사냥터 사용 설정 확인 필요')
  return value
 def stored(self):
  values=self.data['characters'].get(self.character,[])
  if not isinstance(values,list) or len(values)>4 or any(not isinstance(v,dict) for v in values):raise ValueError('사냥터 목록 형식 오류')
  choose_hunt_rule(0,values);return values
 def stationary(self):
  value=self.data.get('stationary',{}).get(self.character)
  if value is not None and (type(value) is not int or not 1<=value<=4):raise ValueError('제자리 사냥 위치 형식 오류')
  return value
 def destinations(self):
  """The same in every game mode: only the one selected source decides."""
  if self.source()=='power':return [dict(rule) for rule in self.stored()]
  fixed=self.stationary()
  return [{'power':0,'slot':fixed}] if fixed is not None else []
 def source(self):
  """Exactly one of 'fixed' or 'power'. Files saved when both could be ticked: written rules win."""
  fixed=self.fixed_enabled();power=self.enabled()
  if power and fixed:return 'power' if self.stored() else 'fixed'
  return 'power' if power else 'fixed'
 def fixed_enabled(self):
  value=self.data.get('fixed_enabled',{}).get(self.character,True)
  if type(value) is not bool:raise ValueError('고정 사냥터 사용 설정 확인 필요')
  return value
 def store(self,rules,stationary_slot=None,*,enabled=None,fixed_enabled=None):
  if not isinstance(rules,list) or len(rules)>4:raise ValueError('사냥터는 최대 4개까지 설정할 수 있습니다')
  if fixed_enabled is not None:
   if type(fixed_enabled) is not bool:raise ValueError('고정 사냥터 사용 설정 확인 필요')
   self.data.setdefault('fixed_enabled',{})[self.character]=fixed_enabled
  choose_hunt_rule(0,rules)
  if stationary_slot is not None and (type(stationary_slot) is not int or not 1<=stationary_slot<=4):raise ValueError('제자리 사냥 저장 위치는 1~4번을 선택하세요')
  rows=[{'power':r['power'],'slot':r['slot']} for r in rules]
  self.data['characters'][self.character]=rows
  if enabled is not None:
   if type(enabled) is not bool:raise ValueError('사냥터 사용 설정 확인 필요')
   self.data.setdefault('enabled',{})[self.character]=enabled
  if stationary_slot is not None:self.data.setdefault('stationary',{})[self.character]=stationary_slot
  self.path.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(prefix='.hunt-',suffix='.tmp',dir=str(self.path.parent))
  try:
   with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(self.data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)

def configured_identity(root):
 """Resolve configured identity only; does NOT prove the live game character."""
 path=Path(root)/'settings/manager_identity.json'
 try:obj=json.loads(path.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError) as exc:raise ValueError('서버와 캐릭터 설정을 확인해 주세요') from exc
 if not isinstance(obj,dict):raise ValueError('서버와 캐릭터 설정 형식 오류')
 server=obj.get('server_name');name=obj.get('character_name')
 if not isinstance(server,str) or not isinstance(name,str):raise ValueError('서버와 캐릭터를 설정해 주세요')
 server=server.strip();name=name.strip()
 if not server or not name or server=='서버 미설정' or name=='캐릭터 미설정' or any(ord(c)<32 for c in server+name):raise ValueError('서버와 캐릭터를 설정해 주세요')
 # Unambiguous even if a value contains the human-readable separator.
 payload=json.dumps([server,name],ensure_ascii=False,separators=(',',':')).encode('utf-8')
 return 'configured-v1:'+hashlib.sha256(payload).hexdigest()

class ConfiguredHuntRules(HuntRules):
 """Detect identity changes during setup or any later return-to-hunt operation."""
 def __init__(self,root):
  self.root=Path(root);self.identity=configured_identity(root)
  super().__init__(root,self.identity)
 def assert_identity(self):
  if configured_identity(self.root)!=self.identity:raise ValueError('서버 또는 캐릭터 설정이 변경되어 사냥을 보류합니다')
 def read(self):self.assert_identity();return HuntRules(self.root,self.identity).read()
 def stored(self):self.assert_identity();return HuntRules(self.root,self.identity).stored()
 def enabled(self):self.assert_identity();return HuntRules(self.root,self.identity).enabled()
 def stationary(self):self.assert_identity();return HuntRules(self.root,self.identity).stationary()
 def destinations(self):self.assert_identity();return HuntRules(self.root,self.identity).destinations()
 def source(self):self.assert_identity();return HuntRules(self.root,self.identity).source()
 def fixed_enabled(self):self.assert_identity();return HuntRules(self.root,self.identity).fixed_enabled()
 def store(self,rules,stationary_slot=None,*,enabled=None,fixed_enabled=None):
  self.assert_identity()
  # Re-read the document so another character's settings saved since the
  # editor was opened are not lost on this commit.
  fresh=HuntRules(self.root,self.identity);fresh.store(rules,stationary_slot,enabled=enabled,fixed_enabled=fixed_enabled);self.data=fresh.data
