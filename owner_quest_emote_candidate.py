"""Observed 산길의 호환 10 뽐내기 operation; no inferred completion."""
from functools import lru_cache
from pathlib import Path
import json,logging,time
import cv2,numpy as np
from PIL import Image
from owner_skill_goal import Pending
from biol_base.session import Cancelled
from owner_story_groups import _verified_mountain_root
LOG=logging.getLogger('project_gui.DKB')
ASSETS=Path(__file__).parent/'assets/quest-emote'

@lru_cache(maxsize=24)
def asset(name):return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

def locate(frame,name,region,threshold):
 if getattr(frame,'shape',None)!=(479,897,3):return None
 l,t,r,b=region;needle=asset(name);area=frame[t:b,l:r]
 if area.shape[0]<needle.shape[0] or area.shape[1]<needle.shape[1]:return None
 scores=np.nan_to_num(cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED),nan=-1)
 _,score,_,(x,y)=cv2.minMaxLoc(scores)
 if score<threshold:return None
 return (l+x+needle.shape[1]//2,t+y+needle.shape[0]//2)

def tracker(frame):
 """Exact observed quest title including step 10, contrast independent."""
 if getattr(frame,'shape',None)!=(479,897,3):return False
 def edge(a):return cv2.Sobel(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY),cv2.CV_32F,1,0,ksize=3)
 hay=edge(frame[124:144,735:850]);needle=edge(asset('tracker'))
 result=np.nan_to_num(cv2.matchTemplate(hay,needle,cv2.TM_CCOEFF_NORMED),nan=-1)
 return float(cv2.minMaxLoc(result)[1])>=.90

def objective(frame,*,menu=False):
 # The goal scrolls behind the icon. Require the explicit known text before
 # opening the menu; afterward the independently identified step 10 remains.
 return bool(tracker(frame) and (menu or locate(frame,'target',(735,145,835,164),.88)))

def target_zone(frame):
 """Visible yellow ground ring near the player, never map/position guess."""
 if getattr(frame,'shape',None)!=(479,897,3):return False
 hsv=cv2.cvtColor(frame[195:315,345:555],cv2.COLOR_RGB2HSV)
 mask=((hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>=60)&(hsv[:,:,2]>=160)).astype('uint8')
 # The avatar and the emotion panel can occlude the left half of the ring.
 # Before opening chat require both halves; with the known panel open the
 # uncovered right rim must still have substantial bright yellow pixels.
 right=int(mask[:,150:210].sum());left=int(mask[:,:50].sum())
 compact=((hsv[:,60:150,0]>=15)&(hsv[:,60:150,0]<=40)&(hsv[:,60:150,1]>=60)&(hsv[:,60:150,2]>=160))
 return (right>=400 and (left>=400 or panel(frame))) or (int(compact[:,:40].sum())>=80 and int(compact[:,50:].sum())>=80 and int(compact.sum())>=500)

REAL_PANEL_TITLE=(400,486,240,28);REAL_PANEL_CLOSE=(672,500);REAL_CHAT_CLOSE=(372,28);REAL_INPUT=(90,722,255,26)  # real pixels
def panel(frame):
 real=getattr(frame,'hi',None)
 if real is not None:
  from owner_text import clean,read_area
  x,y,w,h=REAL_PANEL_TITLE
  return any(clean(row['text'])=='감정표현' for row in read_area(None,np.asarray(real)[y:y+h,x:x+w],minimum=.5))
 return bool(locate(frame,'panel',(300,300,390,320),.97))
def card(frame):return locate(frame,'card',(250,319,429,479),.985) if panel(frame) else None
def empty_chat(frame):
 """Observed placeholder and entire remaining input area, not OCR inference."""
 if getattr(frame,'shape',None)!=(479,897,3):return False
 real=getattr(frame,'hi',None)
 if real is not None:
  # Typed text is bright across the box. An empty one shows at most its caret, one column wide.
  x,y,w,h=REAL_INPUT
  if int((np.asarray(real)[y:y+h,x:x+w].min(axis=2)>150).any(axis=0).sum())<=3:return True
  # At 1366 the placeholder 채팅을 입력해주세요. is drawn bright too (pc1 11-06 13:16: 108 bright columns on an empty box),
  # so it is read: the placeholder alone is empty, anything else is typed text.
  from owner_text import clean,read_area
  words=''.join(clean(row['text']) for row in read_area(None,np.asarray(real)[y:y+h,x:x+w],scale=2,minimum=.6))
  return words.startswith('채팅을입력') and len(words)<=len('채팅을입력해주세요')+1
 patch=frame[448:468,55:214]
 for name in ('placeholder','placeholder-alt'):
  reference=asset(name)
  if patch.shape==reference.shape and int(np.abs(patch.astype('int16')-reference.astype('int16')).max())<=2:return True
  if patch.shape==reference.shape:
   ink=reference.min(axis=2)>150
   if ink.sum()>=20 and np.array_equal(patch.min(axis=2)>150,ink) and int(np.abs(patch.astype('int16')-reference.astype('int16'))[ink].max())<=2:return True
 # An unfocused empty input can hide the placeholder. Typed text is bright;
 # accept only an entirely dark input rectangle, never erase/submit it.
 return bool(patch.size and int(patch.max())<110)

def suppress_native_chat(book,key,frame):
 row=book.item['quests'].get(key) if book else None
 return bool(row and _verified_mountain_root(row) and objective(frame,menu=True))

def paired(ui,predicate):
 a=ui.frame();ui.context.wait(.12);ui.context.checkpoint();b=ui.frame()
 return bool(predicate(a) and predicate(b))

def closed_chat_view(ui):
 """After confirmed chat closure, a native dialogue is a valid next view.

 This does not assert field readiness or quest completion, and sends no input.
 Unknown/loading screens remain unresolved.
 """
 if ui.normal():return 'field'
 dialogue=getattr(ui,'execution_dialogue_pair',None)
 if callable(dialogue) and dialogue():return 'dialogue'
 return None

def _marker_path(root):return Path(root)/'settings/owner-emote-navigation.json'

def save_navigation(root,scope,phase,**details):
 from owner_timetable import save
 save(_marker_path(root),{'version':1,'scope':scope,'phase':phase,'at':time.time(),**details})

class EmoteCleanupPending(Pending):pass

def require_cleanup_closed(ui):
 """Gate the next worker input, without replaying the emotion card."""
 volatile=bool(getattr(ui,'_owner_emote_cleanup_pending',False))
 try:record=json.loads(_marker_path(ui.adapter.project.root).read_text(encoding='utf-8-sig'))
 except FileNotFoundError:
  if volatile:raise EmoteCleanupPending('감정 메뉴 정리 기록 저장 미확인 · 다음 입력 보류')
  return
 except (ValueError,OSError) as exc:raise EmoteCleanupPending('감정 메뉴 정리 기록 확인 필요') from exc
 if not isinstance(record,dict):raise EmoteCleanupPending('감정 메뉴 정리 기록 형식 확인 필요')
 if record.get('phase')!='cleanup_pending':
  if volatile:raise EmoteCleanupPending('감정 메뉴 정리 상태 저장 미확인 · 다음 입력 보류')
  return
 ui.context.checkpoint()
 try:normalize_after_stop(ui.adapter,ui.context,ui.inputs)
 except Cancelled:raise
 except Exception as exc:raise EmoteCleanupPending('감정 입력 결과 보존 · 채팅 메뉴 정리 확인 전 다음 입력 보류') from exc
 try:latest=json.loads(_marker_path(ui.adapter.project.root).read_text(encoding='utf-8-sig'))
 except (ValueError,OSError) as exc:raise EmoteCleanupPending('감정 메뉴 정리 결과 확인 필요') from exc
 if latest.get('phase')!='closed':raise EmoteCleanupPending('감정 입력 결과 보존 · 채팅 메뉴 정리 미확인')
 ui._owner_emote_cleanup_pending=False

def close_chat(ui,detector):
 def chat(f):return bool(detector.find('체크_채팅창',f,threshold=.95))
 # The opened emotion panel can temporarily hide the placeholder. Its own X
 # neither sends nor clears a message; check the input only after it closes.
 if paired(ui,lambda f:chat(f) and panel(f)):
  frame=ui.frame();x,y=(419,312)
  if getattr(frame,'hi',None) is not None:
   from owner_hd import logical_of
   x,y=logical_of(*REAL_PANEL_CLOSE,getattr(frame,'layout',None))
  ui.click(x,y,lambda f:chat(f) and panel(f));ui.context.wait(.5)
 if paired(ui,chat) and not paired(ui,empty_chat):
  raise Pending('채팅 입력 내용 확인 필요 · 닫기 보류')
 if paired(ui,chat):
  frame=ui.frame();hit=detector.find('버튼_X_채팅창',frame,threshold=.95)
  if not hit:
   # Its picture does not survive 1366x768. With the chat proved open and empty above, its X stands at this real place.
   if getattr(frame,'hi',None) is not None:
    from owner_hd import logical_of
    x,y=logical_of(*REAL_CHAT_CLOSE,getattr(frame,'layout',None));hit=(x,y,(x-7,y-7,x+8,y+8))
  if not hit:raise RuntimeError('감정 처리 후 채팅 닫기 확인 필요')
  l,t,r,b=hit[2];ui.click((l+r)//2,(t+b)//2,lambda f:chat(f) and empty_chat(f))
 if not paired(ui,lambda f:not chat(f) and not panel(f)):
  raise RuntimeError('감정 처리 후 채팅 종료 확인 필요')

def normalize_after_stop(adapter,context,inputs,*,frames=None,field_confirmed=False):
 """On requested start, close positively empty known chat; never send text."""
 path=_marker_path(adapter.project.root)
 try:record=json.loads(path.read_text(encoding='utf-8-sig'))
 except FileNotFoundError:record=None
 except (ValueError,OSError) as exc:raise Pending('이전 감정 메뉴 기록 확인 필요') from exc
 if record is not None and not isinstance(record,dict):raise Pending('이전 감정 메뉴 기록 확인 필요')
 tracked=bool(record and record.get('version')==1 and record.get('phase') in ('opening','opened','cleanup_pending'))
 from roi_runtime import RoiDetector
 detector=RoiDetector(Path(adapter.project.root)/'profiles/DKB',['체크_채팅창','버튼_X_채팅창'])
 def chat(f):return bool(detector.find('체크_채팅창',f,threshold=.95))
 ui=None
 if frames is None:
  from owner_mission_ui import MissionUI
  ui=MissionUI(adapter,context,inputs);a=ui.frame();context.wait(.12);b=ui.frame()
 else:
  if not isinstance(frames,(tuple,list)) or len(frames)!=2 or any(not isinstance(f,np.ndarray) or f.shape!=(479,897,3) or f.dtype!=np.uint8 for f in frames):
   raise Pending('시작 화면 두 장의 형식 확인 필요')
  a,b=frames
 if not chat(a) and not panel(a) and not chat(b) and not panel(b):
  # Let native startup handle special/unknown screens unmodified.
  if tracked and (field_confirmed or (ui is not None and ui.normal())):
   from owner_hunt_rules_candidate import configured_identity
   if configured_identity(adapter.project.root)!=record.get('scope'):raise Pending('이전 감정 메뉴 캐릭터 설정 변경')
   save_navigation(adapter.project.root,record['scope'],'closed');return True
  return False
 if not chat(a) or not chat(b):return False
 from owner_hunt_rules_candidate import configured_identity
 if tracked and configured_identity(adapter.project.root)!=record.get('scope'):raise Pending('이전 감정 메뉴 캐릭터 설정 변경')
 if ui is None:
  from owner_mission_ui import MissionUI
  ui=MissionUI(adapter,context,inputs)
 if not paired(ui,chat):raise Pending('시작 화면의 채팅창 상태 확인 필요')
 # Caller explicitly started automation; this is a known empty chat, not a
 # claim that it was opened by us. Typed/unknown input must never be closed.
 context.checkpoint();close_chat(ui,detector)
 if not ui.normal():raise Pending('감정 메뉴 복구 후 일반 필드 확인 필요')
 if tracked:save_navigation(adapter.project.root,record['scope'],'closed')
 LOG.info('시작 요청 · 빈 채팅 및 감정 메뉴 닫힘 · 일반 필드 확인 · 소유권 추정 없음')
 return True

def wheel(ui,guard):
 if not paired(ui,lambda f:panel(f) and objective(f,menu=True) and target_zone(f)) or guard() is not True:raise Pending('감정 목록 또는 대상 임무 확인 필요')
 ui.wheel(-1,1,at=(338,390),verify_cursor=True,
          scene=lambda f:guard() is True and panel(f) and objective(f,menu=True) and target_zone(f))


def run(ui,book,key):
 from owner_emote_dispatch import run as dispatch
 from owner_schedule_priority import LOCAL as priority
 previous=getattr(priority,'feature',None);priority.feature='감정표현'
 try:return dispatch(ui,book,key)
 finally:priority.feature=previous
