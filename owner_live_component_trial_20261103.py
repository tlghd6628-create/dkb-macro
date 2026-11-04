"""Temporary explicitly requested LIVE component trial on the normal worker.

Uses original input handlers/targets/IntentStore, not replay/fake input. This
is not the checker or evidence that the whole start pipeline is healthy.
No boxes, NPC purchases, boss entry or feature activation is performed here.
"""
import json,logging,time
from datetime import datetime
LOG=logging.getLogger('project_gui.DKB')
class Evidence(logging.Handler):
 def __init__(self):super().__init__();self.rows=[]
 def emit(self,record):
  message=record.getMessage()
  if any(k in message for k in ('성장 목표 검사','성장 결과 확인','이전 강화 결과','장비 조건','착용','입력','확인 필요')):
   self.rows.append({'at':datetime.now().astimezone().isoformat(),'message':message})

def run(adapter,context,inputs,kind):
 if kind not in ('gear','equipment'):raise RuntimeError('알 수 없는 단독 검증 요청')
 from owner_schedule_priority import hold_reason
 if hold_reason(adapter):raise RuntimeError('예약·특수 콘텐츠 보호 중 · 검증 입력 없음')
 if kind=='gear' and adapter.values.get('auto_growth.equipment.enabled') is not True:
  raise RuntimeError('장비 성장 사용 해제 · 실제 강화 검증 입력 없음')
 from owner_mission_controller import prepare
 from owner_mission_ui import MissionUI
 previous=(adapter.mode,getattr(adapter,'_owner_requested_quest_mode',None),getattr(adapter,'_owner_mission_ui',None))
 evidence=Evidence();LOG.addHandler(evidence);at=datetime.now().astimezone();result=None
 adapter.mode='sub_quest';adapter._owner_requested_quest_mode='sub_quest'
 try:
  context.checkpoint();progress=prepare(adapter,context,inputs)
  ui=MissionUI(adapter,context,inputs);adapter._owner_mission_ui=ui
  if not ui.normal():raise RuntimeError('단독 검증 전 일반 필드 두 화면 확인 필요')
  label='장비 강화' if kind=='gear' else '흰템→파템 교체'
  LOG.info('실제 기능 단독 검증 시작 · %s · 기존 입력 작업자·원본 경로·목표·결과 확인 유지',label)
  if kind=='gear':
   from owner_timetable import invoke,BY_KEY
   result=invoke(adapter,BY_KEY['gear'],context,inputs)
  else:
   # Equipment-only original component. Calling general inventory use here
   # would additionally open energy/coupon boxes, outside this trial scope.
   from owner_equip_runtime_install_candidate import _run
   result=_run(adapter,context,inputs)
  context.checkpoint()
  LOG.info('실제 기능 단독 검증 반환 · %s · 반환=%s · 성공 여부는 현재값·결과 로그로 별도 판정',label,result)
  return True
 finally:
  LOG.removeHandler(evidence)
  folder=adapter.project.root/'logs/component-trials';folder.mkdir(parents=True,exist_ok=True)
  payload={'started_at':at.isoformat(),'ended_at':datetime.now().astimezone().isoformat(),'kind':kind,
   'return':result,'whole_program_verified':False,'events':evidence.rows,'cancelled':context.stop.is_set()}
  (folder/(at.strftime('%Y%m%dT%H%M%S')+'-'+kind+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf8')
  adapter.mode,adapter._owner_requested_quest_mode,adapter._owner_mission_ui=previous
