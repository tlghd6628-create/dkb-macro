"""Install bounded guarded gear processing on the native inventory worker.

Unknown screen after input stops the job. This installation uses the native
equip gate, while a proved blank slot is handled by the separate tooltip port.
Positive gameplay and non-weapon layouts are not yet live verified.
"""
from functools import wraps
import logging,sys,threading,time
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local()

def scene_detector_names():
 from project_adapter import market_inventory as native
 from owner_special_contexts import NAMES as SCENE_NAMES
 from project_adapter.secret_exploration import AUTO_NAMES
 from owner_startup_stage import DUNGEON,EXIT,MENU
 return list(dict.fromkeys([*native.INVENTORY_USE_NAMES,*SCENE_NAMES,*AUTO_NAMES,DUNGEON,EXIT,MENU]))

def _run(adapter,context,inputs):
 from project_adapter import market_inventory as native
 from project_adapter.town_services import TownServices
 from owner_startup_stage import scene
 from owner_equipment_boxes import close_inventory
 from owner_equipment_tooltip_candidate import run_in_open_inventory,Hold
 from owner_progression import inventory_parts
 names=scene_detector_names()
 service=TownServices(adapter,context,inputs,names)
 def pair(check):
  context.checkpoint();service.check();a=service.capture()
  context.wait(.12);context.checkpoint();service.check();b=service.capture()
  return check(a) and check(b)
 def field(frame):return scene(service.detector,frame)=='field'
 def inventory(frame):return inventory_parts(frame)==(True,True)
 if not pair(field):return 'field_unverified_skip'
 try:
  if native.open_inventory(service) is False:raise Hold('장비 인벤토리 열기 미확인')
  if not pair(inventory):raise Hold('장비 인벤토리 화면 미확인')
  status=run_in_open_inventory(adapter,context,inputs)
 except Hold as exc:
  # The top-level inventory anchors also exist behind tooltips: never use
  # those anchors alone to dismiss an uncertain popup or resume automation.
  # Only a scan that sent no equip input and left no tooltip may skip this visit and let the quest go on.
  from owner_energy_box_detail_candidate import close_mark
  from owner_equipment_tooltip_candidate import comparison_shell
  def bare(frame):return inventory(frame) and not close_mark(frame) and not comparison_shell(frame)
  if '입력 결과' in str(exc):raise RuntimeError('장비 화면 확인 중단 · '+str(exc)) from exc
  # Auto-move can change zones during the visit, which closes the panel on its own.
  if pair(field):
   LOG.info('장비 확인 이번 방문 건너뜀 · %s · 창이 이미 닫힘 · 퀘스트 계속',exc)
   return 'scan_held_skip'
  if not pair(bare):raise RuntimeError('장비 화면 확인 중단 · '+str(exc)) from exc
  LOG.info('장비 확인 이번 방문 건너뜀 · %s · 입력 없음 · 퀘스트 계속',exc)
  close_inventory(service)
  if not pair(field):raise RuntimeError('장비 처리 뒤 원래 화면 복귀 미확인')
  return 'scan_held_skip'
 if status=='pending_confirmation':raise RuntimeError('장비 착용 결과 미확인 · 확인 후 재시도')
 if not pair(inventory):raise RuntimeError('장비 처리 뒤 인벤토리 확인 필요')
 close_inventory(service)
 if not pair(field):raise RuntimeError('장비 처리 뒤 원래 화면 복귀 미확인')
 return status

def install(gui):
 from project_adapter import market_inventory
 from project_adapter._entry import Adapter
 from owner_equip_native_gate_candidate import install as install_gate
 from owner_equipment_tooltip_candidate import Hold
 if getattr(gui,'_owner_guarded_equip_runtime',False):return
 install_gate()
 def wrap(original):
  if getattr(original,'_owner_guarded_equip_runtime',False):return original
  @wraps(original)
  def run(adapter,context,inputs,*args,**kwargs):
   if adapter.values.get('auto_rewards.inventory_use.enabled') is not True:return False
   if getattr(LOCAL,'active',False):return original(adapter,context,inputs,*args,**kwargs)
   LOCAL.active=True
   try:
    skip_generation=getattr(adapter,'_owner_inventory_skip_generation',0)
    result=original(adapter,context,inputs,*args,**kwargs)
    if result is False or getattr(adapter,'_owner_inventory_skip_generation',0)!=skip_generation:return result
    context.checkpoint()
    try:status=_run(adapter,context,inputs)
    except Hold as exc:LOG.info('장비 조건 확인 보류 · %s',str(exc));return result
    LOG.info('장비 조건 확인 · %s',status)
    return result
   finally:LOCAL.active=False
  run._owner_guarded_equip_runtime=True;return run
 current=market_inventory.run_inventory_use;wrapped=wrap(current);market_inventory.run_inventory_use=wrapped
 for name,module in tuple(sys.modules.items()):
  if not name.startswith('project_adapter') or module is None:continue
  for attr,value in tuple(vars(module).items()):
   if value is current:setattr(module,attr,wrapped)
 method=getattr(Adapter,'run_inventory_use',None)
 if callable(method):Adapter.run_inventory_use=wrap(method)
 gui._owner_guarded_equip_runtime=True
