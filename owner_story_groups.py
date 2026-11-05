"""Story groups: dots prove accepted roots; the game counter owns the20 limit."""
from pathlib import Path
from functools import lru_cache
import copy,hashlib,json,logging,re,time
from owner_skill_goal import Pending
from owner_skill_ui import quest_screen,selected_quest_box,clean
from owner_mission_policy import hangul
LOG=logging.getLogger('project_gui.DKB');ASSETS=Path(__file__).parent/'assets/mission-groups'
_LOCATE_BACKOFF={}
class StorySelectionPending(Pending):pass
def _backoff_scope(book):
 """Per-character scope. QuestBook.path is one shared journal, so the path
 alone would leak a skip between characters; the per-character item dict is
 the real owner of this state."""
 character=next((k for k,v in getattr(book,'data',{}).get('characters',{}).items() if v is getattr(book,'item',None)),None)
 return (str(getattr(book,'path','')),character if character is not None else id(getattr(book,'item',None)))
def locate_backoff(book,key,seconds=5):
 """A root whose row is not in the current view is skipped briefly so the
 next candidate gets a turn. Cache only: never a completion, death or hold."""
 token=(_backoff_scope(book),key);now=time.monotonic()
 for seen,at in tuple(_LOCATE_BACKOFF.items()):
  if now-at>=seconds:_LOCATE_BACKOFF.pop(seen,None)
 return token in _LOCATE_BACKOFF
def mark_locate_backoff(book,key):_LOCATE_BACKOFF[((_backoff_scope(book)),key)]=time.monotonic()

def selection_snapshot(ui,frame,key):
 adapter=getattr(ui,'adapter',None);now=time.monotonic()
 if adapter is None or now-getattr(ui,'_owner_selection_snapshot_at',-1e30)<60:return
 try:
  from PIL import Image
  from datetime import datetime,timezone
  folder=Path(adapter.project.root)/'logs/quest-incidents'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-selection')
  folder.mkdir(parents=True,exist_ok=True);Image.fromarray(frame).save(folder/'screen.png')
  (folder/'selection.json').write_text(json.dumps({'quest':key,'stage':'visible_root_handoff','confirmed_complete':False},ensure_ascii=False),encoding='utf-8')
  ui._owner_selection_snapshot_at=now
 except (OSError,ValueError,TypeError):LOG.warning('서사 선택 진단 저장 실패 · 임무 기록 유지')

@lru_cache(maxsize=24)
def _asset(name,stamp):
 from PIL import Image
 import numpy as np
 return np.asarray(Image.open(ASSETS/(name+'.png')).convert('RGB'))

def asset(name):return _asset(name,(ASSETS/(name+'.png')).stat().st_mtime_ns)

def find(frame,name,box,threshold=.94,bright=True):
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return None
 x,y,w,h=box;needle=asset(name);part=frame[y:y+h,x:x+w]
 if part.shape[0]<needle.shape[0] or part.shape[1]<needle.shape[1]:return None
 _,score,_,p=cv2.minMaxLoc(np.nan_to_num(cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED),nan=-1))
 if score<threshold:return None
 l,t=x+p[0],y+p[1];hh,ww=needle.shape[:2];patch=frame[t:t+hh,l:l+ww];white=needle.min(axis=2)>170
 if bright and (white.sum()<8 or float((patch.min(axis=2)[white]>150).mean())<.85):return None
 return l+ww//2,t+hh//2,(l,t,l+ww,t+hh),float(score)

def group_rows(frame):
 from owner_mission_ui import markers
 import cv2,numpy as np
 rows=[{'y':y,'open':False} for y in markers(frame,'group-closed',x=20,width=18)]
 needle=asset('group-up');values=cv2.matchTemplate(frame[96:438,20:38],needle,cv2.TM_CCOEFF_NORMED)
 for y,x in zip(*np.where(np.nan_to_num(values,nan=-1)>=.90)):
  cy=96+int(y)+needle.shape[0]//2
  if all(abs(cy-r['y'])>15 for r in rows):rows.append({'y':cy,'open':True})
 return sorted((r for r in rows if 108<=r['y']<=426),key=lambda r:r['y'])

def dots(frame,y):return bool(find(frame,'group-dots',(620,max(96,y-17),35,34),.93))

def completed_root(frame,y):
 # Native fractional scroll raster variants of the same grey completion
 # stamp. Keep the positive template threshold; suitability alone never
 # proves an uncompleted quest (completed rows still show the green label).
 return any(find(frame,name,(621,max(96,y-17),33,34),.94,bright=False)
            for name in ('group-completed',*(f'group-completed-native{i}' for i in range(1,5))))

def row_tag(frame,y):
 """적합 green, 도전 orange, 위험 red: the game colours the power and its tag.

 The tag's glyph shifts with the width of the power number, so a fixed image
 scored real 적합 rows as low as .84 while 도전 scored in the same range.
 """
 import cv2
 if getattr(frame,'shape',None)!=(479,897,3):return None
 part=frame[max(96,y-12):min(438,y+13),512:596]
 hsv=cv2.cvtColor(part,cv2.COLOR_RGB2HSV);h,s,v=hsv[:,:,0],hsv[:,:,1],hsv[:,:,2]
 strong=(s>50)&(v>70)
 counts={'적합':int((strong&(h>=35)&(h<=85)).sum()),'도전':int((strong&(h>=8)&(h<=24)).sum()),
         '위험':int((strong&((h<8)|(h>=170))).sum())}
 name,count=max(counts.items(),key=lambda item:item[1])
 # One clear colour only. An unclear row stays unknown, never suitable.
 return name if count>=60 and count>=3*(sum(counts.values())-count) else None

def suitable(frame,y):return row_tag(frame,y)=='적합'

def glyph(frame,y):
 import cv2,numpy as np
 patch=frame[max(96,y-11):min(438,y+12),70:490];mask=(patch.min(axis=2)>(110 if completed_root(frame,y) else 170)).astype('uint8')
 ys,xs=np.where(mask)
 if len(xs)<20:return None
 left,right=int(xs.min()),int(xs.max())+1;top,bottom=int(ys.min()),int(ys.max())+1
 normalized=cv2.resize(mask[top:bottom,left:right],(192,20),interpolation=cv2.INTER_NEAREST)
 return {'bits':np.packbits(normalized).tobytes().hex(),'width':right-left}

def likeness(a,b):
 import numpy as np
 if not a or not b or not .80<=a['width']/max(1,b['width'])<=1.25:return 0.
 try:x=np.unpackbits(np.frombuffer(bytes.fromhex(a['bits']),dtype='uint8'));y=np.unpackbits(np.frombuffer(bytes.fromhex(b['bits']),dtype='uint8'))
 except (KeyError,ValueError):return 0.
 if x.shape!=y.shape:return 0.
 x=x.reshape(20,192);y=y.reshape(20,192);best=0.
 # Fractional scroll raster positions shift thin title glyphs. Match small
 # translations rather than treating the same root as another quest.
 for dy in (-2,-1,0,1,2):
  for dx in (-2,0,2):
   xx=x[max(0,dy):min(20,20+dy),max(0,dx):min(192,192+dx)]
   yy=y[max(0,-dy):min(20,20-dy),max(0,-dx):min(192,192-dx)]
   best=max(best,float(2*(xx&yy).sum()/max(1,int(xx.sum()+yy.sum()))))
 return best

def row_words(ui,frame):
 """The whole list's words from real pixels, read once per picture. None on a frame with no real pixels."""
 adapter=getattr(ui,'adapter',None)
 if adapter is None or getattr(frame,'hi',None) is None:return None
 from owner_text import read,word_box
 return read(adapter.project.root,frame,word_box((70,96,430,342)),scale=2)

def row_title(words,y):
 """The title on the row at this logical y; the column beside it can fall inside the read area."""
 def titled(text):
  # Real rows also hold ※37,400 적합 beside them and a Q or ! mark before them. A lone digit can be the step number.
  return '※' not in text and not re.fullmatch(r'[\d,.]*(적합|도전|위험)',text) and bool(hangul(text) or re.fullmatch(r'\d{1,2}',text))
 parts=sorted((r for r in words if abs(r['y']-y)<=10 and r['score']>=.60 and titled(clean(r['text']))),key=lambda r:r['rx'])
 text=' '.join(r['text'].strip() for r in parts)
 return text if len(hangul(text))>=3 else None

def same_root(a,b):
 from difflib import SequenceMatcher
 x,y=hangul(a),hangul(b)
 if len(x)<4 or len(y)<4:return False
 digits=lambda s:re.findall(r'\d+',re.sub(r'^\s*\[[^\]]+\]','',str(s)))
 return digits(a)==digits(b) and SequenceMatcher(None,x,y).ratio()>=.86

def known_root(book,title):
 """The saved root with this title. A hold on any reading of the name stays in force, then the latest seen."""
 hits=[(k,v) for k,v in book.item['quests'].items() if v.get('group') and not v.get('identity_alias_of') and same_root(title,v.get('title',''))]
 pool=[h for h in hits if not h[1].get('completed')] or hits
 return max(pool,key=lambda h:(bool(h[1].get('block')),h[1].get('last_seen',0)))[0] if pool else None

def accept_button(ui,frame):
 """임무 수락 by its picture, or by its words on the real frame. The caller checks it on a second frame."""
 found=find(frame,'accept-button',(700,430,180,44),.94)
 adapter=getattr(ui,'adapter',None)
 if found or adapter is None or getattr(frame,'hi',None) is None:return found
 from owner_text import read,word_box,find as find_words
 rows=[r for r in find_words(read(adapter.project.root,frame,word_box((675,432,200,40)),scale=3),'임무 수락') if r['score']>=.85]
 return (rows[0]['x'],rows[0]['y'],None,rows[0]['score']) if len(rows)==1 else None

def auto_run_shown(ui,frame):
 """자동 진행 where 임무 수락 would be: the selected step is already accepted."""
 adapter=getattr(ui,'adapter',None)
 if adapter is None or getattr(frame,'hi',None) is None:return False
 from owner_text import read,word_box
 # The reader splits it at its space: 자동, 진행.
 rows=read(adapter.project.root,frame,word_box((740,432,140,40)),scale=3)
 return clean(''.join(r['text'] for r in rows if r['score']>=.85))=='자동진행'

def quota_words(ui,first):
 """수락한 임무 N/20 from the footer's real pixels, the same number on two frames."""
 adapter=getattr(ui,'adapter',None)
 if adapter is None or getattr(first,'hi',None) is None:return None
 from owner_text import read,word_box
 values=[]
 for frame in (first,ui.frame()):
  found=set()
  for row in read(adapter.project.root,frame,word_box((580,438,90,28)),scale=3):
   m=re.search(r'(\d{1,2})\s*/\s*20\s*$',row['text'])
   if m and row['score']>=.90 and 0<=int(m[1])<=20:found.add(int(m[1]))
  values.append(next(iter(found)) if len(found)==1 else None)
  if frame is first:ui.context.wait(.12)
 return values[0] if values[0] is not None and values[0]==values[1] else None

def quota(ui):
 """Paired labelled numeric reading; never substitute local batch length."""
 from owner_membership import hit
 first=ui.frame()
 if not quest_screen(first):return None
 worded=quota_words(ui,first)
 if worded is not None:return worded
 def full(f):
  import numpy as np
  found=find(f,'quota-full',(580,438,87,28),.94,bright=False)
  if not found:return False
  l,t,r,b=found[2];needle=asset('quota-full').astype('int16');patch=f[t:b,l:r].astype('int16')
  red=(needle[:,:,0]-needle[:,:,1]>30)&(needle[:,:,0]-needle[:,:,2]>20)
  actual=(patch[:,:,0]-patch[:,:,1]>30)&(patch[:,:,0]-patch[:,:,2]>20)&(patch[:,:,0]>110)
  return bool(red.sum()>=10 and float(actual[red].mean())>=.80)
 if full(first):
  ui.context.wait(.12)
  return 20 if quest_screen(second:=ui.frame()) and full(second) else None
 def label(f):
  options=[]
  new=find(f,'quota-label-nine',(580,438,84,28),.90)
  if new:options.append(new)
  old=hit(f,'accepted-label',(580,438,84,28),.90)
  if old:options.append((*old,.90))
  return max(options,key=lambda h:h[3]) if options else None
 a=label(first);ui.context.wait(.12);b=label(ui.frame())
 if not a or not b:
  # Preserve the product's own captured pixels before menu cleanup. A
  # screenshot of a preview may use a different glyph raster.
  adapter=getattr(ui,'adapter',None);now=time.monotonic()
  if adapter is not None and now-getattr(ui,'_counter_snapshot_at',-1e30)>60:
   from PIL import Image
   folder=Path(adapter.project.root)/'logs/quest-counters';folder.mkdir(parents=True,exist_ok=True)
   target=folder/(str(time.time_ns())+'.png')
   Image.fromarray(first).save(target);ui._counter_snapshot_at=now
   LOG.warning('퀘스트 개수 원본 보존 · %s',target.name)
  return None
 l,t,r,bt=b[2]
 # '1/20' reads .86 on the tight crop and .996 with a few more pixels, and missing it stopped the run (11-05).
 for left in (r+1,r-4):
  rows=ui.rows((left,t-2,666-left,bt-t+5),language='number',pair_minimum=.90)
  values=set()
  for row in rows:
   m=re.fullmatch(r'\s*(\d{1,2})\s*/\s*20\s*',row['text'])
   if m and row['score']>=.90 and 0<=int(m[1])<=20:values.add(int(m[1]))
  if len(values)==1:return next(iter(values))
 return None

def reviewable_block(block):
 return not block.get('functional_hold') and block.get('reason') in ('condition','prerequisite')

def tower_quest(entry):
 return bool(re.search(r'승천의[탑탐]',re.sub(r'\s+','',entry.get('title',''))))

def external_content_goal(rows):
 # Keep the existing selected-detail .85 classification threshold. This only
 # postpones a quest: it never authorizes entry, spending or completion.
 text=''.join(re.sub(r'\s+','',r.get('text','')) for r in rows if r.get('score',0)>=.85)
 match=re.search(r'승천의[탑탐](?:제)?([0-9]{1,3})층(?:을)?(?:클리어|완료)',text)
 if match:return {'content':'tower','floor':int(match[1]),'objective':match[0],'proof':'paired_selected_detail'}
 return None

def defer_external_content(book,key,rows):
 entry=book.item['quests'][key]
 if entry.get('completed') or not tower_quest(entry):return False
 goal=external_content_goal(rows)
 if not goal:return False
 old=entry.get('block')
 if old and old.get('functional_hold'):
  entry.setdefault('content_condition_history',[]).append(copy.deepcopy(old))
 book.defer(key,'condition',external_content=goal,detail='콘텐츠 조건 대기 · 승천의 탑 %d층 클리어'%goal['floor'])
 LOG.info('서사 콘텐츠 조건 대기 · %s · 승천의 탑 %d층 · 다음 서사 진행',entry['title'],goal['floor'])
 return True

def content_hold_probe(entry):
 block=entry.get('block',{})
 return bool(tower_quest(entry) and block.get('reason')=='condition' and block.get('functional_hold')
             and str(block.get('detail','')).startswith('자리 정체 복구 확인 필요'))

def position_hold(entry):
 block=entry.get('block',{})
 return bool(entry.get('accepted') is True and not entry.get('completed') and block.get('reason')=='condition'
             and block.get('functional_hold') is True and str(block.get('detail','')).startswith('자리 정체 복구 확인 필요'))

def position_hold_probe(entry,now=None):
 if not position_hold(entry):return False
 now=time.time() if now is None else now;probe=entry.get('position_condition_probe',{})
 last=probe.get('at');window=probe.get('window_at');count=probe.get('attempts',0)
 if type(last) in (int,float) and now-last<300:return False
 if type(window) in (int,float) and 0<=now-window<900 and type(count) is int and count>=2:return False
 return True

def begin_position_probe(book,key,now=None):
 entry=book.item['quests'][key];now=time.time() if now is None else now
 if not position_hold_probe(entry,now):return False
 prior=entry.get('position_condition_probe',{});window=prior.get('window_at');count=prior.get('attempts',0)
 if type(window) not in (int,float) or not 0<=now-window<900:window=now;count=0
 entry['position_condition_probe']={'at':now,'window_at':window,'attempts':count+1,'stage':'selected_step_recheck'}
 book.commit();return True

def release_position_hold(book,key,expected):
 entry=book.item['quests'][key]
 if not position_hold(entry) or entry.get('block')!=expected:return False
 entry.setdefault('position_condition_history',[]).append(copy.deepcopy(expected));entry.pop('block',None)
 entry['position_condition_probe']['stage']='fresh_suitable_step_and_auto_button'
 # A fresh current-step selection supersedes the old navigation-only Home
 # retry. Keep its history; never replay Home from this obsolete receipt.
 receipt=entry.get('position_recovery')
 if isinstance(receipt,dict) and receipt.get('phase') in ('intent','at_town'):
  entry.setdefault('position_recovery_history',[]).append(copy.deepcopy(receipt));receipt['phase']='selected_recheck'
 book.commit();LOG.info('서사 과거 오류 보류 재검증 · %s · 현재 미완료 단계·적합·자동 진행 버튼 두 화면 확인 · 완료 처리 아님',entry['title'])
 return True

def position_step_button_pair(ui,y):
 from owner_mission_ui import auto_button_hit
 first=ui.frame();ui.context.wait(.12);second=ui.frame()
 def ready(frame):
  box=selected_quest_box(frame)
  return bool(quest_screen(frame) and box and abs(box[1]+box[3]/2-y)<5 and suitable(frame,y))
 if not ready(first) or not ready(second):return False
 one=auto_button_hit(ui.service.detector,first);two=auto_button_hit(ui.service.detector,second)
 return bool(one and one==two)

def _verified_mountain_root(entry):
 """Only OCR variants corroborated by the saved 산길의 호환 10 screen."""
 title=re.sub(r'\s+','',entry.get('title',''))
 return entry.get('group') is True and entry.get('mode')=='sub_quest' and title in {
  '[외전]산길의호환','[외전]1산길의호환','[외전]ㅣ산길의호환'}

def same_verified_root_blocked(book,key,power):
 """Keep all records intact; apply only the specifically evidenced root hold."""
 entry=book.item['quests'][key]
 if not _verified_mountain_root(entry):return False
 for other,row in book.item['quests'].items():
  if other!=key and _verified_mountain_root(row) and row.get('block') and book.blocked(other,power):
   return True
 return False

def group_eligible(book,key,power):
 return book.eligible(key,power) and not same_verified_root_blocked(book,key,power)

class Groups:
 def __init__(self,ui,book,power):self.ui,self.book,self.power=ui,book,power;self.seen=set();self.rejected=set();self.keys=[];self.visible_glyphs={};self.visible_frames={};self.visible_roots={};self._last_unlocated=None;self.scrolled_for_fill=False
 def compact(self):
  for _ in range(20):
   f=self.ui.frame();opened=next((r for r in group_rows(f) if r['open']),None)
   if not opened:return
   y=opened['y'];self.ui.click(29,y,lambda f:any(r['open'] and abs(r['y']-y)<3 for r in group_rows(f)))
  raise Pending('현재 열린 임무 묶음 접기 재확인 필요')
 def top(self):
  if getattr(self.ui,'_owner_mission_fresh_open',False):
   self.ui._owner_mission_fresh_open=False;return
  import cv2
  last=None;still=0
  for _ in range(18):
   f=self.ui.frame();signature=hashlib.sha256((cv2.resize(f[100:436,70:490],(105,84)).min(axis=2)>110).astype('uint8').tobytes()).hexdigest()
   still=still+1 if signature==last else 0;last=signature
   if still>=2:return
   self.ui.wheel(1,35)
  raise Pending('임무 목록 맨 위 도달을 확인하지 못함 · 목록 일부를 전체로 보지 않음')
 def identify(self,frame,row):
  g=glyph(frame,row['y'])
  # Words name the root. Title pictures at the real size made six journal entries for one 가모리의 방랑 도사.
  words=row_words(self.ui,frame);title=row_title(words,row['y']) if words else None
  key=known_root(self.book,title) if title else None
  if not g and not key:raise Pending('임무 묶음 제목 영역 확인 필요')
  if not key:
   matches=sorted(((max(likeness(g,v.get('group_glyph')),likeness(g,self._expected_glyph(k))),k) for k,v in self.book.item['quests'].items() if v.get('group')),reverse=True)
   if matches and matches[0][0]>=.87 and (len(matches)==1 or matches[0][0]-matches[1][0]>=.04 or matches[0][0]>=.97):key=matches[0][1]
   else:key='sub_quest:group:'+hashlib.sha256(bytes.fromhex(g['bits'])).hexdigest()[:24]
  entry=self.book.item['quests'].setdefault(key,{'mode':'sub_quest','title':'서사 임무 (이름 확인 중)','deaths':0,'group':True,'group_glyph':g})
  if title and entry['title'].endswith('(이름 확인 중)'):entry.update(title=title.strip(),title_read_attempted=True)
  if entry['title'].endswith('(이름 확인 중)') and not entry.get('title_read_attempted'):
   entry['title_read_attempted']=True
   try:
    rows=self.ui.rows((70,max(96,row['y']-12),430,24),pair_minimum=.80)
    text=' '.join(r['text'] for r in rows if r['score']>=.80)
    if len(re.findall('[가-힣]',text))>=3:entry['title']=text.strip()
   except Pending:pass
  # Keep prior per-step death/condition evidence when adopting its root.
  # No old record is deleted or inferred completed during the migration.
  stem=lambda text:re.sub(r'\d+$','',re.sub(r'\s+','',text))
  if not entry.get('legacy_history_checked') and not entry['title'].endswith('(이름 확인 중)'):
   prior=[v for v in self.book.item['quests'].values() if v.get('legacy_step') and stem(v['title'])==stem(entry['title'])]
   entry['deaths']=max([entry.get('deaths',0)]+[v.get('deaths',0) for v in prior])
   blocks=[v['block'] for v in prior if v.get('block')]
   if blocks and not entry.get('block'):entry['block']=copy.deepcopy(max(blocks,key=lambda v:v.get('at',0)))
   entry['legacy_history_checked']=True
  # A negative/missed stamp must never erase an independently verified
  # completed root. Current scroll raster belongs to this visible lookup,
  # not to a new permanent identity or a replacement for death history.
  self.visible_glyphs[key]=g;self.visible_frames[key]=id(frame)
  self.visible_roots[key]=(row['y'],frame[max(96,row['y']-10):min(438,row['y']+11),70:490].copy(),time.monotonic(),dots(frame,row['y']))
  entry.update(last_seen=time.time(),accepted=dots(frame,row['y']),suitable=suitable(frame,row['y']),actionable=not entry.get('completed',False),source='paired_group_dots_and_fit')
  self.book.commit();return key
 def _expected_glyph(self,key):
  entry=self.book.item['quests'][key];recent=entry.get('group_recent_glyph')
  if entry.get('group_recent_proof')=='paired_unique_visible_root' and isinstance(recent,dict):
   bits,width=recent.get('bits'),recent.get('width')
   if isinstance(bits,str) and len(bits)==960 and re.fullmatch('[0-9a-fA-F]+',bits) and type(width) is int and 0<width<=420:
    return self.visible_glyphs.get(key,recent)
  return self.visible_glyphs.get(key,entry['group_glyph'])
 def _remember_visible(self,key,frame,row):
  # identify() and this independent visible lookup must agree. A new
  # object may reuse this evidence, while the original identity/deaths stay.
  previous=self.visible_glyphs.get(key)
  if previous is None or key not in self.visible_frames or self.visible_frames[key]==id(frame):return
  current=glyph(frame,row['y'])
  if likeness(previous,current)<.87:return
  entry=self.book.item['quests'][key]
  if entry.get('group_recent_glyph')==current and entry.get('group_recent_proof')=='paired_unique_visible_root':return
  entry.update(group_recent_glyph=current,group_recent_proof='paired_unique_visible_root',group_recent_verified_at=time.time())
  self.book.commit()
 def locate(self,key,frame=None):
  frame=self.ui.frame() if frame is None else frame
  # A row just observed in this same view need not be searched by an old,
  # normalized glyph. This short-lived proof only opens the mission row.
  reference=self.visible_roots.get(key)
  if reference and quest_screen(frame) and 0<=time.monotonic()-reference[2]<=5:
   y,needle,_,accepted=reference
   for r in group_rows(frame):
    if abs(r['y']-y)>2 or dots(frame,r['y'])!=accepted:continue
    part=frame[max(96,r['y']-10):min(438,r['y']+11),70:490]
    if part.shape!=needle.shape:continue
    import cv2,numpy as np
    score=float(cv2.matchTemplate(part,needle,cv2.TM_CCOEFF_NORMED)[0,0])
    if np.isfinite(score) and score>=.95:return r
  words=row_words(self.ui,frame)
  if words:
   named=[r for r in group_rows(frame) if (seen:=row_title(words,r['y'])) and same_root(self.book.item['quests'][key]['title'],seen)]
   if len(named)==1:return named[0]
  expected=self._expected_glyph(key)
  found=[(likeness(expected,glyph(frame,r['y'])),r) for r in group_rows(frame)]
  found.sort(key=lambda x:x[0],reverse=True)
  if found and found[0][0]>=.85 and (len(found)==1 or found[0][0]-found[1][0]>=.04):
   self._remember_visible(key,frame,found[0][1]);return found[0][1]
  # A thin glyph raster can differ after scrolling. Resolve only a unique
  # root with both visual support and a paired name read, never by y alone.
  from difflib import SequenceMatcher
  name=lambda s:re.sub('[^\uac00-\ud7a3]','',re.sub(r'^\[[^]]+\]','',s))
  expected_name=name(self.book.item['quests'][key]['title']);matches=[]
  if len(expected_name)<4:return None
  for score,row in found[:3]:
   if score<.50:continue
   try:
    rows=self.ui.rows((70,max(96,row['y']-12),430,24),pair_minimum=.80)
   except Pending:continue
   title=name(' '.join(r['text'] for r in rows if r['score']>=.80))
   if SequenceMatcher(None,expected_name,title).ratio()>=.86:matches.append(row)
  if len(matches)==1:
   self._remember_visible(key,frame,matches[0]);return matches[0]
  return None
 def select(self,key):
  from owner_mission_ui import list_rows,required_power
  from owner_skill_ui import match
  self._last_unlocated=None
  self._position_recheck_ready=None
  position_block=copy.deepcopy(self.book.item['quests'][key].get('block')) if position_hold(self.book.item['quests'][key]) else None
  for _ in range(8):
   f=self.ui.frame();row=self.locate(key,f)
   if not row:
    # Visible-first handoff: a root that is not in the current view is not
    # hunted by scrolling (wheel -1 is DOWN; a blind burst can walk past the
    # row and rewrites the display order the user asked us to follow). Report
    # it as not-selectable now, leave the journal untouched, and let the
    # caller move to the next visible candidate.
    self._last_unlocated=key
    selection_snapshot(self.ui,f,key)
    LOG.info('선택 묶음 현재 화면 밖 · 다음 후보 · %s',self.book.item['quests'][key]['title'])
    return False
   if self.book.item['quests'][key].get('completed') or completed_root(f,row['y']):return False
   if row['y']<=350:break
   self.ui.wheel(-1,2)
  else:raise Pending('선택 묶음을 화면 안으로 이동하지 못함')
  if not row['open']:
   y=row['y'];self.ui.click(250,y,lambda f:bool((r:=self.locate(key,f)) and abs(r['y']-y)<3))
   self.ui.context.wait(.20)
  for attempt in range(12):
   f=self.ui.frame();row=self.locate(key,f)
   if row and not row['open']:raise Pending('선택한 임무 묶음 열기 확인 필요')
   if not row and not attempt:raise Pending('선택한 임무 묶음 위치 확인 필요')
   top=row['y']+20 if row else 96
   following=[r['y'] for r in group_rows(f) if r['y']>top];end=min(following,default=438)
   candidates=[y for y in list_rows(self.ui,f,'leaf-story') if top<y<min(end,427)]
   candidates=[y for y in candidates if not match(f,'completed',(624,max(96,y-14),28,28),.96)]
   if candidates:
    # Prefer the accepted current step's dots, otherwise first uncompleted
    # step. Grey unaccepted text is NOT a prerequisite failure.
    preferred=[y for y in candidates if find(f,'child-dots',(600,max(96,y-17),33,34),.92)]
    if self.book.item['quests'][key].get('accepted') and not preferred:
     if following:return False
     self.ui.wheel(-1,3);continue
    y=(preferred or candidates)[0];self.ui.click(280,y,quest_screen)
    self.ui.wait(lambda f:bool((box:=selected_quest_box(f)) and abs(box[1]+box[3]/2-y)<5),seconds=3)
    if not suitable(self.ui.frame(),y):
     self.book.defer(key,'condition',detail='현재 단계 적합 표시 미확인');return False
    self.ui.context.wait(.12)
    if not suitable(self.ui.frame(),y):
     self.book.defer(key,'condition',detail='현재 단계 적합 표시 두 화면 불일치');return False
    try:
     details=self.ui.rows((674,229,202,111));text=' '.join(r['text'] for r in details if r['score']>=.85)
     from owner_emote_requirements import learn_selected_requirement
     learn_selected_requirement(self.ui,details,self.book.item['quests'][key]['title'])
     required=required_power(details)
     if required and self.power is not None and self.power<required:
      self.book.defer(key,'power',required=required);return False
     if any(s in clean(text) for s in ('선행','임무완료후','임무를완료')):
      self.book.defer(key,'condition',detail=text[:300]);return False
     if defer_external_content(self.book,key,details):return False
     if not self.book.item['quests'][key].get('block',{}).get('functional_hold'):
      self.book.prerequisite_proved(key)
     if position_block:
      if not position_step_button_pair(self.ui,y):raise Pending('과거 오류 보류 재검증 · 현재 단계 자동 진행 버튼 확인 필요')
      self._position_recheck_ready=(key,position_block)
    except Pending:
     if position_block:raise
    return True
   self.ui.wheel(-1,2)
  raise Pending('선택 묶음의 현재 미완료 단계 확인 필요')
 def accept(self,key,before):
  self.accept_clicked=False;self.already_accepted=False
  if not self.select(key):return False
  def proof(f):return bool(quest_screen(f) and selected_quest_box(f) and accept_button(self.ui,f))
  f=self.ui.frame();button=accept_button(self.ui,f)
  if not button:
   self.already_accepted=auto_run_shown(self.ui,f)
   return False
  self.ui.context.wait(.12)
  if not proof(self.ui.frame()):return False
  self.accept_clicked=True;self.ui.click(button[0],button[1],proof)
  after=None
  for _ in range(5):
   after=quota(self.ui)
   if after==before+1:break
   if after is not None and after not in (before,before+1):break
   self.ui.context.wait(.25)
  button_left=not accept_button(self.ui,self.ui.frame())
  if after==before and not button_left:
   # The same accept button and count: the click did not land. Nothing was
   # accepted, so this row is skipped for this scan rather than clicked again.
   LOG.info('수락 입력 미반영 · 개수와 버튼 그대로 · %s',self.book.item['quests'][key]['title'])
   return False
  if after in (None,before) and button_left:
   # This client keeps the old footer count after accepting, while the button
   # has already become give-up/auto. Re-open the tab to request a fresh
   # counter; never click acceptance a second time.
   self.ui.open('main_quest');self.ui.open('sub_quest');after=quota(self.ui)
  if after!=before+1:raise Pending('실제 수락 개수 증가 확인 필요 · 추가 수락을 멈춥니다')
  # The game's counter owns acceptance; the row may have moved after its update.
  row=self.locate(key)
  if not (row and dots(self.ui.frame(),row['y'])):LOG.info('수락 개수 증가 확인 · 묶음 표시는 다음 판독에서 확인 · %s',self.book.item['quests'][key]['title'])
  self.book.item['quests'][key]['accepted']=True;self.book.commit()
  adapter=getattr(self.ui,'adapter',None)
  if adapter is not None:adapter._owner_catalog_errors=0
  LOG.info('서사 실제 수락 %d/20 → %d/20 · %s',before,after,self.book.item['quests'][key]['title'])
  self.compact();return True
 def scan(self,fill=True):
  self.compact()
  actual=None
  for attempt in range(3):
   # A toast or tab transition can cover the footer for a moment.
   if attempt:self.ui.context.wait(.5)
   actual=quota(self.ui)
   if actual is not None:break
  if actual is None:raise Pending('게임의 실제 수락 개수 판독 필요 · 내부 묶음 수로 대체하지 않음')
  LOG.info('서사 수락 목록 확인 · 실제 %d/20 · 수락된 묶음은 펼치지 않음',actual)
  if not fill or actual==20:
   # Draining a received batch needs its current task, not a complete fresh
   # catalog every time. Actual capacity remains the game's counter.
   keys=[k for k in self.book.item['batch'].get('keys',[]) if self.book.item['quests'].get(k,{}).get('group')]
   f=self.ui.frame()
   for row in group_rows(f):
    if not 114<=row['y']<=420 or not dots(f,row['y']) or completed_root(f,row['y']):continue
    try:key=self.identify(f,row)
    except Pending as exc:
     LOG.info('임무 묶음 제목 판독 보류 · 이번 행 건너뜀 · %s',exc);continue
    if key not in keys:keys.append(key)
   self.book.item['batch'].update(keys=keys,phase='drain',actual_accepted=actual,scan_complete=False,catalog='groups-v1');self.book.commit()
   LOG.info('서사 받은 묶음 진행 · 실제 %d/20 · 전체 목록 재탐색 생략',actual)
   return keys,actual
  self.top()
  last=None;still=0;dragged=False;complete=False;unreadable=False
  for page in range(40):
   self.ui.context.checkpoint();f=self.ui.frame();rows=[r for r in group_rows(f) if 114<=r['y']<=420 and not completed_root(f,r['y'])]
   for row in rows:
    # One unreadable title must not stop the rest of the list. The scan just
    # stays incomplete, so nothing below it is assumed absent.
    try:key=self.identify(f,row)
    except Pending as exc:
     unreadable=True;LOG.info('임무 묶음 제목 판독 보류 · 이번 행 건너뜀 · %s',exc);continue
    if key not in self.keys:self.keys.append(key)
    entry=self.book.item['quests'][key]
    block=entry.get('block',{})
    review_condition=actual==0 and reviewable_block(block) and not same_verified_root_blocked(self.book,key,self.power)
    if fill and actual<20 and not entry['accepted'] and entry['suitable'] and not same_verified_root_blocked(self.book,key,self.power) and (not self.book.blocked(key,self.power) or review_condition) and key not in self.rejected:
     self.rejected.add(key)
     try:
      if self.accept(key,actual):actual+=1
     except Pending as exc:
      if getattr(self,'accept_clicked',False):
       LOG.warning('수락 입력 후 실제 개수 확인 보류 · %s · %s',entry['title'],exc);raise
      LOG.info('미수락 임무 단계 선택 보류 · %s · %s',entry['title'],exc)
     self.compact();f=self.ui.frame();break
   else:
    # Include grey completed names in the cheap scroll fingerprint too;
    # multiple completed-only pages are not evidence of reaching the end.
    import cv2
    signature=hashlib.sha256((cv2.resize(f[100:436,70:490],(105,84)).min(axis=2)>110).astype('uint8').tobytes()).hexdigest()
    still=still+1 if signature==last else 0;last=signature
    if still>=2:
     if dragged:complete=True;break
     self.scrolled_for_fill=True
     self.ui.drag((480,410),(480,150),quest_screen);dragged=True;still=0
    else:self.scrolled_for_fill=True;self.ui.wheel(-1,12)
    continue
   if actual>=20:complete=False;break
  accepted=[k for k in self.keys if self.book.item['quests'][k].get('accepted')]
  complete=complete and not unreadable
  self.book.item['batch']={'number':self.book.item['batch'].get('number',0)+int(fill),'keys':accepted,'phase':'drain','at':time.time(),'actual_accepted':actual,'scan_complete':complete,'catalog':'groups-v1'};self.book.commit()
  LOG.info('서사 수락 준비 종료 · 실제 %d/20 · 확인한 수락 묶음=%d · 목록 끝 확인=%s',actual,len(accepted),complete)
  return accepted,actual
 def activate(self,key):
  if not group_eligible(self.book,key,self.power):raise Pending('보류 임무의 재시도 조건 미확인')
  row=self.book.item['quests'][key]
  if row.get('block',{}).get('reason')=='death':row['deaths']=0;row.pop('block',None)
  elif row.get('block',{}).get('reason')=='power':row.pop('block',None)
  self.book.activate(key)
 def completed(self,key,row):
  from difflib import SequenceMatcher
  y=row['y'];first=self.ui.frame()
  if not completed_root(first,y):return False
  self.ui.context.wait(.12)
  if not completed_root(self.ui.frame(),y):return False
  text=' '.join(r['text'] for r in self.ui.rows((70,max(96,y-12),430,24),pair_minimum=.80) if r['score']>=.80)
  name=lambda s:re.sub('[^가-힣]','',re.sub(r'^\[[^]]+\]','',s))
  expected=name(self.book.item['quests'][key]['title'])
  if len(expected)<4 or SequenceMatcher(None,expected,name(text)).ratio()<.86:return False
  self.book.item['quests'][key].update(completed=True,accepted=False,completed_at=time.time(),completion_proof='paired_root_stamp_and_title')
  self.book.item['quests'][key].pop('block',None);self.book.item['active']=None;self.book.commit()
  adapter=getattr(self.ui,'adapter',None)
  if adapter is not None:
   from owner_mission_controller import confirmed_progress
   confirmed_progress(adapter,key)
  LOG.info('서사 묶음 완료 확인 · %s',self.book.item['quests'][key]['title']);return True
 def choose(self,keys,review=False,prefer_saved=False):
  # Menus choose from visible display order. Existing field returns resume
  # their controller without a historic-row search through this menu.
  self.compact();attempted=set();last=None;still=0;uncertain=False
  for _ in range(30):
   f=self.ui.frame();refresh=False
   for row in group_rows(f):
    if not 114<=row['y']<=420:continue
    if completed_root(f,row['y']):
     previous=self.book.item.get('active')
     if previous:
      prior=self.locate(previous,f)
      if prior and abs(prior['y']-row['y'])<3:self.completed(previous,row)
     continue
    if not suitable(f,row['y']):continue
    accepted=dots(f,row['y'])
    # Owner rule: the topmost suitable quest goes first, whether or not it was
    # accepted earlier. While the game's limit allows, accept it here; once at
    # the limit only quests already accepted can run.
    can_accept=type(getattr(self,'actual',None)) is int and self.actual<20
    if not accepted and not can_accept:continue
    try:key=self.identify(f,row)
    except Pending:
     uncertain=True;continue
    if not accepted:
     if key in self.rejected or same_verified_root_blocked(self.book,key,self.power) or self.book.blocked(key,self.power):continue
     self.rejected.add(key)
     try:
      if self.accept(key,self.actual):self.actual+=1
      # The list's accepted mark is a small picture that 1366x768 misses on some rows. Taken for not accepted, such a
      # quest found no accept button and was passed over without a word: the potion story sat at 0/3 for hours.
      elif getattr(self,'already_accepted',False) and group_eligible(self.book,key,self.power):
       LOG.info('서사 수락 표시 미확인 · 자동 진행 버튼으로 수락 확인 · %s',self.book.item['quests'][key]['title'])
       self.book.item['quests'][key]['accepted']=True
       self.activate(key);return key
     except Pending as exc:
      if getattr(self,'accept_clicked',False):
       LOG.warning('수락 입력 후 실제 개수 확인 보류 · %s · %s',self.book.item['quests'][key]['title'],exc);raise
      LOG.info('미수락 임무 단계 선택 보류 · %s · %s',self.book.item['quests'][key]['title'],exc)
     self.compact();refresh=True;break
    block=self.book.item['quests'][key].get('block',{})
    position_probe=key not in attempted and position_hold_probe(self.book.item['quests'][key])
    reviewable=(review and reviewable_block(block) and not same_verified_root_blocked(self.book,key,self.power)) or (key not in attempted and content_hold_probe(self.book.item['quests'][key])) or position_probe
    if not group_eligible(self.book,key,self.power) and not reviewable:
     LOG.info('서사 제외 사유 · %s · %s',self.book.item['quests'][key]['title'],block.get('detail') or block.get('reason') or '현재 실행 조건 미충족')
     continue
    if key in attempted or locate_backoff(self.book,key):
     raise StorySelectionPending('맨 위 진행 가능 임무의 위치 재판독 대기 · 아래 임무로 바꾸지 않음')
    attempted.add(key)
    try:
     if position_probe and not begin_position_probe(self.book,key):continue
     selected=self.select(key)
     proof=getattr(self,'_position_recheck_ready',None)
     if selected and position_probe and proof and proof[0]==key:release_position_hold(self.book,key,proof[1])
     if selected is False and self._last_unlocated==key:
      mark_locate_backoff(self.book,key);uncertain=True
     elif selected and group_eligible(self.book,key,self.power):
      self.activate(key);return key
    except Pending as exc:
     uncertain=True;mark_locate_backoff(self.book,key)
     LOG.warning('수락 임무 위치 보류 · %s · %s',self.book.item['quests'][key]['title'],str(exc))
    self.compact();refresh=True;break
   if refresh:continue  # Retry the same viewport before any downward scroll.
   if uncertain:
    raise StorySelectionPending('수락 임무 위치 미확인 · 완료·사냥 전환 없이 재판독 대기')
   import cv2
   signature=hashlib.sha256((cv2.resize(f[100:436,70:490],(105,84)).min(axis=2)>110).astype('uint8').tobytes()).hexdigest()
   still=still+1 if signature==last else 0;last=signature
   if still>=2:break
   self.ui.wheel(-1,12)
  return self.choose(keys,review=True) if not review else None

def pick(ui,book,power):
 ui.open('sub_quest')
 migrated=False
 if book.item.get('story_catalog_version')!='groups-v2':
  old=book.item.get('active')
  for entry in book.item['quests'].values():
   if entry['mode']=='sub_quest' and not entry.get('group'):entry['legacy_step']=True
  if old and book.item['quests'][old]['mode']=='sub_quest':book.item['active']=None
  book.item.update(story_catalog_version='groups-v2',story_group_fill_pending=True);book.commit();migrated=True
 fill=migrated or book.item.get('story_group_fill_pending') or book.batch_needs_fill(power) or not book.item['batch'].get('keys')
 if fill:book.item['story_group_fill_pending']=True;book.commit()
 groups=Groups(ui,book,power);keys,actual=groups.scan(fill=fill)
 if fill:book.item['story_group_fill_pending']=False;book.commit()
 if not fill and actual==0:
  keys,actual=groups.scan(fill=True);fill=True
 # The user's rule is that display order decides the next root, so selection
 # always starts at the top. A freshly opened list keeps its no-wheel shortcut.
 if fill and groups.scrolled_for_fill:ui._owner_mission_fresh_open=False
 try:groups.top()
 except Pending as exc:raise StorySelectionPending('목록 맨 위 복귀 확인 필요 · 중간 임무 선택 안 함') from exc
 groups.actual=actual
 adapter=getattr(ui,'adapter',None)
 restore=bool(getattr(adapter,'_owner_restore_story_once',False))
 result=groups.choose(keys,prefer_saved=restore)
 if result is not None and adapter is not None:adapter._owner_restore_story_once=False
 return result
