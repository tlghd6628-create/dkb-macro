"""Connect owner settings to existing game operations on the original worker."""
from functools import partial
import sys,logging,time

LOG=logging.getLogger('project_gui.DKB')

def install_inventory_evidence(native,aliases):
 if getattr(native.open_inventory,'_owner_growth_evidence',False):return
 from functools import wraps
 import time
 original=native.open_inventory
 @wraps(original)
 def opened(service,*args,**kwargs):
  result=original(service,*args,**kwargs)
  if result is False:return result
  from owner_progression import inventory_parts
  from owner_equipment_boxes import agree
  identity=gear_identity(service)
  if identity:
   service.check();a=service.capture().copy();service.context.wait(.08);service.check();b=service.capture().copy()
   if inventory_parts(a)==(True,True) and inventory_parts(b)==(True,True):
    service.adapter._owner_gear_worn_frames={'identity':identity,'context':service.context,
     'captured_monotonic':time.monotonic(),'frames':(a,b),'verified_worn':agree(a,b)}
  return result
 opened._owner_growth_evidence=True;native.open_inventory=opened
 from owner_gear_native_install_candidate import _rebind_aliases
 _rebind_aliases(aliases,original,opened)

def gear_identity(service):
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 progress=state(service.adapter)
 if not progress.character or not 0<=time.monotonic()-progress.observed<=180:return None
 from owner_character_binding import mismatch
 if mismatch(service.adapter):return None
 profile=configured_identity(service.adapter.project.root)
 observed=(profile,progress.character)
 previous=getattr(service.adapter,'_owner_growth_profile',None)
 if previous is not None and previous!=observed:return None
 # Timetable execution temporarily masks adapter.values. Initialize from the
 # durable user's settings, so the first narrow job cannot disable other goals.
 from pathlib import Path
 import json
 from owner_gear_migration_candidate import initialize_missing
 try:
  saved=json.loads((Path(service.adapter.project.root)/'settings/auto-settings.json').read_text(encoding='utf-8-sig'))
  result=initialize_missing(service.adapter.project.root,profile,saved.get('values'))
 except (OSError,ValueError,TypeError,KeyError):return None
 if result.startswith('hold_'):return None
 if result=='initialized':LOG.info('성장 목표 초기 설정 · 기존 활성 상태와 확정 목표 유지')
 service.adapter._owner_growth_profile=observed
 return profile

REAL_FIELD_NAME=(0,745,150,23)  # the character's name at the field's lower left

def field_shows_name(adapter,context,inputs,character):
 """Sends nothing. False on anything unclear, and the info window then answers as it always has."""
 from project_adapter.town_services import TownServices
 from project_adapter import market_inventory
 from owner_text import clean,read
 try:
  frame=TownServices(adapter,context,inputs,market_inventory.INVENTORY_USE_NAMES).capture()
  if getattr(frame,'hi',None) is None:return False
  return any(clean(row['text'])==clean(character) for row in read(None,frame,REAL_FIELD_NAME,scale=2,minimum=.6))
 except (OSError,ValueError,TypeError,RuntimeError,AttributeError):return False

def fresh_growth_identity(adapter,context,inputs):
 from owner_progression import state
 progress=state(adapter)
 receipt=getattr(adapter,'_owner_progression_observation',None)
 if (isinstance(receipt,tuple) and len(receipt)==3 and receipt[0] is context
     and receipt[1]==progress.observed and receipt[2]==progress.character
     and progress.character and type(progress.level) is int and 0<=time.monotonic()-progress.observed<=180):
  adapter._owner_growth_identity_context=context
  return True
 if (getattr(adapter,'_owner_growth_identity_context',None) is context
     and progress.character and 0<=time.monotonic()-progress.observed<=180):return True
 # This run has read who is playing before, and the field still shows that name: no need to open the info window for it.
 if progress.character and type(progress.level) is int and field_shows_name(adapter,context,inputs,progress.character):
  adapter._owner_growth_identity_context=context
  return True
 from owner_quest_preflight import read_power
 previous_observed=progress.observed
 started=time.monotonic();context.checkpoint()
 read_power(adapter,context,inputs)
 context.checkpoint();progress=state(adapter)
 # Growth does not need a numeric combat-power threshold. It does require
 # this invocation's paired actual character/level receipt, even if power
 # OCR was ambiguous. Such a receipt never releases quest/death holds.
 if (not progress.character or progress.observed<started or progress.observed<=previous_observed
     or type(progress.level) is not int):return False
 adapter._owner_growth_identity_context=context
 return True

def install_identity_preflight(native,name,aliases):
 from functools import wraps
 original=getattr(native,name)
 if getattr(original,'_owner_growth_identity_preflight',False):return
 @wraps(original)
 def run(adapter,context,inputs,*args,**kwargs):
  keys=(('auto_growth.energy.enabled',) if name=='run_energy_entry' else
        ('auto_growth.equipment.enabled','auto_growth.blessing.enabled','auto_growth.taoist.enabled'))
  if not any(adapter.values.get(key) is True for key in keys):return True
  if not fresh_growth_identity(adapter,context,inputs):
   LOG.info('성장 작업 보류 · 이번 실행의 캐릭터·레벨 재확인 필요')
   adapter._owner_growth_preflight_hold=True
   if name=='run_energy_entry':
    # Native's energy caller treats False as a fatal program error. No
    # action was sent; preserve a separate hold outcome and continue the
    # original scene classifier, without claiming energy completion.
    adapter._owner_energy_outcome={'status':'held','reason':'캐릭터·레벨 재확인 필요'}
   else:
    adapter._owner_growth_pending_hold=True
   return True
  adapter._owner_growth_preflight_hold=False
  if name=='run_growth_entry':
   # At 1366x768 worn items grow by way of the bag and the blessing screen. The native entry would only open the growth
   # screen and close it again: energy and skills have their own entries.
   from owner_worn_growth import run as run_worn_growth
   if run_worn_growth(adapter,context,inputs) is True:return True
  # The actual growth observer proves this item's current values immediately
  # before input. Reading every worn tooltip is display-only and must not
  # starve that guarded action whenever a short quest changes the map.
  result=original(adapter,context,inputs,*args,**kwargs)
  if (name=='run_growth_entry' and adapter.values.get('auto_growth.equipment.enabled') is True
      and not getattr(adapter,'_owner_growth_pending_hold',False)):
   from owner_chore_transition import ancillary_field_ready,ChoreYield
   from owner_worn_stats import inspect_equipped
   if ancillary_field_ready(adapter,context,inputs):
    # A slot takes about six seconds to read, so four never got past the first one.
    try:inspect_equipped(adapter,context,inputs,max_seconds=20)
    except ChoreYield:
     LOG.info('장비 표시값 갱신 보류 · 실제 성장 결과와 분리 · 다음 기회에 이어서 확인')
  return result
 run._owner_growth_identity_preflight=True;setattr(native,name,run)
 from owner_gear_native_install_candidate import _rebind_aliases
 _rebind_aliases(aliases,original,run)

def install(gui):
 if getattr(gui,'_owner_program_runtime',False):return
 from owner_hunt_memory import install as install_hunt_memory
 install_hunt_memory(gui)
 from project_adapter import market_inventory,growth_equipment_extra
 from project_adapter import achievement_rewards
 from owner_gear_native_install_candidate import install as install_gear,native_readers_factory
 from owner_gear_extra_runtime_candidate import factory as native_extra_readers_factory
 from owner_blessing_native_candidate import run_blessing
 from owner_growth_current import observe
 aliases=tuple(m for n,m in sys.modules.items() if m is not None and n.startswith('project_adapter'))
 from owner_disassembly_settings import install as install_disassembly
 install_disassembly(market_inventory,aliases)
 install_inventory_evidence(market_inventory,aliases)
 def readers(service,context,identity,targets):
  return native_readers_factory(service,context,identity,targets,
   observation_sink=partial(observe,service.adapter.project.root))
 install_gear(market_inventory,gear_identity,readers,extra_module=growth_equipment_extra,
  # Each extra uses its own current/post stage reader and durable restart
  # recovery. Unknown numeric stages remain held before resource input.
  extra_readers_factory=native_extra_readers_factory,alias_modules=aliases,blessing_runner=run_blessing)
 from owner_energy_native_candidate import install as install_energy
 from types import SimpleNamespace
 install_energy(achievement_rewards,lambda adapter:gear_identity(SimpleNamespace(adapter=adapter)),alias_modules=aliases)
 from owner_blessing_original_fence_candidate import install_runtime as install_blessing_policy
 install_blessing_policy(achievement_rewards,market_inventory,
  lambda adapter:gear_identity(SimpleNamespace(adapter=adapter)),alias_modules=aliases)
 install_identity_preflight(achievement_rewards,'run_growth_entry',aliases)
 install_identity_preflight(achievement_rewards,'run_energy_entry',aliases)
 from owner_shop_runtime_candidate import install as install_shop
 install_shop()
 from owner_skill_growth_candidate import install as install_skill_growth
 install_skill_growth(gui)
 from owner_starter_choice_candidate import install as install_choices
 install_choices(gui)
 from owner_equip_runtime_install_candidate import install as install_guarded_equip
 install_guarded_equip(gui)
 from owner_equip_growth_due_candidate import install as install_equip_growth_due
 import owner_timetable
 install_equip_growth_due(owner_timetable)
 from owner_start_menu import install as install_start_menu
 install_start_menu()
 from owner_reward_cycle import install as install_reward_cycle
 install_reward_cycle(gui,aliases)
 gui._owner_program_runtime=True
 LOG.info('개인용 설정 실행 연결 · 사냥 복귀·성장 목표·상점 구매')
