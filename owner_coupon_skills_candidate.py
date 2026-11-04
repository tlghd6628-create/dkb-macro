"""30-level coupon-skill learning; box consumption still needs item evidence."""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
TARGETS=((84,'생명의 흐름'),(68,'방패 밀기'),(89,'공간 결계'))
class NavigationError(RuntimeError):pass

def require_owned_filter(ui,Pending):
 """Protect every owned-list page, including LearnOne's internal scans."""
 import numpy as np
 from owner_starter_choice_candidate import owned_filter_frame,owned_filter_proved
 original_scan=ui.scan_owned
 def scan():
  original_rows=ui.skill_rows
  def rows():
   values=original_rows();pair=getattr(ui,'_owner_last_rows_pair',None)
   if (not pair or len(pair[0])!=2 or len(pair[1])!=2 or
       pair[0][0] is pair[0][1] or np.shares_memory(pair[0][0],pair[0][1]) or
       any(not 0<=time.monotonic()-t<=3 for t in pair[1])):
    raise Pending('보유 도술 행 두 화면 확인 필요')
   if not all(owned_filter_frame(frame) for frame in pair[0]) or not owned_filter_proved(ui):
    raise Pending('보유 도술 필터 확인 필요')
   return values
  ui.skill_rows=rows
  try:return original_scan()
  finally:ui.skill_rows=original_rows
 ui.scan_owned=scan

def process(adapter,context,inputs):
 from owner_progression import state
 from owner_energy_box_runtime_candidate import fresh_character
 from owner_hunt_rules_candidate import configured_identity
 from owner_skill_goal import runtime_ledger,Pending
 from owner_skill_ui import SkillUI
 from owner_learned_skills_candidate import LearnedSkills
 progress=state(adapter);character=progress.character
 if not fresh_character(adapter,context,progress) or progress.level<30:return 'identity_or_level_hold'
 scope=configured_identity(adapter.project.root);ledger=runtime_ledger(adapter,character)
 store=LearnedSkills(adapter.project.root,ledger.receipt_key)
 missing=[(sid,name) for sid,name in TARGETS if not store.known(name)]
 if not missing:return 'already_learned'
 old=getattr(adapter,'_owner_coupon_skills_attempt',None)
 if old and old[0] is context and old[1]==ledger.receipt_key and 0<=time.monotonic()-old[2]<600:return 'retry_wait'
 def guard():
  context.checkpoint();current=state(adapter)
  return current.character==character and fresh_character(adapter,context,current) and configured_identity(adapter.project.root)==scope
 ui=None;outcomes=[]
 try:
  if guard() is not True:raise Pending('현재 캐릭터 확인 필요')
  ui=SkillUI(adapter,context,inputs);ui._owner_identity_guard=guard
  require_owned_filter(ui,Pending)
  if not ui.normal():raise Pending('도술 확인 전 일반 화면 확인 필요')
  for sid,name in missing:
   if guard() is not True:raise Pending('현재 캐릭터 확인 필요')
   current=LearnedSkills(adapter.project.root,ledger.receipt_key)
   if current.known(name):continue
   try:
    # The existing method proves the exact individual skill + learn dialog,
    # and holds instead of pressing the bulk learn button.
    if ui.learn_one(sid,ledger,coupon=True) is not True:raise Pending('개별 학습 결과 미확인')
    current.observed(name,verified=True);outcomes.append((name,'verified'))
   except Pending as exc:
    outcomes.append((name,'held'))
    LOG.info('쿠폰 도술 학습 보류 · %s · %s',name,str(exc))
    # Once a learn was submitted, no other resource action may mask its result.
    if ledger.item.get('learning_intents',{}).get(str(sid),{}).get('status')=='intent':break
  adapter._owner_coupon_skills_attempt=(context,ledger.receipt_key,time.monotonic())
 finally:
  if ui is not None:
   try:ui.close_known()
   except Exception as exc:raise NavigationError('도술 화면 종료 확인 필요') from exc
 return outcomes
