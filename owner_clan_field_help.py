"""Free field help button, on the existing quest input worker only."""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
SWITCH='auto_rewards.clan_help.enabled'

def add_switch(schema):
 """Use the native settings model and existing clan capability, default OFF."""
 import copy
 groups=[g for t in schema['tabs'] for g in t['groups']]
 if any(f['id']==SWITCH for g in groups for f in g['fields']):return schema
 source=next(f for g in groups for f in g['fields'] if f['id']=='auto_growth.clan_cooperative_training.enabled')
 target=next(g for g in groups if any(f['id']=='auto_rewards.mail.enabled' for f in g['fields']))
 field=copy.deepcopy(source);field.update(id=SWITCH,label='문파 도움',default=False,existing_default=False,visible=True)
 field.pop('enabled_if',None);target['fields'].append(field)
 return schema

def attempt(ui,*,clock=time.monotonic):
 if getattr(ui.adapter,'values',{}).get(SWITCH) is not True:return False
 from project_adapter.spirit_training import CLAN_HELP
 from roi_runtime import RoiDetector
 from owner_movement import field_hud
 if clock()-getattr(ui,'_owner_clan_help_check',-1e30)<10:return False
 ui._owner_clan_help_check=clock()
 if ui.context.input_depth or getattr(ui.inputs,'held',()):return False
 if not ui.normal():return False
 detector=getattr(ui,'_owner_clan_help_detector',None)
 if detector is None:
  detector=RoiDetector(ui.adapter.project.root/'profiles'/ui.adapter.project.code,[CLAN_HELP]);ui._owner_clan_help_detector=detector
 def hit(frame):
  if not field_hud(frame):return None
  found=detector.find(CLAN_HELP,frame,threshold=.95)
  if found and 0<found[0]<70 and 350<found[1]<425:return found
 a=hit(ui.frame())
 if not a:return False
 ui.context.wait(.12);b=hit(ui.frame())
 if a!=b:return False
 ui.click(b[0],b[1],lambda frame:hit(frame)==b)
 ui._owner_clan_help_check=clock()+20
 LOG.info('문파도움 · 일반 필드 버튼 두 화면 확인 후 클릭 · 수련 입장·구매 없음')
 return True
