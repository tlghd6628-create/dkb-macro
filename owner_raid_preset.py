"""Load the raid skill preset once inside the raid, with the native preset routine.

Default OFF: unless the user turns it on, every wrapped raid call passes straight through.
"""
import copy,logging
from functools import wraps
LOG=logging.getLogger('project_gui.DKB')
ENABLED='auto_schedule.boss_raid.skill_preset.enabled'
CHOICE='auto_schedule.boss_raid.skill_preset.choice'
BOSS_ENABLED='auto_schedule.field_boss.skill_preset.enabled'
BOSS_CHOICE='auto_schedule.field_boss.skill_preset.choice'
COMMON='common.skill_preset.enabled'

def add_fields(schema):
 """Same native field shape as the world boss preset, on the raid capability."""
 groups=[g for t in schema['tabs'] for g in t['groups']]
 if any(f['id']==ENABLED for g in groups for f in g['fields']):return schema
 by_id={f['id']:(g,f) for g in groups for f in g['fields']}
 if not all(key in by_id for key in (BOSS_ENABLED,BOSS_CHOICE,'auto_schedule.boss_raid.enabled')):return schema
 group,raid=by_id['auto_schedule.boss_raid.enabled']
 switch=copy.deepcopy(by_id[BOSS_ENABLED][1]);switch.update(id=ENABLED,capability=raid['capability'],default=False,label='레이드 스킬 프리셋')
 choice=copy.deepcopy(by_id[BOSS_CHOICE][1]);choice.update(id=CHOICE,capability=raid['capability'],default='A',label='레이드 스킬 프리셋 선택',enabled_if=ENABLED)
 at=group['fields'].index(raid)+1
 group['fields'][at:at]=[switch,choice]
 return schema

def guarded(change,*args,**kwargs):
 """A preset that could not be changed must not cost the raid itself."""
 from biol_base.session import Cancelled
 try:change(*args,**kwargs);return True
 except Cancelled:raise
 except Exception:
  LOG.exception('레이드 스킬 프리셋 변경 실패 · 레이드는 계속 진행');return False

def restore(adapter,context,inputs,change):
 """Back to the everyday preset. A stop or re-route never reaches a caller of this."""
 if not getattr(adapter,'_owner_raid_preset_applied',False):return
 adapter._owner_raid_preset_applied=False
 if adapter.values.get(COMMON) is True:guarded(change,adapter,context,inputs)

def install_on(flow_class,module,change):
 """Patch one flow class. Entry and matching are never touched: the preset can
 only load after the native flow has reached its combat step inside the raid."""
 if getattr(flow_class,'_owner_raid_preset',False):return
 ordinary_init=flow_class.__init__
 @wraps(ordinary_init)
 def init(flow,adapter,context,inputs,*args,**kwargs):
  ordinary_init(flow,adapter,context,inputs,*args,**kwargs)
  flow._owner_raid_args=(adapter,context,inputs);flow._owner_raid_pending=False
 flow_class.__init__=init
 ordinary_combat=flow_class.combat
 @wraps(ordinary_combat)
 def combat(flow,*args,**kwargs):
  adapter,context,inputs=flow._owner_raid_args
  flow._owner_raid_pending=getattr(adapter,'values',{}).get(ENABLED) is True
  result=ordinary_combat(flow,*args,**kwargs)
  flow._owner_raid_pending=False
  # Resuming an entered raid calls this directly, without the outer run.
  if kwargs.get('wait_for_exit'):restore(adapter,context,inputs,change)
  return result
 flow_class.combat=combat
 # The first AUTO check is the earliest step the flow reaches with raid controls.
 for name in ('auto_cycle','auto_state'):
  def checked(flow,*args,_ordinary=getattr(flow_class,name),**kwargs):
   if getattr(flow,'_owner_raid_pending',False):
    flow._owner_raid_pending=False
    adapter,context,inputs=flow._owner_raid_args
    LOG.info('레이드 입장 확인 · 레이드 스킬 프리셋 불러오기')
    if guarded(change,adapter,context,inputs,enabled_key=ENABLED,choice_key=CHOICE):adapter._owner_raid_preset_applied=True
   return _ordinary(flow,*args,**kwargs)
  setattr(flow_class,name,checked)
 ordinary_run=module._run
 @wraps(ordinary_run)
 def run(adapter,context,inputs,*args,**kwargs):
  result=ordinary_run(adapter,context,inputs,*args,**kwargs)
  restore(adapter,context,inputs,change)
  return result
 module._run=run
 flow_class._owner_raid_preset=True

def install():
 from project_adapter import boss_raid
 from project_adapter.skill_preset import run_skill_preset
 install_on(boss_raid.RaidFlow,boss_raid,run_skill_preset)
