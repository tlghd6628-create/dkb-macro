"""Integer-only percentage allocation; no game/file/input operations."""
from decimal import Decimal,InvalidOperation
from functools import reduce
from math import gcd
import hashlib,json

NAMES=('생명','여명','몽환','홍염')

def percent_units(values,names=NAMES):
 if not isinstance(values,dict) or set(values)!=set(names):raise ValueError('종류별 비율을 입력해 주세요')
 result={}
 for name in names:
  value=values[name]
  if isinstance(value,bool):raise ValueError('비율은 숫자로 입력해 주세요')
  try:number=Decimal(str(value).strip())
  except InvalidOperation as exc:raise ValueError('비율은 숫자로 입력해 주세요') from exc
  if not number.is_finite() or not 0<=number<=100 or number*100!=(number*100).to_integral_value():
   raise ValueError('비율은 0~100%, 소수 둘째 자리까지 입력해 주세요')
  result[name]=int(number*100)
 total=sum(result.values())
 if total not in (0,10000):raise ValueError('비율 합계는 100%로 맞춰 주세요')
 return result

def equal_display(selected):
 if not isinstance(selected,list) or len(set(selected))!=len(selected) or any(n not in NAMES for n in selected):raise ValueError('기운 종류 확인 필요')
 values={n:0 for n in NAMES}
 if selected:
  base,remainder=divmod(10000,len(selected))
  for n in selected:values[n]=base
  # Display rounds to exactly 100%; balanced mode internally uses equal 1s.
  for n in selected[-remainder:] if remainder else []:values[n]+=1
 return {n:f'{values[n]//100}.{values[n]%100:02d}' for n in NAMES}

def weights(settings):
 if not isinstance(settings,dict):raise ValueError('기운 비율 설정 확인 필요')
 selected=settings.get('energies')
 if not isinstance(selected,list) or len(set(selected))!=len(selected) or any(n not in NAMES for n in selected):raise ValueError('기운 종류 확인 필요')
 if settings.get('energy_mode') in ('balanced','single'):
  return {n:1 if n in selected else 0 for n in NAMES}
 if settings.get('energy_mode')!='percent':raise ValueError('기운 비율 설정 확인 필요')
 result=percent_units(settings.get('energy_percentages'))
 if {n for n in NAMES if result[n]>0}!=set(selected):raise ValueError('기운 비율과 선택 종류가 다릅니다')
 return result

def fingerprint(setting):
 value=weights(setting);divisor=reduce(gcd,value.values()) or 1
 normalized={n:value[n]//divisor for n in NAMES}
 return hashlib.sha256(json.dumps(normalized,ensure_ascii=True,sort_keys=True).encode()).hexdigest()

def allocation(available,settings,journal):
 """Divide this stack only; carry rounding within the same ratio fingerprint.

 Historic receipts never impose debt on a newly requested percentage ratio.
 The caller commits rounding_after only once this whole durable plan completes.
 """
 if type(available) is not int or not 0<=available<=999999:raise ValueError('분배 수량 확인 필요')
 value=weights(settings);divisor=reduce(gcd,value.values()) or 1
 value={n:value[n]//divisor for n in NAMES};selected=[n for n in NAMES if value[n]>0]
 stamp=fingerprint(settings);total_weight=sum(value.values());cursor=0;debt=dict.fromkeys(NAMES,0)
 saved=journal.get('energy_ratio_rounding')
 if isinstance(saved,dict) and saved.get('fingerprint')==stamp:
  candidate=saved.get('debt');position=saved.get('cursor')
  if (not isinstance(candidate,dict) or set(candidate)!=set(NAMES)
      or any(type(candidate[n]) is not int or abs(candidate[n])>total_weight for n in NAMES)
      or sum(candidate.values())!=0 or any(candidate[n] for n in NAMES if not value[n])
      or type(position) is not int or not 0<=position<len(NAMES)):
   raise ValueError('저장된 분배 반올림 상태 확인 필요')
  debt=dict(candidate);cursor=position
 result=dict.fromkeys(NAMES,0)
 for _ in range(available if selected else 0):
  for name in selected:debt[name]+=value[name]
  name=max(selected,key=lambda n:(debt[n],-((NAMES.index(n)-cursor)%len(NAMES))))
  result[name]+=1;debt[name]-=total_weight;cursor=(NAMES.index(name)+1)%len(NAMES)
 return result,{'fingerprint':stamp,'debt':debt,'cursor':cursor}
