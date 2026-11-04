"""Menu-only probe on the product's existing input owner and target guards.

There is no run_* call and no purchase, accept, claim, enhance or enter action.
Unknown screens remain unchanged. A menu being visible never proves a gameplay
operation or a numerical decision succeeded.
"""
from pathlib import Path
from datetime import datetime
import threading,time,hashlib
from owner_native_contracts import energy_contract,find_energy_entry,validate_feature,NativeContractError,pool_for,menu_aliases,menu_candidates,menu_regions,find_menu_target
ENERGY=energy_contract()

# Only navigation buttons may be invoked. Action/confirm buttons are absent.
PATHS={
 'gear':('버튼_전체매뉴_성장','버튼_성장_장비탭'),
 'gear_enhance':('버튼_전체매뉴_성장','버튼_성장_장비탭','버튼_성장_강화'),
 'gear_break':('버튼_전체매뉴_성장','버튼_성장_장비탭','버튼_성장_장비_돌파'),
 'gear_awaken':('버튼_전체매뉴_성장','버튼_성장_장비탭','버튼_성장_장비_각성'),
 'blessing_growth':('버튼_전체매뉴_성장','버튼_성장_장비탭','버튼_성장_가호탭'),
 'skill_growth':('버튼_전체매뉴_성장','버튼_성장_도술탭'),
 'energy':(ENERGY['entries'][0],),
 'daily_dungeon':('버튼_전체매뉴_비경',),
 'daily24_dungeon':('버튼_전체매뉴_비경',),
 'weekly_dungeon':('버튼_전체매뉴_비경','버튼_비경_전래동화탭'),
 'weekly24_dungeon':('버튼_전체매뉴_비경','버튼_비경_전래동화탭'),
 'clan_training':('버튼_전체매뉴_문파',),
 'clan_request':('버튼_전체매뉴_문파','버튼_문파_전투'),
 'spirit':('버튼_전체매뉴_영기수련',),
 'blessing_reward':('버튼_전체매뉴_가호',),
 'seal_release':('버튼_전체매뉴_단봉인해제',),
}
CHECKS={
 'gear':('체크_성장',),'blessing_growth':('체크_성장',),'skill_growth':('체크_성장',),
 'gear_enhance':('체크_성장',),'gear_break':('체크_성장',),'gear_awaken':('체크_성장',),
 'energy':(ENERGY['check'],),'daily_dungeon':('체크_비경',),
 'daily24_dungeon':('체크_비경',),'weekly_dungeon':('체크_비경',),'weekly24_dungeon':('체크_비경',),
 'clan_training':('체크_문파',),'clan_request':('체크_문파',),
 'spirit':('체크_영기수련',),'blessing_reward':('체크_전체매뉴_가호',),
 'seal_release':('체크_단봉인해제',),
 'mail':('체크_우편함',),'events':('체크_이벤트',),'guide':('체크_길라잡이',),
}
DIRECT={'mail':'버튼_우편','events':'버튼_이벤트','guide':'버튼_길라잡이'}
# Each window's own close button in the original modules.
CLOSE={'guide':'버튼_X_창','events':'버튼_X_이벤트창'}
MAX_TARGET_SECONDS=40
NAV=frozenset(['버튼_전체매뉴','버튼_나가기',*CLOSE.values(),*ENERGY['entries']]+[name for path in PATHS.values() for name in path]+list(DIRECT.values())+[name for group in menu_aliases().values() for name in group])

class MenuProbe:
 def __init__(self,gui,adapter,cancel):
  self.gui,self.adapter,self.cancel=gui,adapter,cancel
  self.context=None;self.inputs=None;self.service=None;self.known=None;self.saved=set();self.last_frame=None
  self.navigation=[]
  self.normalized=False
 def _init(self):
  if self.service is not None:return
  from biol_base.session import Context
  from project_adapter.town_services import TownServices
  self.context=Context(self.cancel,threading.Event())
  self.inputs=self.gui.session.input_factory(self.adapter.input_backend,self.context)
  names=set(NAV)|{n for names in CHECKS.values() for n in names}
  names.update(menu_regions());names.update(CLOSE.values())
  names.update(('버튼_전체매뉴_임무','체크_임무','버튼_인벤토리','버튼_나가기','버튼_X'))
  from owner_special_contexts import NAMES
  from project_adapter.secret_exploration import AUTO_NAMES
  names.update(NAMES);names.update(AUTO_NAMES)
  names.update(('체크_던전진행중','버튼_던전_나가기'))
  self.service=TownServices(self.adapter,self.context,self.inputs,list(names))
 def frame(self):
  self.context.checkpoint();self.service.check()
  self.last_frame=self.service.capture();return self.last_frame
 def pair(self,predicate):
  first=predicate(self.frame());self.context.wait(.12)
  return bool(first and predicate(self.frame()))
 def wait_pair(self,predicate,seconds=2):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if self.pair(predicate):return True
   self.context.wait(.08)
  return False
 def field(self,frame):
  # Transparent menus retain the field HUD. Prove known panels are absent
  # before accepting the generic HUD classifier as a navigation boundary.
  if any(self.menu_visible(key,frame) for key in ('all_menu','main','inventory','skill_preset')):return False
  if any(self.service.detector.find(name,frame,threshold=.96) for name in {n for group in CHECKS.values() for n in group}):return False
  from owner_startup_stage import scene
  return scene(self.service.detector,frame)=='field'
 def menu_visible(self,key,frame):
  if key=='all_menu':
   anchors=('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파')
   return sum(bool(self.service.detector.find(name,frame,threshold=.95)) for name in anchors)>=2
  if key in ('main','sub','daily_quest','weekly_quest','folktale'):
   from owner_skill_ui import quest_screen
   return quest_screen(frame)
  if key=='inventory':
   from owner_progression import inventory_parts
   return inventory_parts(frame)==(True,True)
  if key=='skill_preset':
   from owner_skill_ui import skill_screen
   return skill_screen(frame)
  return any(self.service.detector.find(name,frame,threshold=.96) for name in CHECKS.get(key,()))
 def button(self,name):
  if name not in NAV:raise RuntimeError('점검에서는 실행 버튼을 누를 수 없습니다.')
  self.context.checkpoint();self.service.check()
  if name==ENERGY['entries'][0]:
   frame=self.frame()
   name=find_energy_entry(self.service.detector,frame) or name
  self.navigation.append({'kind':'menu','name':name})
  # Menu diagnostics must not enter the native long gameplay retry loop.
  # Prove a native navigation target on two fresh frames, then one click.
  deadline=time.monotonic()+1.2
  while time.monotonic()<deadline:
   frame=self.frame();first=None;chosen=None
   for candidate in menu_candidates(name):
    first=find_menu_target(self.service.detector,candidate,frame)
    if first:chosen=candidate;break
   if first:
    self.context.wait(.08)
    second=find_menu_target(self.service.detector,chosen,self.frame())
    if second and first[2]==second[2]:
     self.context.checkpoint();self.service.check();self.service.click_hit(second);self.context.wait(.08);return True
   self.context.wait(.05)
  raise RuntimeError('메뉴 버튼 두 화면 미확인: '+name)
 def key(self,vk):
  if vk not in (0x49,0x4a,0x4b,0x1b):raise RuntimeError('점검용 메뉴 단축키가 아닙니다.')
  self.navigation.append({'kind':'menu_key','name':{0x49:'I',0x4a:'J',0x4b:'K',0x1b:'ESC'}[vk]})
  self.context.checkpoint();self.service.key(vk)
 def close_menu(self):
  if not self.known:return True
  key=self.known
  if self.pair(lambda frame:self.menu_visible(key,frame)):
   if key=='spirit':
    from owner_diagnostic_repairs import normalize_spirit
    from owner_startup_stage import scene
    if normalize_spirit(self.service,self.context,scene):
     self.known=None;return True
   if key=='inventory':self.key(0x49)
   elif key=='all_menu':self.key(0x1b)
   elif self.window_close(key):pass
   elif self.pair(lambda frame:bool(self.service.detector.find('버튼_나가기',frame,threshold=.96))):
    self.button('버튼_나가기')
   else:self.key(0x1b)
   if self.wait_pair(self.field):self.known=None;return True
   # Retry one reversible Back only while the exact original menu and its
   # native Back button are freshly proven. Never clear ownership on failure.
   if self.pair(lambda frame:self.menu_visible(key,frame)) and self.pair(lambda frame:bool(self.service.detector.find('버튼_나가기',frame,threshold=.96))):
    self.button('버튼_나가기')
    if self.wait_pair(self.field):self.known=None;return True
  elif self.pair(self.field):self.known=None;return True
  return False
 def evidence(self,item,*,failure=False):
  if self.service is not None:
   try:self.frame()
   except Exception:pass
  if self.last_frame is None or len(self.saved)>=(16 if failure else 6):return None
  digest=hashlib.sha256(self.last_frame.tobytes()).hexdigest()
  if digest in self.saved:return None
  self.saved.add(digest)
  from PIL import Image
  folder=Path(self.adapter.project.root)/'logs/feature-checks/screens';folder.mkdir(parents=True,exist_ok=True)
  name=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'-'+item['id']+'.png'
  target=folder/name;Image.fromarray(self.last_frame).save(target)
  return str(target)
 def __call__(self,item,cancel):
  key=item['id']
  if key not in PATHS and key not in DIRECT and key not in ('main','sub','daily_quest','weekly_quest','folktale','inventory','skill_preset'):
   return {'verified':False,'screen':'미점검','detail':'기본 구성 확인 · 해당 메뉴 판독 연결 필요',
           'stage':'unsupported','finding':'no_probe_path',
           'steps':[{'stage':'menu','status':'not_probed'}]}
  self._init();self.context.checkpoint()
  try:validate_feature(self.service,key)
  except NativeContractError as exc:
   return {'verified':False,'screen':'원본 판독 정의 확인 실패','stage':'contract','finding':'contract_error',
           'detail':str(exc),'steps':[{'stage':'wiring','status':'error'}]}
  if not self.normalized:
   for opened in ('all_menu','spirit','inventory','skill_preset','main','gear','energy','daily_dungeon','clan_training','mail','events','guide'):
    if self.pair(lambda frame:self.menu_visible(opened,frame)):
     self.known=opened;self.close_menu();break
   self.normalized=True
  reuse=(self.known in PATHS and key in PATHS and PATHS[self.known][0]==PATHS[key][0]
         and self.pair(lambda frame:self.menu_visible(self.known,frame)))
  previous=self.known
  if not reuse:self.close_menu()
  if not reuse and not self.pair(self.field):
   # Every later row is skipped too, so say why instead of a bare count.
   import logging
   logging.getLogger('project_gui.DKB').warning('기능 점검 · 일반 필드가 아니라 메뉴 점검 중단 · 던전·전투가 끝난 뒤 필드에서 다시 점검해 주세요')
   return {'verified':False,'screen':'현재 화면 확인 필요',
           'detail':'일반 필드가 아니라 메뉴 점검 중단 · 던전·전투가 끝난 뒤 필드에서 다시 점검','stage':'menu','finding':'field_not_proven',
           'stop_navigation':True,'steps':[{'stage':'menu','status':'field_not_proven'}],
           'evidence_file':self.evidence(item,failure=True)}
  try:
   if key in ('main','sub','daily_quest','weekly_quest','folktale'):self.key(0x4a)
   elif key=='inventory':self.key(0x49)
   elif key=='skill_preset':self.key(0x4b)
   elif key in DIRECT:self.button(DIRECT[key])
   elif reuse:
    old_path=PATHS[previous]
    for index,name in enumerate(PATHS[key]):
     if index>=len(old_path) or name!=old_path[index]:self.button(name)
     if key=='blessing_growth' and name=='버튼_성장_장비탭':self.ensure_enhance()
   else:
    self.button('버튼_전체매뉴')
    if not self.wait_pair(lambda frame:self.menu_visible('all_menu',frame)):
     raise RuntimeError('전체 메뉴 두 화면 인식 확인 필요')
    self.known='all_menu'
    for name in PATHS[key]:
     self.button(name)
     if key=='blessing_growth' and name=='버튼_성장_장비탭':self.ensure_enhance()
   end=time.monotonic()+3
   while time.monotonic()<end:
    if self.pair(lambda frame:self.menu_visible(key,frame)):break
    self.context.wait(.1)
   else:
    evidence=self.evidence(item,failure=True)
    return {'verified':False,'screen':'인식 실패','detail':'메뉴 화면 두 번 확인 실패 · 실행 없음','stage':'menu','finding':'menu_unrecognized','stop_navigation':not self.recover(),'steps':[{'stage':'menu','status':'unrecognized'}],'evidence_file':evidence}
   self.known=key
   # Numerical and eligibility readers differ by feature. Do not translate a
   # root menu title into proof of a particular stage, target, cost or entry.
   screen=('성장 메뉴·탭 미확인' if key in ('gear','gear_enhance','gear_break','gear_awaken','blessing_growth','skill_growth')
           else '비경 목록·단계 미확인' if key.endswith('dungeon')
           else '임무 메뉴·탭 미확인' if key in ('main','sub','daily_quest','weekly_quest','folktale')
           else '메뉴 확인')
   detail='메뉴 인식 확인 · 수치/다음 단계는 미검증 · 실행 없음'
   values_ok=False;value_failed=False;steps=[{'stage':'menu','status':'opened'}];diagnosis=None
   if key=='gear_enhance':
    try:
     from owner_feature_check_gear_candidate import diagnose
     from owner_hunt_rules_candidate import configured_identity
     diagnosis=diagnose(self.service,self.context,self.adapter.project.root,configured_identity(self.adapter.project.root))
     if diagnosis.get('level') is not None:
      screen=f"{diagnosis.get('grade') or '선택 장비'} {diagnosis['level']}강"
     detail=str(diagnosis.get('detail') or detail)
     values_ok=diagnosis.get('values_verified') is True
     steps.extend(list(diagnosis.get('steps') or []))
    except Exception as exc:
     if self.cancel.is_set():raise
     detail='장비 수치 판독 실패 · '+type(exc).__name__+': '+str(exc)[:180]+' · 실행 없음';value_failed=True
   elif key in ('gear_break','gear_awaken'):
    try:
     from owner_feature_check_growth_candidate import read_extra
     from owner_feature_check_gear_candidate import goals,goal_for
     from owner_hunt_rules_candidate import configured_identity
     kind='awaken' if key=='gear_awaken' else 'breakthrough'
     reading=read_extra(self.service,self.context,kind);values_ok=reading.get('verified') is True
     if values_ok:
      level=reading['current'];label='각성' if kind=='awaken' else '돌파';screen=f'{reading["grade"]} {label} {level}'
      target=goal_for(goals(self.adapter.project.root,configured_identity(self.adapter.project.root)),reading['grade'])
      field='awaken' if kind=='awaken' else 'breakthrough';goal=(target or {}).get(field)
      from owner_growth_reading import extra_decision
      stage,finding=extra_decision(target,level,field=field,maximum=reading.get('maximum'),
                                   needs_enhancement=reading.get('needs_enhancement'),ready=reading.get('ready'))
      detail=screen+f' · 목표 {goal} · 재료 선택·성장 실행 없음'
      if reading.get('needs_enhancement') is True:detail+=f' · 직전 강화 {reading["observed_enhancement"]} / 돌파 해금 50강'
     elif reading.get('empty_verified') is True:
      stage,finding='action_ready','no_eligible_item';screen='등록 가능한 장비 없음';detail=reading['detail']
     else:stage,finding='values','values_unreadable';detail=reading.get('detail','현재 단계 판독 실패')
     from owner_growth_reading import breakthrough_allowed
     if kind=='breakthrough' and not breakthrough_allowed():stage,finding='config','breakthrough_disabled'
     diagnosis={'stage':stage,'finding':finding,'decision_verified':reading.get('empty_verified') is True,'targets':reading.get('targets')};steps.append({'stage':'values','status':'read' if values_ok else 'unreadable'})
    except Exception as exc:
     if self.cancel.is_set():raise
     detail='각성·돌파 판독 실패 · '+type(exc).__name__+': '+str(exc)[:180];value_failed=True
   elif key=='blessing_growth':
    try:
     from owner_feature_check_growth_candidate import read_blessing
     from owner_feature_check_gear_candidate import goals
     from owner_hunt_rules_candidate import configured_identity
     ident=configured_identity(self.adapter.project.root)
     from owner_growth_reading import enhance_decision,worst_row
     rows=[];position=0;total=1;deadline=time.monotonic()+MAX_TARGET_SECONDS
     while True:
      reading=read_blessing(self.service,self.context,ident,position=position)
      if reading.get('exhausted'):break
      total=max(total,(reading.get('targets') or {}).get('total',1));position+=1
      if reading.get('verified') is not True:
       rows.append({'stage':'values','finding':'values_unreadable','values_ok':False,'screen':screen,'detail':reading.get('detail','가호 수치 판독 실패')});break
      slot,level=reading['slot'],reading['level']
      target=(goals(self.adapter.project.root,ident) or {}).get('blessings',{}).get(slot)
      row_stage,row_finding=enhance_decision(target,level,ready=reading.get('ready'),materials=reading.get('materials'))
      rows.append({'stage':row_stage,'finding':row_finding,'values_ok':True,'screen':f'가호 {slot} {level}강',
                   'detail':f'가호 {slot} {level}강 · '+str((target or {}).get('enhance','—'))+'강 목표 · 실제 강화 없음'})
      if position>=total or time.monotonic()>=deadline:break
     chosen=worst_row(rows);stage,finding=chosen['stage'],chosen['finding'];screen=chosen['screen'];detail=chosen['detail']
     values_ok=all(row['values_ok'] for row in rows)
     if total>1:detail+=f' · 장착 가호 {len(rows)}/{total} 확인'
     diagnosis={'stage':stage,'finding':finding,'targets':{'read':len(rows),'total':total,'unit':'가호'} if total>1 else None};steps.append({'stage':'values','status':'read' if values_ok else 'unreadable'})
    except Exception as exc:
     if self.cancel.is_set():raise
     detail='가호 수치 판독 실패 · '+type(exc).__name__+': '+str(exc)[:180];value_failed=True
   elif key=='skill_growth':
    try:
     from owner_feature_check_growth_candidate import read_styles
     reading=read_styles(self.service,self.context,self.inputs);values_ok=reading.get('verified') is True
     if values_ok:screen='도술 '+str(len(reading['levels']))+'계열 수치 확인'
     detail=str(reading.get('detail') or '도술 수치 미확인')+' · 실제 강화·각성·돌파 없음'
     diagnosis={'stage':'action_ready' if values_ok else 'values','finding':'decision_not_probed' if values_ok else 'values_unreadable'}
     if values_ok:
      from owner_feature_check_gear_candidate import goals
      from owner_hunt_rules_candidate import configured_identity
      from owner_growth_reading import goal_state
      wanted={name:row for name,row in ((goals(self.adapter.project.root,configured_identity(self.adapter.project.root)) or {}).get('skills') or {}).items() if isinstance(row,dict) and row.get('enabled') is True}
      seen=[name for name in wanted if name in reading['levels']]
      diagnosis['targets']={'read':len(seen),'total':len(wanted),'unit':'계열'} if wanted else None
      # Reaching every goal needs no material reading. Anything below stays
      # undecided, since this tab's price and materials are not read here.
      if wanted and len(seen)==len(wanted) and all(goal_state(wanted[name],reading['levels'][name])=='goal_reached' for name in seen):
       diagnosis['finding']='goal_reached'
     steps.append({'stage':'values','status':'read' if values_ok else 'unreadable'})
    except Exception as exc:
     if self.cancel.is_set():raise
     detail='도술 수치 판독 실패 · '+type(exc).__name__+': '+str(exc)[:180];value_failed=True
   if diagnosis is not None:
    stage,finding=diagnosis['stage'],diagnosis['finding']
   else:
    stage,finding=('values','values_unreadable') if value_failed else ('action_ready','decision_not_probed')
    steps.append({'stage':'values','status':'unreadable' if value_failed else 'unsupported'})
    steps.append({'stage':'decision','status':'not_connected'})
   return {'verified':True,'decision_verified':bool(diagnosis and diagnosis.get('decision_verified') is True),'screen':screen,
           'detail':detail,'stage':stage,'finding':finding,'values_verified':values_ok,'steps':steps,
           'targets':(diagnosis or {}).get('targets'),
           'evidence_file':self.evidence(item,failure=(value_failed or finding in ('values_unreadable','materials_unreadable')))}
  except Exception as exc:
   if self.cancel.is_set():raise
   evidence=self.evidence(item,failure=True)
   return {'verified':False,'screen':'확인 필요','detail':str(exc)[:350],'stage':'menu','finding':'probe_error',
           'stop_navigation':not self.recover(),'steps':[{'stage':'menu','status':'probe_error'}],'evidence_file':evidence}
 def window_close(self,key):
  """Press a window's own proven close button; False when it is not shown."""
  name=CLOSE.get(key)
  detector=self.service.detector
  if not name or name not in getattr(detector,'entries',{name:1}):return False
  if not self.pair(lambda frame:bool(detector.find(name,frame,threshold=.96))):return False
  self.button(name);return True
 def recover(self):
  """One failed item must not hide the rest if the field is proven again."""
  try:
   if self.known and not self.close_menu():return False
   if self.pair(self.field):return True
   # The window may have opened even though its check image was not proven.
   if any(self.window_close(key) for key in CLOSE):return self.wait_pair(self.field)
   return False
  except Exception:
   if self.cancel.is_set():raise
   return False
 def ensure_enhance(self):
  from owner_gear_extra_runtime_candidate import ensure_enhance_tab
  self.navigation.append({'kind':'menu','name':'기존 장비 강화 탭 복귀'})
  ensure_enhance_tab(self.service,self.context)
 def metrics(self):
  return pool_for(self.service).snapshot() if self.service is not None else {}
 def close(self):
  try:
   if self.service is not None and not self.cancel.is_set():self.close_menu()
  finally:
   try:
    if self.inputs is not None:self.inputs.close()
   finally:self.adapter.close()

def factory(gui,cancel):
 """Called on Tk's thread; input initialization remains on the owning worker."""
 snapshot=gui.session.snapshot()
 if snapshot['worker_alive'] or snapshot['status'] in ('running','paused'):raise RuntimeError('매크로를 중지한 뒤 점검해 주세요.')
 try:
  gui.execution_gate()
  adapter=gui.make_adapter()
 except Exception as exc:
  message=str(exc)
  def unavailable(item,cancel):return {'verified':False,'screen':'연결 확인 필요','detail':message}
  return unavailable
 return MenuProbe(gui,adapter,cancel)

def install(gui):
 gui._owner_feature_probe_factory=lambda cancel:factory(gui,cancel)
