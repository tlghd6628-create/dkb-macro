"""Hold native auto-equip until exact general-to-rare visual proof exists.

Existing inventory and box processing remains available. This is a safety
gate only; it does not implement the requested rare-equipment upgrade path.
"""
from functools import wraps
import logging,sys,threading

LOCAL=threading.local()
LOG=logging.getLogger('project_gui.DKB')

def wrap_inventory(original):
 if getattr(original,'_owner_auto_equip_gate',False):return original
 @wraps(original)
 def guarded(*args,**kwargs):
  previous=getattr(LOCAL,'inside_inventory',False)
  LOCAL.inside_inventory=True
  try:return original(*args,**kwargs)
  finally:LOCAL.inside_inventory=previous
 guarded._owner_auto_equip_gate=True
 return guarded

def wrap_init(original,ready_name):
 if getattr(original,'_owner_auto_equip_gate',False):return original
 @wraps(original)
 def init(service,*args,**kwargs):
  result=original(service,*args,**kwargs)
  if not getattr(LOCAL,'inside_inventory',False):return result
  detector=getattr(service,'detector',None);find=getattr(detector,'find',None)
  if not callable(find):raise RuntimeError('인벤토리 장비 판독 보호 설정 실패')
  if getattr(find,'_owner_auto_equip_gate',False):return result
  @wraps(find)
  def safe_find(name,*a,**kw):
   if name==ready_name:
    if not getattr(service,'_owner_equip_hold_logged',False):
     LOG.info('기존 자동 장착 보류 · 일반→희귀 비교 화면 확인 필요')
     service._owner_equip_hold_logged=True
    return None
   return find(name,*a,**kw)
  safe_find._owner_auto_equip_gate=True;detector.find=safe_find
  return result
 init._owner_auto_equip_gate=True
 return init

def install():
 """Install after existing wrappers; affects only this input worker's call."""
 from project_adapter import market_inventory,town_services
 from project_adapter._entry import Adapter
 cls=town_services.TownServices
 cls.__init__=wrap_init(cls.__init__,market_inventory.EQUIP_READY)
 current=market_inventory.run_inventory_use;wrapped=wrap_inventory(current)
 market_inventory.run_inventory_use=wrapped
 # Rebind native Python aliases that still point to this exact prior wrapper.
 for name,module in tuple(sys.modules.items()):
  if not name.startswith('project_adapter') or module is None:continue
  for attr,value in tuple(vars(module).items()):
   if value is current:setattr(module,attr,wrapped)
 method=getattr(Adapter,'run_inventory_use',None)
 if callable(method):Adapter.run_inventory_use=wrap_inventory(method)
