"""Durable per-character emote input rate; an attempt is not completion."""
from pathlib import Path
import hashlib,json,math,time
from owner_skill_goal import Pending

INTERVAL=61.0
class Rate:
 def __init__(self,root,scope,character,*,clock=time.time):
  if not all(isinstance(s,str) and s for s in (scope,character)):raise Pending('감정표현 캐릭터 확인 필요')
  self.path=Path(root)/'settings/owner-emote-rate.json';self.clock=clock
  self.key=hashlib.sha256((scope+'\0'+character).encode()).hexdigest()
 def read(self):
  try:d=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:d={'version':1,'characters':{}}
  except (ValueError,OSError) as e:raise Pending('감정표현 재전송 기록 확인 필요') from e
  if d.get('version')!=1 or not isinstance(d.get('characters'),dict):raise Pending('감정표현 재전송 기록 형식 확인 필요')
  row=d['characters'].setdefault(self.key,{'last_attempt':None,'requests':{}})
  if not isinstance(row,dict) or not isinstance(row.get('requests'),dict):raise Pending('감정표현 캐릭터 기록 확인 필요')
  return d,row
 def remaining(self):
  _,row=self.read();at=row.get('last_attempt')
  if at is None:return 0.
  if type(at) not in (int,float) or not math.isfinite(at):raise Pending('감정표현 입력 시각 확인 필요')
  age=self.clock()-at
  if age < -5:raise Pending('PC 시각이 바뀌어 감정표현 재전송 보류')
  return max(0.,INTERVAL-age)
 def attempts(self,request):
  value=self.read()[1]['requests'].get(request,{}).get('count',0)
  if type(value) is not int or value<0:raise Pending('감정표현 시도 횟수 기록 확인 필요')
  return value
 def reserve(self,request,target):
  if self.remaining()>0:raise Pending('감정표현 1분 재전송 제한 대기')
  d,row=self.read();old=row['requests'].get(request,{});count=old.get('count',0)
  if type(count) is not int or count<0 or count>=3:raise Pending('감정표현 3회 시도 후 미완료 · 진단 확인 필요')
  at=self.clock();row['last_attempt']=at;row['requests'][request]={'count':count+1,'target':target,'phase':'input_intent_unverified','at':at}
  from owner_timetable import save
  save(self.path,d)
  return at
