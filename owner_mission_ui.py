"""Mission-tab catalog. Unknown/partial lists never mean all quests cleared."""
from pathlib import Path
from functools import lru_cache
import re,time,hashlib,logging
from owner_skill_ui import SkillUI,Pending,quest_screen,match,clean
from owner_membership import hit
from owner_mission_policy import normalize
from owner_mission_reading import MissionRowUnreadable,read_selected_title,selected_center
LOG=logging.getLogger('project_gui.DKB')
AUTO_BUTTONS=('버튼_임무_자동진행',*(f'버튼_임무_자동진행시작{i}' for i in range(1,5)))

def auto_button_hit(detector,frame):
 import numpy as np
 if not quest_screen(frame) or selected_center(frame) is None:return None
 for name in AUTO_BUTTONS:
  if name not in detector.templates:continue
  found=detector.find(name,frame,threshold=.95)
  if not found:continue
  x,y,box=found;l,t,r,b=box
  if not (750<=l<r<=881 and 430<=t<b<=474):continue
  needle=detector.templates[name];patch=frame[t:b,l:r];white=needle.min(axis=2)>170
  if patch.shape==needle.shape and white.sum()>=8 and float((patch.min(axis=2)[white]>150).mean())>=.85:return found
 return None

@lru_cache(maxsize=12)
def image(name):
 from PIL import Image
 import numpy as np
 return np.asarray(Image.open(Path(__file__).parent/'assets/mission-catalog'/(name+'.png')).convert('RGB'))

def markers(frame,name,x=45,width=24):
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return []
 patch=frame[96:438,x:x+width];points=[]
 variants=(name,'leaf-story-active') if name=='leaf-story' else ((name,'group-closed-current') if name=='group-closed' else (name,))
 # Small diamond icons shift through fractional list-row raster positions.
 # The lower icon threshold is identity-only; selected title and conditions
 # still require two fresh reads before any quest action.
 for variant in variants:
  needle=image(variant);values=cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)
  ys,xs=np.where(np.nan_to_num(values,nan=-1)>=(.75 if name.startswith('leaf-') else .90))
  for y in ys:
   center=96+int(y)+needle.shape[0]//2
   if all(abs(center-old)>15 for old in points):points.append(center)
 return sorted(points)

def row_signature(frame,y):
 import cv2,numpy as np
 patch=frame[max(96,y-9):min(438,y+10),70:480]
 # Text-only contrast, independent of selected row/background and mouse.
 gray=cv2.cvtColor(patch,cv2.COLOR_RGB2GRAY)
 return hashlib.sha256((gray>150).astype('uint8').tobytes()).hexdigest()

def required_power(rows):
 candidates=set()
 for r in rows:
  if r['score']<.92:continue
  for a,b in re.findall(r'([\d,]+)\s*/\s*([\d,]+)',r['text']):
   try:
    v=int(b.replace(',',''))
    if 1000<=v<=10000000:candidates.add(v)
   except ValueError:pass
 return next(iter(candidates)) if len(candidates)==1 else None

def parse_remaining(rows):
 values=set()
 for row in rows:
  if row.get('score',0)<.99:continue
  m=re.fullmatch(r'\s*([0-5])\s*/\s*5\s*',row['text'])
  if m:values.add(int(m[1]))
 return next(iter(values)) if len(values)==1 else None

def remaining_on_screen(ui):
 # The fixed label distinguishes this counter from membership instant-use
 # quota elsewhere in the same menu. Korean OCR is too small here; use its
 # exact observed label plus two number-only reads.
 first=ui.frame()
 if not quest_screen(first):return None
 if hit(first,'quota-label-accepted',(280,441,62,22),.9):
  # The game now counts up: 수락한 임무 N/5, so N accepted leaves 5-N.
  ui.context.wait(.12)
  if not hit(ui.frame(),'quota-label-accepted',(280,441,62,22),.9):return None
  # Tiny text scores about .87-.94 here, so the agreement of two reads is the proof.
  values=[]
  for _ in range(2):
   found={m[1] for row in ui.rows((333,442,21,20),language='number',pair=False) if row.get('score',0)>=.8 for m in [re.fullmatch(r'\s*([0-5])\s*/\s*5\s*',row['text'])] if m}
   values.append(next(iter(found)) if len(found)==1 else None)
  return 5-int(values[0]) if values[0] is not None and values[0]==values[1] else None
 if not hit(first,'quota-label',(268,438,87,27),.95):return None
 ui.context.wait(.12);second=ui.frame()
 if not hit(second,'quota-label',(268,438,87,27),.95):return None
 if hit(first,'quota-five',(343,438,34,27),.97) and hit(second,'quota-five',(343,438,34,27),.97):return 5
 return parse_remaining(ui.rows((345,440,30,22),language='number'))

def fit_rows_left(frame):
 """Rows tagged green (strong enough) that lack the round in-progress mark on the right."""
 left=0
 for n in range(9):
  y=112+round(38.3*n);tag=frame[y-8:y+8,588:612].astype('int16')
  green=((tag[...,1]-tag[...,0]>25)&(tag[...,1]-tag[...,2]>25)).sum()
  mark=(frame[y-9:y+10,628:650].min(axis=2)>190).sum()
  if green>=15 and mark<25:left+=1
 return left

def instant_left(ui):
 """멤버십 즉시 완료 남은 횟수 N/5, on the daily tab only."""
 values=[]
 for _ in range(2):
  found={m[1] for row in ui.rows((700,416,132,18),pair=False) if row.get('score',0)>=.8 and '즉시' in row['text'] for m in [re.search(r'([0-5])\s*/\s*5\s*$',row['text'])] if m}
  values.append(next(iter(found)) if len(found)==1 else None)
 return int(values[0]) if values[0] is not None and values[0]==values[1] else None

def accepted_quota(ui):
 first=ui.frame()
 if not quest_screen(first) or not hit(first,'accepted-label',(594,438,44,28),.93):return None
 ui.context.wait(.08);second=ui.frame()
 if not hit(second,'accepted-label',(594,438,44,28),.93):return None
 if hit(first,'accepted-eighteen',(632,438,30,28),.97) and hit(second,'accepted-eighteen',(632,438,30,28),.97):return 18
 rows=ui.rows((634,440,27,22),language='number');values=set()
 for row in rows:
  m=re.fullmatch(r'\s*(\d{1,2})\s*/\s*20\s*',row['text'])
  if m and row['score']>=.99 and 0<=int(m[1])<=20:values.add(int(m[1]))
 return next(iter(values)) if len(values)==1 else None

def side_story_gate(text):
 """The side story a main step is waiting on, named in its objective: 외전 '기묘리의 방랑 도사' 완료하기."""
 found=re.search(r"외전\s*['‘\"]?\s*([^'’\"]+?)\s*['’\"]?\s*완료",text)
 return normalize(found[1]) if found else None

class MissionUI(SkillUI):
 def __init__(self,adapter,context,inputs):
  super().__init__(adapter,context,inputs)
  from project_adapter.town_services import TownServices
  from project_adapter import mission_quests
  names=list(self.service.detector.templates)+list(getattr(mission_quests,'NAMES',()))+list(AUTO_BUTTONS)+['버튼_전체매뉴','버튼_전체매뉴_임무','체크_임무','버튼_나가기','버튼_X']
  self.service=TownServices(adapter,context,inputs,list(dict.fromkeys(names)))
 def open(self,mode):
  entered=not quest_screen(self.frame())
  if not quest_screen(self.frame()):
   self.adapter.exit_sleep_mode(self.context,self.inputs)
   self.key(0x4a)
   try:self.wait(quest_screen,2)
   except Pending:
    # J may arrive during a map transition. Wait without another key/menu
    # click; an eventually opened mission screen must not be toggled closed.
    def ready(frame):
     return quest_screen(frame) or bool(self.service.detector.find('버튼_전체매뉴',frame,threshold=.95))
    try:
     frame=self.wait(ready,15)
     if not quest_screen(frame):
      self.service.button('버튼_전체매뉴',wait_before_click=.2)
      self.service.button('버튼_전체매뉴_임무',wait_before_click=.2)
      self.wait(quest_screen)
    except RuntimeError as exc:
     if not str(exc).startswith('버튼 미감지:'):raise
     raise Pending('임무 메뉴 이동 중 화면이 바뀌어 다시 확인합니다') from exc
  self.opened='quest';self.click(63 if mode=='main_quest' else 146,53,quest_screen)
  if entered:self._owner_mission_fresh_open=True
 def close_known(self):
  if quest_screen(self.frame()) and not self.execution_dialogue(self.frame()):
   self.click(21,19,quest_screen)
   self.wait(lambda f:not quest_screen(f))
  self.opened=None
 def execution_dialogue(self,frame):
  if not hasattr(self,'adapter'):return False
  slots=getattr(self,'_execution_slots',None)
  if slots is None:
   from project_adapter.main_quest import StateROIs
   mode=self.adapter.mode if self.adapter.mode in ('main_quest','sub_quest') else 'sub_quest'
   slots=StateROIs(self.adapter.project.root/'profiles'/self.adapter.project.code,mode=mode);self._execution_slots=slots
  return any(slots.match(key,frame).get('hit') for key in ('skip','skip_confirm','skip_confirm2'))
 def execution_dialogue_pair(self):
  if not self.execution_dialogue(self.frame()):return False
  self.context.wait(.12);return bool(self.execution_dialogue(self.frame()))
 def wheel(self,direction,notches=8,*,at=(456,300),scene=quest_screen,verify_cursor=False):
  # Normal Windows wheel events under the same product input transaction.
  # No window messages, memory access, driver or second input thread.
  import ctypes
  from ctypes import wintypes as W
  class M(ctypes.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
  class U(ctypes.Union):_fields_=[('mi',M),('padding',ctypes.c_byte*32)]
  class I(ctypes.Structure):_fields_=[('type',W.DWORD),('u',U)]
  send=ctypes.windll.user32.SendInput;send.argtypes=[W.UINT,ctypes.POINTER(I),ctypes.c_int];send.restype=W.UINT
  if not scene(self.frame()):raise Pending('목록 이동 전 화면 확인 필요')
  with self.inputs.transaction():
   self.inputs.move(*at)
   for _ in range(notches):
    self.context.checkpoint();self.inputs._guard_target()
    if verify_cursor:
     # SendInput wheel is desktop-wide. Only emit it if our existing backend
     # actually put the physical cursor inside the intended game panel.
     import win32gui
     from input_target import resolve
     from window_resolution import physical_coordinates
     hwnd,cx,cy=resolve(self.adapter.window,int(at[0]),int(at[1]))
     with physical_coordinates():
      sx,sy=win32gui.ClientToScreen(hwnd,(cx,cy));px,py=win32gui.GetCursorPos()
     if win32gui.GetForegroundWindow()!=hwnd or abs(px-sx)>3 or abs(py-sy)>3:
      raise Pending('감정 목록 스크롤 입력 대상 확인 필요')
     if not scene(self.frame()):raise Pending('감정 목록 스크롤 전 화면 변경')
    event=I(0,U(mi=M(0,0,(120*direction)&0xffffffff,0x0800,0,0)))
    if send(1,ctypes.byref(event),ctypes.sizeof(I))!=1:raise Pending('임무 목록 휠 입력 미완료')
    self.context.wait(.04)
  self.context.wait(.35)
 def startable_main(self,frame,y):
  """A new chapter's first step stays grey until started, though the game has selected it and offers AUTO.
  A step locked behind another quest shows the same button; its condition text still blocks it in _selected."""
  if selected_center(frame)!=y:return False
  if auto_button_hit(self.service.detector,frame):return True
  return any('자동진행' in clean(row['text']) and row['score']>=.88 for row in self.rows((674,432,205,40)))
 def selected(self,mode,y,book,power):
  self._owner_last_mission_read={}
  try:return self._selected(mode,y,book,power)
  except Pending as exc:
   if not quest_screen(self.frame()):raise
   detail=getattr(self,'_owner_last_mission_read',{}) or getattr(self,'_owner_last_pair_mismatch',{})
   LOG.warning('퀘스트 행 판독 보류 · mode=%s selected=mission_title · y=%s · %s · 후보=%s',mode,y,exc,str(detail)[:950])
   raise MissionRowUnreadable(str(exc)) from exc
 def _selected(self,mode,y,book,power):
  self.click(280,y,quest_screen)
  title,y=read_selected_title(self,y)
  frame=self.frame()
  # Selected leaf, not a group header or an unrelated completed quest.
  if selected_center(frame)!=y:raise MissionRowUnreadable('선택 임무 강조 행 위치 재확인 필요')
  complete=bool(match(frame,'completed',(624,max(96,y-14),28,28),.96))
  self.context.wait(.12)
  complete=complete and bool(match(self.frame(),'completed',(624,max(96,y-14),28,28),.96))
  suitable=mode=='main_quest' or hit(frame,'suitable',(512,max(96,y-15),84,30),.90) is not None
  import numpy as np
  # Grey future steps remain unsuitable for execution even when their power
  # badge is green. Their prerequisites have not necessarily been satisfied.
  bright=int((frame[max(96,y-8):min(438,y+9),70:480].min(axis=2)>180).sum())>=20
  if mode=='main_quest' and not bright:bright=self.startable_main(frame,y)
  rows=self.rows((674,229,202,111));text=' '.join(r['text'] for r in rows if r['score']>=.85)
  required=required_power(rows);prereq=None
  found=re.search(r'(\[[^\]]+\][^\n]+?)\s*임무.*완료',text)
  if found:prereq=normalize(found[1])
  has_prereq=any(s in clean(text) for s in ('선행','임무완료후','임무를완료'))
  # '[4장] 쉬어가는 길' only asks for a side story to be finished; AUTO on it stood still for minutes.
  side=side_story_gate(text)
  if side:has_prereq=True;prereq=side
  gated=required is not None and (power is None or power<required)
  objective=clean(text).split('실행조건')[0].split('완료보상')[0].replace('임무목표','')
  objective=re.sub(r'[0-9,]+/[0-9,]+','',objective)
  accepted=bool(auto_button_hit(self.service.detector,frame))
  if not accepted:
   buttons=self.rows((674,432,205,40))
   accepted=any('자동진행' in clean(row['text']) and row['score']>=.88 for row in buttons)
  key=book.observe(mode,title,objective=objective,completed=complete,suitable=bool(suitable),actionable=bright and not has_prereq and not gated,accepted=accepted,required_power=required,source='paired_selected_mission_tab')
  chapter=re.search(r'\[\s*(\d+)\s*장\s*\]',str(title))
  if mode=='main_quest' and bright and not complete and chapter and book.chapter_reached(int(chapter[1])):
   LOG.info('지난 장 조건으로 보류된 임무 다시 확인 · 현재 %s장',chapter[1])
  if complete:
   from owner_skill_goal import STORY,runtime_ledger
   if clean(STORY+'5') in clean(title):
    from owner_progression import state
    ledger=runtime_ledger(self.adapter,state(self.adapter).character)
    if ledger.item.get('story_step',0)<5:
     ledger.story_receipt(5,{'title':STORY+'5','verified':True,'source':'paired_selected_mission_tab_completed_mark'})
    if ledger.item.get('stage') in ('purchase','presets'):self.adapter._owner_skill_purchase_ready=True
  if not complete:
   if gated:book.defer(key,'power',required=required)
   elif has_prereq:book.defer(key,'prerequisite',prerequisite=prereq,detail=text[:300])
   elif not book.item['quests'][key].get('block',{}).get('functional_hold'):
    book.prerequisite_proved(key)
  return key
 def accept_only(self,book,key,before):
  if before is None or before>=20:return False
  self.click_word('임무 수락',(675,432,200,40),quest_screen,minimum=.85)
  self.wait(quest_screen,seconds=3)
  from owner_mission_reading import agree_titles
  title,_=read_selected_title(self,selected_center(self.frame()))
  if not agree_titles(title,book.item['quests'][key]['title']):raise Pending('서사 수락 후 선택 임무 변경')
  if not auto_button_hit(self.service.detector,self.frame()):self.word('자동 진행',(750,432,130,40),minimum=.88)
  after=accepted_quota(self)
  if after is None or after!=before+1:raise Pending('서사 일괄 수락 후 수락 개수 변화 확인 필요')
  book.item['quests'][key]['accepted']=True;book.commit();return True
 def pick(self,book,requested,power,*,fill=False,reconcile_depth=0):
  active=getattr(book,'item',{}).get('active')
  if active and book.eligible(active,power) and book.item['quests'][active]['mode'] in (('main_quest','sub_quest') if requested=='main_quest' else ('sub_quest',)) and self.execution_dialogue_pair():
   LOG.info('진행 임무 대화 화면 · 임무 탭 재열기 없이 기존 대화 처리기로 연결');return active
  if requested=='sub_quest':
   from owner_story_groups import pick
   return pick(self,book,power)
  return self._pick_legacy(book,requested,power,fill=fill,reconcile_depth=reconcile_depth)
 def to_list_top(self):
  """A long list left at its end needs more than one sweep; a second scan used to read nothing."""
  import hashlib
  def view():return hashlib.sha256((self.frame()[100:436,70:490].min(axis=2)>145).tobytes()).hexdigest()
  self.wheel(1,35);self.context.wait(.35);previous=view()
  for _ in range(4):
   self.wheel(1,35);self.context.wait(.35);current=view()
   if current==previous:return
   previous=current
 def _pick_legacy(self,book,requested,power,*,fill=False,reconcile_depth=0):
  active=book.item.get('active');modes=('main_quest','sub_quest') if requested=='main_quest' else ('sub_quest',)
  if requested=='sub_quest' and active and book.item['quests'][active]['mode']=='main_quest':book.item['active']=None;book.commit();active=None
  if fill:
   book.start_batch();modes=('sub_quest',)
   if book.item['batch'].get('title_reader')!='selected-row-v2':
    # Old narrow-header OCR produced inconsistent identities. Reconfirm the
    # pending batch, keeping all quest/death/prerequisite history untouched.
    book.item['batch'].update(keys=[],title_reader='selected-row-v2');book.commit()
    LOG.info('서사 수락 묶음 재확인 · 넓은 선택 행 제목 기준 · 기존 임무·사망 기록 유지')
  # A running story used to skip the main list altogether, so a main step waiting on a side story was never
  # read again while another story was on hand ('읽은 행=0' at 14:50). Its row is read first until it opens.
  main_waiting=requested=='main_quest' and not fill and any(r.get('mode')=='main_quest' and r.get('block',{}).get('reason')=='prerequisite' for r in book.item['quests'].values())
  if active and book.item['quests'][active]['mode'] in modes and not main_waiting:
   modes=(book.item['quests'][active]['mode'],)+tuple(m for m in modes if m!=book.item['quests'][active]['mode'])
  keys=[];seen=set();expanded=set();unknown=0;partial=False
  for mode in modes:
   if mode=='sub_quest' and requested=='main_quest':
    # A finished main quest turns grey and the scan skips it, so it can stay saved as active.
    # It then blocks the current row it just read, and the block at the end of this function is never reached.
    stale=book.item.get('active')
    LOG.info('본편 목록 확인 결과 · 읽은 행=%d · 판독 보류=%d · 저장된 진행 임무=%s',len(keys),unknown,book.item['quests'][stale]['title'] if stale else '없음')
    # The same row can read 탐방 then 탈방, and that used to retire the quest it was running.
    if stale and stale not in keys:
     from difflib import SequenceMatcher
     near=[k for k in keys if SequenceMatcher(None,book.item['quests'][k]['title'],book.item['quests'][stale]['title']).ratio()>=.8]
     if near:
      LOG.info('본편 진행 임무 제목 차이 흡수 · %s',book.item['quests'][near[0]]['title'])
      book.activate(near[0]);return near[0]
    if stale and book.item['quests'][stale]['mode']=='main_quest' and stale not in keys and book.choose(keys,'main_quest',power) and reconcile_depth<2:
     book.defer(stale,'condition',detail='본편 목록 밝은 행에 없음 · 완료로 단정하지 않음')
     LOG.info('본편 이전 진행 임무 미표시 · 완료 처리 없이 보류 · 현재 임무 재선택')
     return self._pick_legacy(book,requested,power,reconcile_depth=reconcile_depth+1)
    from owner_story_groups import pick
    return pick(self,book,power)
   if mode=='sub_quest' and not fill and book.batch_needs_fill(power):self._pick_legacy(book,'sub_quest',power,fill=True,reconcile_depth=reconcile_depth)
   self.open(mode);self.to_list_top();last=None;still=0
   capacity=accepted_quota(self) if fill else None
   for page in range(100):
    self.context.checkpoint();frame=self.frame()
    leaves=markers(frame,'leaf-main' if mode=='main_quest' else 'leaf-story')
    for y in leaves:
     if y<108 or y>424:continue
     import numpy as np
     # Grey future steps cannot be executed. Do not OCR every future row
     # while looking for the saved active/current mission.
     if (int((frame[max(96,y-8):min(438,y+9),70:480].min(axis=2)>180).sum())<20
         and not (mode=='main_quest' and self.startable_main(frame,y))):continue
     sig=(mode,row_signature(frame,y))
     if sig in seen:continue
     seen.add(sig)
     try:key=self.selected(mode,y,book,power)
     except MissionRowUnreadable:
      # This row remains unresolved, never completed. Other proved rows keep
      # their receipts and may run; do not restart the complete catalog.
      unknown+=1
      if not quest_screen(self.frame()):raise
      frame=self.frame()
      if fill and unknown>=3 and keys and book.item['batch']['keys']:
       partial=True;break
      continue
     keys.append(key)
     seen.add((mode,row_signature(self.frame(),y)))
     if fill:
      if book.eligible(key,power):
       accepted=book.item['quests'][key].get('accepted') is True
       if not accepted and capacity is not None and capacity<20:
        accepted=self.accept_only(book,key,capacity)
        if accepted:capacity+=1
       if accepted:book.batch_add(key)
      if len(book.item['batch']['keys'])>=20:
       book.seal_batch();LOG.info('서사 일괄 수락 완료 · 묶음=%s · 진행 대상=20개',book.item['batch']['number']);return None
      frame=self.frame();continue
     choice=book.choose(keys,requested,power)
     # A saved active quest has priority until independently completed or
     # deferred. Do not select another merely because it appears first.
     waiting=book.item.get('active')
     # Except a main step whose condition just cleared: the story was only ever filling that wait.
     reopened=choice and mode=='main_quest' and book.item['quests'][choice].get('condition_recovered')
     if choice and (not waiting or choice==waiting or reopened):
      if choice!=key:continue
      book.item['quests'][key].pop('condition_recovered',None)
      book.activate(key);return key
     frame=self.frame()
    if partial:break
    # Expand closed groups only. Existing open groups are preserved.
    closed=markers(frame,'group-closed',x=20,width=18)
    expanded_now=False
    for y in closed:
     sig=row_signature(frame,y)
     if sig in expanded:continue
     expanded.add(sig);self.click(28,y,quest_screen);expanded_now=True;break
    if expanded_now:continue
    import cv2
    signature=hashlib.sha256((cv2.resize(frame[100:436,70:490],(105,84)).min(axis=2)>145).astype('uint8').tobytes()).hexdigest()
    still=still+1 if signature==last else 0;last=signature
    if still>=2:break
    self.wheel(-1,10)
   else:
    if not keys:raise Pending('임무 전체 목록 탐색 한도 · 완료로 간주하지 않음')
    partial=True
    LOG.warning('퀘스트 목록 탐색 범위 종료 · 확인된 항목 우선 · 미확인 항목은 완료 처리하지 않음')
  if not keys:raise Pending('임무 목록의 진행 가능 행을 확인하지 못함 · 전체 완료나 사냥 전환으로 간주하지 않음')
  if fill:
   book.item['batch']['unreadable_rows']=unknown
   book.item['batch']['scan_complete']=not partial
   book.seal_batch();LOG.info('서사 일괄 수락 확인 · 묶음=%s · 가능한 대상=%s/20 · 현재 수락 수=%s · 판독 보류=%s행',book.item['batch']['number'],len(book.item['batch']['keys']),capacity,unknown);return None
  if book.item.get('active'):
   missing=book.item['active']
   if book.item['quests'][missing].get('block'):
    book.item['active']=None;book.commit()
   else:book.defer(missing,'condition',detail='현재 목록 탐색에서 재확인되지 않음 · 완료로 단정하지 않음')
   LOG.warning('퀘스트 목록 재확인 · 이전 진행 임무 미표시 · 완료 처리 없이 보류 · 다른 확인된 임무 진행')
  for missing in tuple(book.item['batch']['keys']):
   if missing not in keys and book.eligible(missing,power):
    book.defer(missing,'condition',detail='현재 목록에서 재확인되지 않은 이전 묶음 항목 · 완료 아님')
  fresh=[key for key in keys if book.eligible(key,power) and book.item['quests'][key].get('accepted')][:20]
  if fresh and fresh!=book.item['batch']['keys']:
   if reconcile_depth>=2:raise Pending('임무 기록 재확인이 반복되어 진단 확인 필요')
   book.item['batch'].update(keys=fresh,phase='drain',scan_complete=not partial,unreadable_rows=unknown);book.commit()
   return self._pick_legacy(book,requested,power,reconcile_depth=reconcile_depth+1)
  return None
 def start_selected(self):
  if self.execution_dialogue_pair():
   LOG.info('알려진 임무 대화 화면 · 기존 ESC 처리기로 연결');self.opened=None;return
  if not self.click_auto():
   try:self.click_word('임무 수락',(675,432,200,40),quest_screen,minimum=.85)
   except Pending:pass
   if quest_screen(self.frame()) and not self.click_auto():self.click_word('자동 진행',(750,432,130,40),quest_screen,minimum=.85)
  self.context.wait(.15)
  if quest_screen(self.frame()) and not self.execution_dialogue(self.frame()):self.close_known()
  self.wait(lambda f:not quest_screen(f) or self.execution_dialogue(f),seconds=12);self.opened=None
 def click_auto(self):
  first=auto_button_hit(self.service.detector,self.frame())
  if not first:return False
  self.context.wait(.10);second=auto_button_hit(self.service.detector,self.frame())
  if not second or second[:2]!=first[:2]:return False
  self.click(second[0],second[1],lambda f:bool((hit:=auto_button_hit(self.service.detector,f)) and hit[:2]==second[:2]))
  LOG.info('선택 임무 자동 진행 · 기존 버튼 이미지 두 화면 확인')
  return True
 def remaining_quota(self,weekly=False):
  self.open('sub_quest');self.click(315 if weekly else 231,53,quest_screen)
  return remaining_on_screen(self)
