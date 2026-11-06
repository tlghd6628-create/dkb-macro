"""Presentation-only consolidation; keep schema IDs and saved values intact."""
import copy

GROWTH_SWITCHES={
 'equipment':'auto_growth.equipment.enabled',
 'skills':'auto_growth.taoist.enabled',
 'blessings':'auto_growth.blessing.enabled',
 'energies':'auto_growth.energy.enabled',
 'album':'auto_rewards.album.enabled',
}
INTERNAL={
 'auto_schedule.quest_defaults_initialized','auto_register.market.initialized',
 'auto_register.market.sales_defaults_initialized','auto_register.market.unchecked_defaults_initialized',
 'auto_register.equipment_disassembly.initialized','auto_challenge.secret_type_initialized',
 'auto_challenge.initial_defaults_initialized','custom.start_selected',
}

def consolidated(schema):
 result=copy.deepcopy(schema)
 def field_ids(node):
  if isinstance(node,dict):
   if node.get('type') and isinstance(node.get('id'),str):yield node['id']
   for value in node.values():yield from field_ids(value)
  elif isinstance(node,list):
   for value in node:yield from field_ids(value)
 for tab in result.get('tabs',[]):
  for group in tab.get('groups',[]):
   ids=list(field_ids(group))
   if ids and all(key.startswith('custom.') for key in ids):group['visible']=False
 def visit(node):
  if isinstance(node,dict):
   key=node.get('id')
   if key in INTERNAL or key in GROWTH_SWITCHES.values():node['visible']=False
   if key=='auto_rewards.blessing.enabled':node['label']='가호 일괄 획득'
   if key=='auto_register.market.bag.enabled':node['default']=False  # the market is closed for now
   for value in node.values():visit(value)
  elif isinstance(node,list):
   for value in node:visit(value)
 visit(result)
 return result

def install(gui):
 schema=getattr(gui,'_live_schema',None)
 if not isinstance(schema,dict):raise ValueError('설정 화면을 준비하지 못했습니다.')
 updated=consolidated(schema)
 if updated!=schema:
  gui._live_schema=updated
  gui._settings_schema_revision=getattr(gui,'_settings_schema_revision',0)+1

class GrowthSwitches:
 """Use native SettingsModel save; never create a parallel enable store."""
 def __init__(self,gui,character):
  self.gui,self.character=gui,character
  model=gui.load_settings_model()
  if model.load_error:raise ValueError('기본 동작 설정을 읽을 수 없습니다.')
  self.initial=self._read(model)
  self.editable={s:model.editable(model.items[key]) for s,key in GROWTH_SWITCHES.items()}
 def _read(self,model):
  result={section:model.values.get(key) for section,key in GROWTH_SWITCHES.items()}
  if any(type(value) is not bool for value in result.values()):raise ValueError('성장 기능 사용 설정 확인 필요')
  return result
 def _model(self):
  from owner_hunt_rules_candidate import configured_identity
  state=self.gui.session.snapshot()
  # The user's rule: settings may change while paused (F2), as the other pages already allow (pc2 11-06 was refused).
  self.paused=state.get('status')=='paused'
  if state.get('status')=='running' or (state.get('worker_alive') and not self.paused):
   raise ValueError('일시정지(F2)나 중지 후 성장 설정을 저장해 주세요.')
  if configured_identity(self.gui.project.root)!=self.character:raise ValueError('캐릭터가 바뀌었습니다. 설정창을 다시 열어 주세요.')
  model=self.gui.load_settings_model()
  if model.load_error or self._read(model)!=self.initial:raise ValueError('다른 창에서 성장 사용 설정이 변경되었습니다. 다시 열어 주세요.')
  return model
 def validate(self,wanted):
  model=self._model()
  if set(wanted)!=set(GROWTH_SWITCHES) or any(type(v) is not bool for v in wanted.values()):raise ValueError('성장 기능 사용 설정 확인 필요')
  for section,key in GROWTH_SWITCHES.items():
   if wanted[section]!=self.initial[section] and not model.editable(model.items[key]):
    raise ValueError('현재 사용할 수 없는 성장 기능입니다.')
  return model
 def _save(self,model,wanted):
  values=dict(model.values)
  for section,key in GROWTH_SWITCHES.items():values[key]=wanted[section]
  model.save(model.mode,values)
  if self._read(model)!=wanted:raise ValueError('성장 기능 사용 설정 저장 결과를 확인해 주세요.')
  if getattr(self,'paused',False):
   # A paused run picks the switches up when it resumes, like the native settings saved in a pause.
   from owner_timetable import live_settings
   live_settings({key:wanted[section] for section,key in GROWTH_SWITCHES.items()})
  self.initial=dict(wanted);self.gui.settings_model=model
  self.gui.refresh_summary()
 def save(self,wanted,write_goals):
  """Disable first, write targets, enable last. A failed save cannot enable
  new spending with stale targets. Do not roll back by re-enabling features."""
  model=self.validate(wanted)
  off_first={s:self.initial[s] and wanted[s] for s in GROWTH_SWITCHES}
  if off_first!=self.initial:self._save(model,off_first)
  write_goals()
  # Re-read after target persistence; concurrent character/master changes
  # must not enable a feature in another context.
  model=self._model()
  if wanted!=self.initial:self._save(model,wanted)
