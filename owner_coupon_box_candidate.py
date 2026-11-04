"""Transactional coupon-fragment box coordinator; unknown evidence holds.

The actual inventory port is intentionally not registered until the box
identity, selection and reward screens are independently observed.
"""
from pathlib import Path
import hashlib,json,time
from owner_skill_goal import atomic,Pending
from owner_energy_box_runtime_candidate import proof
TARGETS={84:'생명의 흐름',68:'방패 밀기',89:'공간 결계'}
class CouponBoxJournal:
 def __init__(self,root,receipt_key):
  if not isinstance(receipt_key,str) or not receipt_key:raise Pending('캐릭터 확인 필요')
  self.identity=receipt_key;key=hashlib.sha256(receipt_key.encode('utf-8')).hexdigest()[:24]
  self.path=Path(root)/'settings'/('owner-coupon-skill-box-'+key+'.json')
 def read(self):
  try:value=json.loads(self.path.read_text(encoding='utf-8'))
  except FileNotFoundError:return {'version':1,'identity':self.identity,'pending':None,'receipts':[]}
  if not isinstance(value,dict) or value.get('version')!=1 or value.get('identity')!=self.identity or not isinstance(value.get('receipts'),list) or (value.get('pending') is not None and not isinstance(value['pending'],dict)):raise Pending('도술상자 기록 확인 필요')
  return value
 def save(self,value):atomic(self.path,value)

def claim_one(port,journal,sid,guard):
 if sid not in TARGETS:raise Pending('승인하지 않은 도술')
 state=journal.read()
 if state['pending'] is not None:raise Pending('이전 도술상자 수령 결과 확인 필요')
 if guard() is not True:raise Pending('캐릭터 또는 설정 확인 필요')
 # The port must positively identify the exact skill as unlearned; an absent
 # row or an incomplete scan is never sufficient evidence.
 skill=port.skill_state(sid,guard=guard)
 if not proof(skill) or skill.get('sid')!=sid:raise Pending('도술 보유 상태 확인 필요')
 if skill.get('owned') is True:return 'already_owned'
 if skill.get('owned') is not False or skill.get('unlearned_verified') is not True:raise Pending('미학습 증거 확인 필요')
 fragments=skill.get('fragments')
 if type(fragments) is not int or fragments<0:raise Pending('현재 도술 조각 수량 확인 필요')
 if fragments>=100:return 'ready_to_learn'
 if any(row.get('sid')==sid for row in state['receipts']):raise Pending('기존 수령 후 도술 상태 재확인 필요')
 prepared=port.prepare_box(sid,guard=guard)
 if (not proof(prepared) or prepared.get('sid')!=sid or prepared.get('name')!=TARGETS[sid] or prepared.get('quantity')!=1
     or type(prepared.get('boxes')) is not int or prepared['boxes']<1 or prepared.get('detail_boxes')!=prepared['boxes']
     or type(prepared.get('fragments_per_box')) is not int or prepared['fragments_per_box']<100-fragments):
  raise Pending('도술 조각 상자 품목·수량 확인 필요')
 if guard() is not True:raise Pending('캐릭터 또는 설정 변경')
 state['pending']={'phase':'prepared','sid':sid,'name':TARGETS[sid],'boxes_before':prepared['boxes'],
                   'fragments_before':fragments,'fragments_per_box':prepared['fragments_per_box'],
                   'before_frame_ids':list(prepared['frame_ids']),'at':time.time()}
 journal.save(state)
 def mark_sent():
  data=journal.read()
  if not data.get('pending') or data['pending'].get('phase')!='prepared' or guard() is not True:raise Pending('도술상자 입력 직전 재확인 필요')
  data['pending']['phase']='sent';journal.save(data)
 port.submit(prepared,mark_sent=mark_sent,guard=guard)
 state=journal.read()
 if state['pending'].get('phase')!='sent':raise Pending('상자 입력 여부 확인 필요')
 after=port.receipt(sid,guard=guard)
 if (guard() is not True or not proof(after) or set(after['frame_ids'])&set(prepared['frame_ids'])
     or after.get('sid')!=sid or after.get('name')!=TARGETS[sid] or after.get('boxes')!=prepared['boxes']-1
     or after.get('fragment_receipt') is not True or after.get('fragments_received')!=prepared['fragments_per_box']):
  raise Pending('동일 도술 조각 수령·상자 차감 확인 필요')
 state['receipts'].append({'sid':sid,'name':TARGETS[sid],'frame_ids':list(after['frame_ids']),'at':time.time()})
 state['pending']=None;journal.save(state)
 return 'claim_verified'
