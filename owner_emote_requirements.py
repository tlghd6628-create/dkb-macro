"""Shared quest/step requirements, separate from character input cooldowns."""
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
import json,re,time
from owner_skill_goal import Pending
PACKAGED=Path(__file__).parent/'assets/quest-emote/emote-knowledge.json'

@lru_cache(maxsize=1)
def packaged_knowledge():
 """Reviewed observations shipped with the update; local learning never enters."""
 try:d=json.loads(PACKAGED.read_text(encoding='utf8'))
 except (OSError,ValueError):return {'cards':{},'quests':{}}
 if d.get('version')!=1 or not isinstance(d.get('quests'),dict) or not isinstance(d.get('cards'),dict):return {'cards':{},'quests':{}}
 return d

def title_root(title):
 root=re.sub(r'[0-9]+$','',re.sub(r'[^가-힣0-9]','',title or ''))
 return re.sub(r'^(외전|서사|본편)1(?=[가-힣])',r'\1',root)

def stage_of(rows):
 """OCR confuses title letters but is only ever used here for the step digit."""
 values=set()
 for row in rows:
  if row.get('score',0)<.95:continue
  text=row.get('text','')
  digits=re.findall(r'[0-9]{1,3}',text)
  if digits and re.search('[가-힣]',text):values.add(digits[-1])
 return next(iter(values)) if len(values)==1 else None

class EmoteQuestMismatch(Pending):
 """The game tracks another quest than the book. Nothing was sent or recorded."""
 def __init__(self,message,*,quest=None,hud=None,target=None):
  super().__init__(message);self.quest=quest;self.hud=hud;self.target=target

def title_disagrees(text,title):
 """Only a readable title with almost nothing in common. Partial marquee text,
 misread letters and short fragments are not proof of another quest."""
 read=re.sub(r'[^가-힣]','',text or '');book=re.sub(r'[^가-힣]','',title or '')
 if len(read)<4 or not book:return False
 same=sum(block.size for block in SequenceMatcher(None,read,book,autojunk=False).get_matching_blocks())
 return same/len(read)<.4

def search_order(target):
 """A hint only chooses the first scroll direction; the card is still proven."""
 return (1,-1) if packaged_knowledge()['cards'].get(target,{}).get('search_first')=='up' else (-1,1)

def quest_id(rows):
 candidates=set()
 for row in rows:
  if row.get('score',0)<.95:continue
  text=re.sub(r'[^가-힣0-9]','',row.get('text','')).removesuffix('진행')
  m=re.fullmatch(r'(외전|서사|본편)([가-힣]{4,})([0-9]{1,3})',text)
  if m:candidates.add('|'.join(m.groups()))
 return next(iter(candidates)) if len(candidates)==1 else None

def parse_target(rows,*,emote_context=False):
 values=set()
 for row in rows:
  if row.get('score',0)<.95:continue
  text=row.get('text','')
  # The compact tracker often shows only the quoted final objective. These
  # labels were independently confirmed by native frames (화남: actual08:54
  # tracker and panel card); do not interpret arbitrary quoted items as emotions.
  from owner_emote_atlas import names as card_names,canonical
  short=re.fullmatch(r'''\s*[‘'"“]?\s*([가-힣]{1,8})\s*[’'"”]?\s*사용하기\s*''',text)
  if short:
   value=canonical(short[1])
   if emote_context or value in card_names():values.add(value)
   continue
  if '표현' not in text or '사용' not in text:continue
  m=re.search(r"표현\s*중\s*[‘'\"“]?([가-힣]{1,8})[’'\"”]?\s*사용",text)
  if m:values.add(canonical(m[1]))
 return next(iter(values)) if len(values)==1 else None

class Catalog:
 def __init__(self,root):self.path=Path(root)/'settings/owner-emote-quest-catalog.json'
 def read(self):
  try:d=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:d={'version':1,'quests':{}}
  except (OSError,ValueError) as e:raise Pending('감정 임무 학습 기록 확인 필요') from e
  if d.get('version')!=1 or not isinstance(d.get('quests'),dict):raise Pending('감정 임무 학습 기록 형식 확인 필요')
  return d
 def get(self,key):
  v=self.read()['quests'].get(key,{})
  return v.get('target') if v.get('proof')=='paired_requirement' else None
 def packaged(self,key):
  entry=packaged_knowledge()['quests'].get(key)
  if not isinstance(entry,dict) or entry.get('proof')!='actual_frames':return None
  return None if key in self.read().get('invalid',{}) else entry
 def packaged_images(self):
  """Every shipped title image, to recognize which quest the game is tracking."""
  return [(key,self.packaged(key)) for key,entry in packaged_knowledge()['quests'].items() if isinstance(entry,dict) and entry.get('title_image') and self.packaged(key)]
 def packaged_for_title(self,title):
  """Exact root only. The stage still has to be read from the current screen."""
  root=title_root(title);found=[]
  for key in packaged_knowledge()['quests']:
   parts=key.split('|')
   aliases=packaged_knowledge()['quests'][key].get('observed_book_titles',[])
   if root and len(parts)==3 and root in (parts[1],parts[0]+parts[1],*aliases):
    entry=self.packaged(key)
    if entry:found.append((key,parts[2],entry))
  return found
 def known_for_title(self,title):
  found={name:(name,stage,entry) for name,stage,entry in self.packaged_for_title(title)}
  root=title_root(title)
  for key,row in self.read()['quests'].items():
   parts=key.split('|')
   if len(parts)!=3 or root not in (parts[1],parts[0]+parts[1],*row.get('observed_book_titles',[])):continue
   if row.get('proof')=='paired_requirement' and key not in self.read().get('invalid',{}):
    found.setdefault(key,(key,parts[2],{'emote':row['target'],'proof':'paired_requirement'}))
  return list(found.values())
 def invalidate(self,key,observed):
  """Fresh contradicting evidence disables one shipped entry on this PC only."""
  from owner_timetable import save
  d=self.read();d.setdefault('invalid',{})[key]={'observed':observed,'at':time.time()}
  save(self.path,d)
 def visual_goal(self,frame):
  import numpy as np,cv2
  if getattr(frame,'shape',None)!=(479,897,3):return None
  hay=(frame[108:274,731:877].min(axis=2)>150).astype('uint8');found=[]
  for row in list(self.read()['quests'].values())[:256]:
   v=row.get('visual',{})
   if v.get('shape')!=[18,146]:continue
   try:n=np.unpackbits(np.frombuffer(bytes.fromhex(v['bits']),dtype='uint8'))[:18*146].reshape(18,146)
   except (ValueError,KeyError):continue
   if n.sum()<20:continue
   scores=cv2.matchTemplate(hay,n,cv2.TM_SQDIFF)
   for y,x in zip(*np.where(scores<.1)):
    if np.array_equal(hay[y:y+18,x:x+146],n):found.append((row['target'],108+int(y)))
  return found[0] if len({n for n,_ in found})==1 else None
 def learn(self,key,target,visual=None,*,book_title=None):
  if not key or not re.fullmatch('[가-힣]{1,8}',target):return False
  d=self.read();old=d['quests'].get(key,{})
  aliases=list(old.get('observed_book_titles',[])) if old.get('target')==target else []
  if book_title and title_root(book_title) not in aliases:aliases.append(title_root(book_title))
  d['quests'][key]={'target':target,'proof':'paired_requirement','quest_completed':False,'observed_book_titles':aliases}
  if visual is not None:
   import numpy as np
   if getattr(visual,'shape',None)==(18,146,3):
    d['quests'][key]['visual']={'shape':[18,146],'bits':np.packbits(visual.min(axis=2)>150).tobytes().hex()}
  from owner_timetable import save
  save(self.path,d);return True

def learn_selected_requirement(ui,details,book_title=None,*,emote_context=False):
 """Reuse the already selected mission detail and its stable title reader.
 No menu input, new image or guessed quest is introduced by this observer.
 """
 from owner_mission_reading import selected_center
 from owner_skill_ui import quest_screen
 target=parse_target(details,emote_context=emote_context)
 if not target:
  # The fixed row can be grey text on grey paper. Reuse rows() and its
  # original raw paired frames; only model input loses colour. No threshold
  # or complete-match guard is relaxed, no other feature changes OCR mode.
  candidates=[r for r in details if r.get('score',0)>=.5 and '표현' in r.get('text','') and isinstance(r.get('bounds'),(tuple,list)) and len(r['bounds'])==4]
  if len(candidates)==1:
   l,t,r,b=map(int,candidates[0]['bounds'])
   if 674<=l<r<=877 and 229<=t<b<=340:
    retry=ui.rows((l,t,r-l,b-t),pair_minimum=.95,text_mode='gray')
    target=parse_target(retry,emote_context=emote_context)
    if target:details=retry
 if not target:
  good=[r for r in details if r.get('score',0)>=.95]
  if good:target=parse_target([{'text':' '.join(r['text'] for r in good),'score':min(r['score'] for r in good)}],emote_context=emote_context)
 if not target:
  if any('표현' in r.get('text','') for r in details):
   import logging
   logging.getLogger('project_gui.DKB').warning('감정 고정 상세 판독 보류 · %s',[(r.get('text'),round(r.get('score',0),3)) for r in details])
  return None
 if not quest_screen(ui.frame()):return None
 center=selected_center(ui.frame())
 if center is None:return None
 titles=ui.rows((679,76,196,28),pair_minimum=.95)
 identity=quest_id(titles)
 if not identity:
  titles=ui.rows((679,76,196,28),pair_minimum=.95,text_mode='gray')
  identity=quest_id(titles)
 if not identity and book_title:
  # Groups.select already verified this exact root's glyph and current
  # selected leaf. Reuse that root; independently require the CURRENT step
  # from the fresh paired heading at the unchanged .95 stage threshold.
  stage=stage_of(titles);root=title_root(book_title)
  if stage:
   known=[key for key,s,e in Catalog(ui.adapter.project.root).known_for_title(book_title) if s==stage]
   if len(known)==1:identity=known[0]
   else:
    m=re.fullmatch(r'(외전|서사|본편)([가-힣]{4,})',root)
    if m:identity='|'.join((m[1],m[2],stage))
 if not identity or selected_center(ui.frame())!=center:
  import logging
  logging.getLogger('project_gui.DKB').warning('감정 고정 제목·단계 판독 보류 · %s',[(r.get('text'),round(r.get('score',0),3)) for r in titles])
  # A paired fixed requirement on the SAME selected leaf is sufficient for
  # this action. Unreadable global quest identity is never fabricated/learned.
  return (None,target) if selected_center(ui.frame())==center else None
 Catalog(ui.adapter.project.root).learn(identity,target,book_title=book_title)
 return identity,target
