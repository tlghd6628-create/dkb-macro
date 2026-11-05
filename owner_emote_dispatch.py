"""Read the requested emote, locate that card, and keep a durable1min limit."""
import hashlib,logging,re,time,sys
from functools import lru_cache
from pathlib import Path
import cv2,numpy as np
from owner_skill_goal import Pending
from biol_base.session import Cancelled
from owner_quest_emote_candidate import asset,panel,paired,empty_chat,target_zone,close_chat,save_navigation,objective,require_cleanup_closed,closed_chat_view
from owner_emote_cooldown import Rate
from owner_emote_atlas import Atlas
from owner_emote_requirements import Catalog,EmoteQuestMismatch,quest_id,parse_target,stage_of,search_order,title_disagrees,title_root
LOG=logging.getLogger('project_gui.DKB')
NAMES={'졸기':'sleep','황당':'surprise','뽐내기':'proud','화남':'angry'}
NATIVE_CARDS={'화남':'버튼_채팅창_감정_화남','웃음':'버튼_채팅창_감정_웃음'}
# Saved 897x479 panel observations. Coordinates nominate a card only; the
# current face/label must still match before reserving or sending any input.
CARD_POSITIONS={'화남':(281,460),'졸기':(279,440),'뽐내기':(338,449),'황당':(397,440)}

def card_offset(target):
 # The original proud-only reference chooses the icon/tile centre, 9px
 # below the generic face crop's top-biased point. Keep other targets intact.
 return (14,19 if target=='뽐내기' else 10)

@lru_cache(maxsize=4)
def chat_detector(root):
 from roi_runtime import RoiDetector
 return RoiDetector(Path(root)/'profiles/DKB',['체크_채팅창','버튼_채팅창_감정','버튼_X_채팅창',*NATIVE_CARDS.values()])

def navigation_open(ui):
 frame=ui.frame()
 return bool(chat_detector(str(ui.adapter.project.root)).find('체크_채팅창',frame,threshold=.95) or panel(frame))

def word_hits(frame,name):
 n=asset(name);mask=(n.min(axis=2)>150).astype('uint8')
 if mask.sum()<10:return []
 hay=(frame[108:274,731:877].min(axis=2)>150).astype('uint8')
 scores=np.nan_to_num(cv2.matchTemplate(hay,mask,cv2.TM_CCOEFF_NORMED),nan=-1)
 ys,xs=np.where(scores>=.94)
 return [(731+int(x),108+int(y),float(scores[y,x])) for y,x in zip(ys,xs)]

def gray_hits(frame,name,threshold):
 n=asset(name).min(axis=2).astype('float32')
 hay=frame[108:274,731:877].min(axis=2).astype('float32')
 scores=np.nan_to_num(cv2.matchTemplate(hay,n,cv2.TM_CCOEFF_NORMED),nan=-1)
 ys,xs=np.where(scores>=threshold)
 return [(731+int(x),108+int(y)) for y,x in zip(ys,xs)]

def angry_hits(frame):
 """The marquee moves about20px/s, so the word never keeps one binary mask.
 Gray comparison survives half-pixel phases; in the saved frames 황당 scored
 <=.919 and the quoted word sits a fixed distance before its 사용하기."""
 uses=gray_hits(frame,'word-use-angry',.90)
 return [(x,y) for x,y in gray_hits(frame,'word-angry',.95) if any(abs(uy-y)<=3 and 17<=ux-x<=21 for ux,uy in uses)]

def known_goal(frame):
 uses=sum((word_hits(frame,n) for n in ('word-use','word-use-alt','word-use-current')),[]);found=[]
 gray_uses=sum((gray_hits(frame,n,.95) for n in ('word-use','word-use-alt','word-use-current','word-use-angry')),[])
 for target,suffix in NAMES.items():
  if target=='뽐내기':
   # Reuse the existing quoted-name image across tracker rows and marquee
   # positions instead of requiring the fixed first-row title at y=128.
   hits=gray_hits(frame,'target',.95)
   if hits:found.extend((target,y) for _,y in hits)
   elif objective(frame):found.append((target,145))
   continue
  if target=='화남':
   found.extend((target,y) for _,y in angry_hits(frame))
   continue
  variants=('word-surprise','word-surprise-alt') if target=='황당' else ('word-'+suffix,)
  for x,y,score in sum((word_hits(frame,n) for n in variants),[]):
   if any(abs(uy-y)<=3 and 0<ux-x<60 for ux,uy,_ in uses):found.append((target,y))
  # Reuse the same name/suffix assets, without binarizing away fractional
  # marquee strokes. Both must score .95 and keep their observed spacing.
  for x,y in sum((gray_hits(frame,n,.95) for n in variants),[]):
   if any(abs(uy-y)<=3 and 17<=ux-x<=25 for ux,uy in gray_uses):found.append((target,y))
 names={n for n,_ in found}
 return found[0] if len(names)==1 else None

def card_hit(frame,target):
 if not panel(frame):return None
 if target not in NAMES:return None
 n=asset('card-'+NAMES[target]);area=frame[322:479,250:429]
 _,score,_,(x,y)=cv2.minMaxLoc(cv2.matchTemplate(area,n,cv2.TM_CCOEFF_NORMED))
 dx,dy=card_offset(target)
 if score>=.97:return (250+x+dx,322+y+dy)
 # The panel is translucent and the stored card holds one scroll position's
 # background. Face and label pixels stay bright over any background; in the
 # saved panels the requested card scored >=.927 and every other card <=.838.
 mask=(asset('card-clean-'+NAMES[target]).min(axis=2)>150).astype('uint8')
 scores=np.nan_to_num(cv2.matchTemplate((area.min(axis=2)>150).astype('uint8'),mask,cv2.TM_CCOEFF_NORMED),nan=-1)
 _,score,_,(x,y)=cv2.minMaxLoc(scores)
 return (250+x+dx,322+y+dy) if score>=.92 else None

def card_point(detector,frame,target):
 """The first scroll position shows 웃음 and a cut-off 화남, which only the
 program's original fixed-position images can prove. Mode never selects them."""
 point=card_hit(frame,target)
 if point or target not in NATIVE_CARDS or not panel(frame):return point
 hit=detector.find(NATIVE_CARDS[target],frame,threshold=.95)
 return (hit[0],hit[1]) if hit else None

REAL_CARDS=(398,514,290,254);REAL_COLUMNS=(449,542,635);FACE_ABOVE_WORD=45  # real pixels of the emote panel

def real_card(frame,target):
 """The card by its name under the face, as a click point. Only the panel's three columns count: scenery shows through."""
 from owner_hd import logical_of
 from owner_text import clean,read_area
 x,y,w,h=REAL_CARDS;real=np.asarray(frame.hi)
 found=[r for r in read_area(None,real[y:y+h,x:x+w],left=x,top=y,scale=3,minimum=.6)
        if clean(r['text'])==clean(target) and min(abs(r['rx']-c) for c in REAL_COLUMNS)<=20]
 if len(found)!=1:return None
 column=min(REAL_COLUMNS,key=lambda c:abs(found[0]['rx']-c))
 # Snapped so that two looks at a still card give the same point.
 return logical_of(column,round((found[0]['ry']-FACE_ABOVE_WORD)/6)*6,getattr(frame,'layout',None))

def card_at(frame,target,point):
 """Prove an already known slot, using the existing image/ink thresholds.
 A changed scroll page or resolution invalidates the hint, never the proof."""
 if getattr(frame,'hi',None) is not None:return panel(frame) and real_card(frame,target)==tuple(point)
 if getattr(frame,'shape',None)!=(479,897,3) or target not in NAMES or not panel(frame):return False
 if not isinstance(point,(tuple,list)) or len(point)!=2 or any(type(v) is not int for v in point):return False
 x,y=point;dx,dy=card_offset(target);l,t=x-dx,y-dy
 if l<250 or t<322:return False
 for prefix,threshold,ink in (('card-',.97,False),('card-clean-',.92,True)):
  needle=asset(prefix+NAMES[target]);h,w=needle.shape[:2]
  if l+w>429 or t+h>479:continue
  patch=frame[t:t+h,l:l+w]
  if ink:
   needle=(needle.min(axis=2)>150).astype('uint8');patch=(patch.min(axis=2)>150).astype('uint8')
  score=float(np.nan_to_num(cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED),nan=-1)[0,0])
  if score>=threshold:return True
 return False

def proud_face_state(frame,point):
 """Current card response, not quest completion. NCC alone also matches a
 disabled grey face. Inspect only reference-white face pixels, excluding the
 name, star and moving map. Unknown stays unknown, never authorizes a send."""
 if not card_at(frame,'뽐내기',point):return None
 if getattr(frame,'hi',None) is not None:return 'enabled'  # the reference pictures hold 897x479 faces; the 61-second limit still guards a repeat
 x,y=point;dx,dy=card_offset('뽐내기');l,t=x-dx,y-dy
 reference=asset('card-clean-proud')[:22];mask=reference.min(axis=2)>200
 patch=frame[t:t+22,l:l+reference.shape[1]]
 if mask.sum()<10 or patch.shape!=reference.shape:return None
 fraction=float((patch.min(axis=2)[mask]>150).mean())
 return 'enabled' if fraction>=.85 else ('disabled' if fraction<=.25 else None)

def observe_proud_response(ui,point):
 """Bounded result observation before menu cleanup. Never click twice or
 convert a dimmed card/dialogue into a quest-completed record."""
 last=None
 for _ in range(10):
  ui.context.wait(.12);ui.context.checkpoint();frame=ui.frame()
  now=proud_face_state(frame,point)
  if now=='disabled' and last=='disabled':return 'card_disabled'
  if not panel(frame) and getattr(ui,'execution_dialogue',lambda f:False)(frame):
   ui.context.wait(.12)
   if ui.execution_dialogue(ui.frame()):return 'npc_dialogue'
  last=now
 return 'unverified'

class CardLocator:
 """Per-worker hints, seeded by shared reference positions. No character state,
 screenshot cache, OCR, input, or durable send/completion record is stored here."""
 def __init__(self,ui,detector):
  self.detector=detector
  hints=getattr(ui,'_owner_emote_card_positions',None)
  if not isinstance(hints,dict):hints={};ui._owner_emote_card_positions=hints
  self.hints=hints
  self.atlas=Atlas(ui.adapter.project.root) if hasattr(ui,'adapter') else None
 def matches(self,frame,target,point):
  if point is None:return False
  if card_at(frame,target,point):return True
  if getattr(frame,'hi',None) is not None:return False
  if self.atlas and panel(frame) and self.atlas.matches(frame,target,point):return True
  # The original native 화남 image is a clipped first-page card, not the
  # full face/label crop. Retain its original detector and exact hit position.
  if target in NATIVE_CARDS or getattr(frame,'shape',None)!=(479,897,3):
   return card_point(self.detector,frame,target)==point
  return False
 def find(self,frame,target):
  if getattr(frame,'hi',None) is not None:return real_card(frame,target) if panel(frame) else None
  for point in (self.hints.get(target),CARD_POSITIONS.get(target)):
   if point is not None and self.matches(frame,target,point):return point
  if self.atlas and panel(frame):
   point=self.atlas.find(frame,target)
   if point is not None:self.hints[target]=point;return point
  point=card_point(self.detector,frame,target)
  if point is not None:self.hints[target]=point
  return point

def read_new_card(ui,frame,target):
 rows=ui.rows((250,334,179,140),pair_minimum=.95)
 found=[r for r in rows if r.get('score',0)>=.95 and re.sub(r'\s+','',r.get('text',''))==target]
 if len(found)!=1:return None
 box=found[0].get('bounds')
 if not box or len(box)!=4:return None
 l,t,r,b=box
 if not (250<=l<r<=429 and 340<=t<b<=474):return None
 pair=getattr(ui,'_owner_last_rows_pair',None)
 frames=pair[0] if pair else None
 # rows() captures its own newer pair. Never attach its label to the older
 # frame passed by the caller, or persist an unpaired name/slot.
 if frames and len(frames)==2:frame=frames[-1]
 bits=frame[t:b,l:r].min(axis=2)>150
 if bits.sum()<5:return None
 point=((l+r)//2,t-16)
 def same(f):return panel(f) and np.array_equal(f[t:b,l:r].min(axis=2)>150,bits)
 if not same(ui.frame()):return None
 if frames and len(frames)==2:Atlas(ui.adapter.project.root).learn(target,frames,box)
 return point,same

def read_requirement(ui):
 """Compare the interpreted requirement, not every moving tracker glyph."""
 try:
  a=ui.rows((731,143,145,120),pair=False,pair_minimum=.95)
  ui.context.wait(.12)
  b=ui.rows((731,143,145,120),pair=False,pair_minimum=.95)
 except Pending:return None
 # This nominates a read-only detail check, NEVER an emote/send permission.
 ui._owner_emote_requirement_hint=any(r.get('score',0)>=.5 and '표현' in r.get('text','') for r in a+b)
 first,second=parse_target(a,emote_context=True),parse_target(b,emote_context=True)
 if not first or first!=second:
  # No 표현 in the tracker means no emote is asked: two looks of a plain quest line differ by OCR (늪/늙, pc2 11-06)
  # and that was a warning every 10 s. It never held the quest up; the caller just returns.
  if ui._owner_emote_requirement_hint:LOG.warning('감정 요구 판독 대조 · 첫 화면=%s · 다음 화면=%s',
              [(r.get('text'),round(r.get('score',0),3)) for r in a],
              [(r.get('text'),round(r.get('score',0),3)) for r in b])
  return None
 matches=[r for r in b if parse_target([r],emote_context=True)==second]
 if len(matches)!=1:return None
 bounds=matches[0].get('bounds')
 y=bounds[1] if isinstance(bounds,(list,tuple)) and len(bounds)==4 else matches[0].get('y',145)
 return second,max(108,min(256,int(y)))

def fixed_requirement(ui,book,key):
 """Unreadable moving tracker: reuse the SAME mission-tab selection route.
 Read only the selected current leaf, close the menu and recheck the field.
 """
 if not callable(getattr(ui,'open',None)) or not callable(getattr(ui,'close_known',None)):return None
 # The original quest handler can already have opened the empty panel.
 # Reuse its existing no-send cleanup; don't silently bypass the fixed
 # detail fallback merely because that successful old navigation ran first.
 if navigation_open(ui):
  close_chat(ui,chat_detector(str(ui.adapter.project.root)))
  if closed_chat_view(ui)!='field':raise Pending('감정 상세 판독 전 빈 채팅 닫힘·필드 확인 필요')
 if not ui.normal():return None
 from owner_story_groups import Groups
 from owner_progression import state
 from owner_emote_requirements import learn_selected_requirement
 row=book.item['quests'][key];answer=None
 ui.open('sub_quest')
 try:
  if book.item.get('active')!=key:raise Pending('감정 임무 상세 확인 중 대상 변경')
  if not Groups(ui,book,state(ui.adapter).power).select(key):
   raise EmoteQuestMismatch('감정 임무 상세의 기존 묶음 미확인 · 현재 수락 목록 재선택',quest=row.get('title'))
  details=ui.rows((674,229,202,111),pair_minimum=.95)
  answer=learn_selected_requirement(ui,details,row.get('title'),emote_context=True)
 finally:ui.close_known()
 if not ui.normal():raise Pending('감정 임무 상세 확인 후 일반 필드 확인 필요')
 if answer:LOG.info('감정 요구 고정 상세 확인 · %s → %s · 공통 학습 저장',*answer)
 return answer

def title_edges(area):
 return cv2.Sobel(cv2.cvtColor(area,cv2.COLOR_RGB2GRAY),cv2.CV_32F,1,0,ksize=3)

def tracked_title_y(frame,image):
 """Exact title image on the highlighted tracker row; never a game-state proof."""
 if getattr(frame,'shape',None)!=(479,897,3):return None
 root,digit=title_edges(asset(image['root'])),title_edges(asset(image['digit']))
 scores=np.nan_to_num(cv2.matchTemplate(title_edges(frame[108:274,731:877]),root,cv2.TM_CCOEFF_NORMED),nan=-1)
 _,score,_,(x,y)=cv2.minMaxLoc(scores)
 if score<image['root_min']:return None
 x+=731+root.shape[1];y+=108;patch=frame[y:y+digit.shape[0],x:x+digit.shape[1]]
 if patch.shape[:2]!=digit.shape[:2]:return None
 if float(cv2.matchTemplate(title_edges(patch),digit,cv2.TM_CCOEFF_NORMED)[0,0])<image['digit_min']:return None
 # NCC alone accepts the real stage-5 glyph as stage 8 (.913). Require the
 # exact bright foreground too: all seven differing stage-5 pixels reject it.
 # Background/animated rim is excluded; no OCR confidence gate is relaxed.
 ink=asset(image['digit']).min(axis=2)>150
 if int(ink.sum())<5 or not np.array_equal(patch.min(axis=2)>150,ink):return None
 # Only the row the game is tracking carries the bright band left of its title.
 band=np.percentile(frame[y+1:y+16,731:738].reshape(-1,3),90,axis=0)
 return y if band[0]>=200 and band[1]>=200 else None

def bound_requirement(ui,row,catalog,first,second):
 """Bind shipped knowledge to the same highlighted title and exact stage glyph
 on two fresh frames. Never use uncertain title OCR to authorize a step."""
 if time.monotonic()<getattr(ui,'_owner_emote_bound_after',0):return None
 for name,stage,entry in catalog.packaged_for_title(row.get('title')):
  image=entry.get('title_image')
  if not image:continue
  a,b=tracked_title_y(first,image),tracked_title_y(second,image)
  if a is None or b is None or abs(a-b)>3 or not target_zone(first) or not target_zone(second):continue
  return name,entry['emote'],b+22
 # Known quest names without dedicated title PNGs use the SAME existing
 # high-confidence title reader. Requirement OCR is unnecessary after the
 # current highlighted quest AND stage agree on two independently read frames.
 entries={name:entry for name,stage,entry in catalog.known_for_title(row.get('title'))}
 if not entries or not target_zone(first) or not target_zone(second):return None
 try:
  a=ui.rows((731,108,145,166),pair=False,pair_minimum=.95)
  fa=getattr(ui,'last_text_frame',first)
  ui.context.wait(.12)
  b=ui.rows((731,108,145,166),pair=False,pair_minimum=.95)
  fb=getattr(ui,'last_text_frame',second)
 except Pending:return None
 def candidates(rows,frame):
  result={}
  if getattr(frame,'shape',None)!=(479,897,3) or not target_zone(frame):return result
  for item in rows:
   identity=quest_id([item]);box=item.get('bounds')
   if identity not in entries or not isinstance(box,(list,tuple)) or len(box)!=4:continue
   y=int(box[1])
   if not 108<=y<=249:continue
   band=np.percentile(frame[y+1:y+16,731:738].reshape(-1,3),90,axis=0)
   if band[0]>=200 and band[1]>=200:result[identity]=y
  return result
 left,right=candidates(a,fa),candidates(b,fb)
 same=[name for name in left.keys()&right.keys() if abs(left[name]-right[name])<=3]
 if len(same)==1:
  name=same[0];return name,entries[name]['emote'],right[name]+22
 return None

def require_same_quest(ui,row,catalog,first,second,y,target):
 """Raise before any input or record when the game positively tracks another
 quest. An unreadable title is not proof, and stays the caller's fresh reading."""
 title=row.get('title')
 # The existing proud-only path already proves this exact quest+step and
 # quoted objective. Do not charge that input to an unrelated selected root
 # just because its tiny title OCR is uncertain (the actual failed run did).
 if target=='뽐내기' and objective(first) and objective(second) and title_root(title) not in ('산길의호환','외전산길의호환','외전1산길의호환'):
  raise EmoteQuestMismatch('뽐내기 임무와 선택 장부 불일치',quest=title,hud='외전|산길의호환|10',target=target)
 for name,entry in catalog.packaged_images():
  if name.split('|')[1] in title_root(title):continue
  if tracked_title_y(first,entry['title_image']) is not None and tracked_title_y(second,entry['title_image']) is not None:
   raise EmoteQuestMismatch('감정 임무 장부와 게임 추적 임무 불일치',quest=title,hud=name,target=target)
 box=(731,max(105,y-25),145,21)
 try:
  a=[r for r in ui.rows(box,pair=False,pair_minimum=.95) if r.get('score',0)>=.95]
  ui.context.wait(.12)
  b=[r for r in ui.rows(box,pair=False,pair_minimum=.95) if r.get('score',0)>=.95]
 except Pending:return
 def differs(rows):return any(title_disagrees(r.get('text',''),title) for r in rows) and not any(not title_disagrees(r.get('text',''),title) and len(re.sub(r'[^가-힣]','',r.get('text','')))>=4 for r in rows)
 if differs(a) and differs(b):
  hud=next((r.get('text') for r in b if title_disagrees(r.get('text',''),title)),None)
  raise EmoteQuestMismatch('감정 임무 장부와 게임 추적 임무 불일치',quest=title,hud=hud,target=target)

def run(ui,book,key):
 ui.context.checkpoint()
 ui._owner_emote_cooldown_until=0.
 require_cleanup_closed(ui)
 row=book.item.get('quests',{}).get(key)
 if not row:return False
 catalog=Catalog(ui.adapter.project.root)
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 character=state(ui.adapter).character;scope=configured_identity(ui.adapter.project.root)
 def guard():
  ui.context.checkpoint()
  return bool(character and state(ui.adapter).character==character and configured_identity(ui.adapter.project.root)==scope
              and book.item.get('active')==key and book.item['quests'].get(key) is row)
 if not guard():raise Pending('감정 임무 캐릭터 변경')
 # The game can leave/open its old chat UI after acknowledging the emote
 # with NPC dialogue. That is cleanup, not another current emote request.
 if row.get('emote_attempt',{}).get('next_view') in ('field','dialogue'):
  ui.adapter._owner_emote_request_consumed=key
 if getattr(ui.adapter,'_owner_emote_request_consumed',None)==key:
  ui.adapter._owner_emote_requested=None
  if navigation_open(ui):
   close_chat(ui,chat_detector(str(ui.adapter.project.root)))
   if closed_chat_view(ui) is None:raise Pending('감정 응답 후 빈 채팅 정리 확인 필요')
   LOG.info('감정 응답 후 다시 열린 빈 채팅 정리 · 기존 다음 단계 진행 유지')
 rate=Rate(ui.adapter.project.root,scope,character)
 remaining=rate.remaining()
 if remaining:
  ui._owner_emote_cooldown_until=time.monotonic()+remaining
  if getattr(ui.adapter,'_owner_emote_requested',None)==key and time.monotonic()-getattr(ui,'_owner_emote_wait_note',-1e30)>15:
   LOG.info('감정표현 재전송 제한 · %.0f초 후 요구 내용 재확인',remaining);ui._owner_emote_wait_note=time.monotonic()
  return False
 detector=chat_detector(str(ui.adapter.project.root))
 def chat(f):return bool(detector.find('체크_채팅창',f,threshold=.95))
 def ready(f):return bool((ui.normal_frame(f) or chat(f)) and target_zone(f))
 observed=None;observed_at=0.;prebound=None
 if getattr(ui.adapter,'_owner_emote_requested',None)!=key:
  # Arrival at a quest's already occupied trigger can leave the native
  # state at quest_active instead of ever calling handle_sub_chat.
  # Only an explicit paired current requirement can start this path.
  first=ui.frame()
  if not ready(first):return False
  seen=known_goal(first);ui.context.wait(.12);second=ui.frame()
  other=known_goal(second)
  prebound=bound_requirement(ui,row,catalog,first,second)
  if prebound:
   _,target,y=prebound;observed=(target,y);observed_at=time.monotonic()
   ui.adapter._owner_emote_requested=key
  elif seen and other and seen[0]==other[0]:
   observed=other;observed_at=time.monotonic()
   ui.adapter._owner_emote_requested=key
   LOG.info('현재 필드 감정 임무 요구 확인 · 기존 채팅 상태 전환 대기 없이 처리')
  else:
   if time.monotonic()<getattr(ui,'_owner_emote_probe_after',0):return False
   ui._owner_emote_probe_after=time.monotonic()+10
   if not target_zone(second):return False
   observed=read_requirement(ui)
   if not observed:
    if not getattr(ui,'_owner_emote_requirement_hint',False):return False
    if not guard():raise Pending('감정 상세 확인 전 캐릭터·임무 변경')
    fixed=fixed_requirement(ui,book,key)
    if not fixed:return False
    identity,target=fixed;prebound=(identity,target,145);observed=(target,145)
   observed_at=time.monotonic()
   ui.adapter._owner_emote_requested=key
 def detect(f):return known_goal(f) or catalog.visual_goal(f)
 first=ui.frame();seen=detect(first)
 if not ready(first):return False
 ui.context.wait(.12);second=ui.frame();seen2=detect(second)
 bound=prebound or bound_requirement(ui,row,catalog,first,second)
 if bound and seen and seen2 and seen[0]==seen2[0] and abs(seen[1]-bound[2])<=3 and abs(seen2[1]-bound[2])<=3 and seen2[0]!=bound[1]:
  catalog.invalidate(bound[0],seen2[0])
  LOG.warning('감정 임무 저장 지식과 현재 화면 불일치 · %s · 입력 없음',bound[0])
  return False
 recent=observed and time.monotonic()-observed_at<20
 # Another accepted quest's row must not replace the requirement just confirmed.
 if bound:
  _,target,y=bound
  LOG.info('감정 임무 저장 위치 경로 · %s → %s · 요구 문구 재판독 생략',bound[0],target)
 elif seen and seen2 and seen[0]==seen2[0] and not (recent and abs(seen2[1]-observed[1])>3):target,y=seen2
 elif recent:
  if any(v and abs(v[1]-observed[1])<=3 and v[0]!=observed[0] for v in (seen,seen2)):return False
  target,y=observed
 else:
  # OCR backoff must not also hide short visible phases of an already
  # known marquee label. Keep the inexpensive template pair available.
  if time.monotonic()<getattr(ui,'_owner_emote_unreadable_until',0):return False
  observed=read_requirement(ui)
  if not observed:
   fixed=fixed_requirement(ui,book,key)
   if fixed:
    identity,target=fixed;y=145;bound=(identity,target,y)
   else:
    if not getattr(ui,'_owner_emote_unreadable_note',False):LOG.warning('감정 임무 요구 이름 판독 보류 · 원본 고정 항목 입력 없음');ui._owner_emote_unreadable_note=True
    ui._owner_emote_unreadable_until=time.monotonic()+10
    return False
  else:target,y=observed
 if bound and abs(bound[2]-y)<=3 and bound[1]!=target:
  catalog.invalidate(bound[0],target)
  LOG.warning('감정 임무 저장 지식과 현재 화면 불일치 · %s · 이 PC에서 해당 항목 사용 중지',bound[0])
  return False
 if bound:identity=bound[0]
 else:
  require_same_quest(ui,row,catalog,first,second,y,target)
  try:identity=quest_id(ui.rows((731,max(105,y-23),145,21),pair_minimum=.95))
  except Pending:identity=None
 if identity:
  shipped=catalog.packaged(identity)
  if shipped and shipped.get('emote')!=target:
   catalog.invalidate(identity,target)
   LOG.warning('감정 임무 저장 지식과 현재 화면 불일치 · %s · 이 PC에서 해당 항목 사용 중지',identity)
   return False
  prior=catalog.get(identity)
  if prior and prior!=target:LOG.info('감정 임무 요구 변경 확인 · 저장값 대신 현재 화면 사용')
  if prior==target:target=prior
  latest=ui.frame();visual=latest[y:y+18,731:877].copy() if getattr(latest,'shape',None)==(479,897,3) else None
  catalog.learn(identity,target,visual)
 request=identity or re.sub(r'\s+','',row['title'])+'|'+target
 if rate.attempts(request)>=3:raise Pending('감정표현 3회 시도 후 미완료 · 진단 확인 필요')
 latched_until=time.monotonic()+20
 bound_image=None
 if bound:
  entry=catalog.packaged(bound[0]);image=entry.get('title_image') if entry else None
  # A fixed-detail or paired-title proof must not be replaced afterward by
  # an optional title PNG which did NOT match this observation. Keep the
  # original exact-image guard only when it was actually the binding proof.
  if image and tracked_title_y(first,image) is not None and tracked_title_y(second,image) is not None:bound_image=image
 def goal(f):
  if bound and abs(bound[2]-y)<=3:
   return bool(target_zone(f) and (tracked_title_y(f,bound_image) is not None if bound_image else time.monotonic()<latched_until))
  v=detect(f)
  if v and abs(v[1]-y)<=3:return v[0]==target
  # A second accepted quest has its own tracker row and marquee. Its
  # visible emotion name must not cancel the confirmed current row.
  # The tracker text scrolls horizontally. The paired request is held only
  # while this worker owns the same quest, before any emote input, at its zone.
  return bool(time.monotonic()<latched_until and target_zone(f))
 opened=False
 try:
  if paired(ui,lambda f:goal(f) and target_zone(f) and chat(f)):
   if not paired(ui,empty_chat):raise Pending('감정 입력 전 열린 채팅창 내용 확인 필요')
   opened=True;save_navigation(ui.adapter.project.root,scope,'opened')
  else:
   if not paired(ui,lambda f:goal(f) and target_zone(f) and not chat(f)):return False
   save_navigation(ui.adapter.project.root,scope,'opening')
   opened=True
   ui.click(114,447,lambda f:guard() and ui.normal_frame(f) and goal(f) and target_zone(f) and not chat(f))
   ui.wait(chat,seconds=3);opened=True;save_navigation(ui.adapter.project.root,scope,'opened')
   # The chat title can appear before its input box has finished drawing.
   try:ui.wait(empty_chat,seconds=1.5)
   except Pending:pass
  if not paired(ui,empty_chat):raise Pending('감정 입력 전 빈 채팅창 확인 필요')
  if not paired(ui,panel):
   hit=detector.find('버튼_채팅창_감정',ui.frame(),threshold=.95)
   if not hit:raise Pending('감정 목록 버튼 확인 필요')
   ui.click(hit[0],hit[1],lambda f:guard() and chat(f) and goal(f));ui.wait(panel,seconds=3)
  locator=CardLocator(ui,detector)
  for direction in search_order(target):
   for _ in range(14):
    a=ui.frame();ui.context.wait(.12);b=ui.frame();ha,hb=locator.find(a,target),locator.find(b,target)
    verify=lambda f:locator.matches(f,target,hb)
    if target not in NAMES and not hb and target not in locator.atlas.entries():
     discovered=read_new_card(ui,b,target)
     if discovered:hb,verify=discovered;ha=hb
    if ha and ha==hb and goal(a) and goal(b):
     if not guard():raise Pending('감정 카드 입력 전 캐릭터·임무 변경')
     if target=='뽐내기' and getattr(b,'shape',None)==(479,897,3):
      if proud_face_state(a,ha)!='enabled' or proud_face_state(b,hb)!='enabled':
       raise Pending('뽐내기 카드 활성 상태 확인 필요 · 입력 없음')
     rate.reserve(request,target)
     row['emote_attempt']={'name':target,'phase':'input_intent_unverified','at':time.time()};book.commit()
     ui.click(*hb,lambda f:guard() and panel(f) and goal(f) and verify(f) and
              (target!='뽐내기' or getattr(f,'shape',None)!=(479,897,3) or proud_face_state(f,hb)=='enabled'))
     if target=='뽐내기' and getattr(b,'shape',None)==(479,897,3):
      response=observe_proud_response(ui,hb)
      row['emote_attempt']['ui_response']=response;book.commit()
      LOG.info('뽐내기 입력 반응 · %s · 퀘스트 완료와 별개',response)
     ui.adapter._owner_emote_requested=None
     ui.adapter._owner_emote_request_consumed=key
     LOG.info('요구 감정표현 %s 입력 시도 · 완료는 별도 확인 · 재전송61초 제한',target)
     return True
    # One notch keeps adjacent rows overlapping. Twelve notches could jump
    # over the requested middle cards and spent seconds verifying each jump.
    chosen=locator.atlas.direction(b,target) if locator.atlas else None
    ui.wheel(chosen or direction,1,at=(338,390),verify_cursor=True,scene=lambda f:guard() and panel(f) and goal(f))
  raise Pending('요구 감정 카드 확인 실패 · 다른 항목 입력 없음')
 finally:
  if opened:
   # Keep the original sent-intent/result or exception. Cleanup failure is
   # durable and blocks the caller before ANY next native input; it is not
   # evidence the send failed, and must never cause a second card click.
   primary=sys.exc_info()[1]
   try:
    ui.context.checkpoint();close_chat(ui,detector)
    view=closed_chat_view(ui)
    if view is None:raise Pending('감정 메뉴 종료 후 필드·기존 NPC 대화 확인 필요')
    save_navigation(ui.adapter.project.root,scope,'closed',next_view=view,field_verified=view=='field')
    if view=='dialogue':LOG.info('감정 메뉴 닫힘 · NPC 대화 전환 확인 · 기존 대화 처리로 계속')
    ui._owner_emote_cleanup_pending=False
    if row.get('emote_attempt',{}).get('phase')=='input_intent_unverified':
     # This ends the attempted input request only. It never marks the quest/chapter done
     # or clears the durable 61-second rate/attempt record. A later explicit
     # requirement can still use the independent field recognition path.
     row['emote_attempt']['next_view']=view;book.commit()
     ui.adapter._owner_emote_request_consumed=key
     ui.adapter._owner_emote_requested=None
   except BaseException as cleanup:
    ui._owner_emote_cleanup_pending=True
    try:save_navigation(ui.adapter.project.root,scope,'cleanup_pending',
      quest=key,attempt=row.get('emote_attempt'),cleanup_error=str(cleanup),
      primary_error=str(primary) if primary else None)
    except Exception:
     LOG.exception('감정 메뉴 정리 보류 기록 저장 실패')
    LOG.warning('감정 입력·원래 결과 유지 · 채팅 정리 확인 전 다음 입력 차단 · %s',cleanup)
    # Cancellation/control-flow must propagate immediately, including when
    # received during cleanup. Ordinary cleanup errors cannot mask primary.
    if isinstance(cleanup,Cancelled) or not isinstance(cleanup,Exception):raise
