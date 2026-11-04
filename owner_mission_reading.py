"""Selected mission identity; split OCR fragments never authorize another row."""
import re
from difflib import SequenceMatcher
from owner_skill_ui import Pending,clean,selected_quest_box

class MissionRowUnreadable(Pending):pass

def title_from_rows(rows,minimum=.86):
 parts=[r for r in rows if r.get('score',0)>=minimum and len(clean(r.get('text','')))>=1]
 if not parts or len(parts)>4:return None
 parts.sort(key=lambda r:(round(r.get('y',0)/8),r.get('x',0)))
 text=' '.join(r['text'].strip() for r in parts)
 if not re.search('[가-힣]',text) or len(text)>100:return None
 if any(s in clean(text) for s in ('본임무는','임무목표','완료보상','요약정보')):return None
 # More than one bracketed category means distinct titles, not split words.
 if len(re.findall(r'\[[^\]]+\]',text))>1:return None
 body=re.sub(r'\[[^\]]+\]','',text)
 if len(re.findall('[가-힣]',body))<2:return None
 if parts and max(r.get('y',0) for r in parts)-min(r.get('y',0) for r in parts)>18:return None
 return text

def agree_titles(left,right,minimum=.70):
 if not left or not right:return False
 a,b=clean(left),clean(right)
 return a==b or SequenceMatcher(None,a,b).ratio()>=minimum

def selected_center(frame):
 box=selected_quest_box(frame)
 return round(box[1]+box[3]/2) if box else None

def read_selected_title(ui,y):
 """Use the actual selected row after auto-scroll, plus its detail heading."""
 frame=ui.frame();center=selected_center(frame)
 if center is None:raise MissionRowUnreadable('선택 강조 행 확인 필요')
 ui.context.wait(.10)
 if selected_center(ui.frame())!=center:raise MissionRowUnreadable('선택 행 이동 중')
 row_box=(70,max(96,center-12),430,24)
 left_rows=ui.rows(row_box,pair_minimum=.80);left=title_from_rows(left_rows)
 right_rows=ui.rows((679,76,196,28),pair_minimum=.75);right=title_from_rows(right_rows)
 weak=False
 if left is None:
  candidate=title_from_rows(left_rows,.80);corroboration=title_from_rows(right_rows,.75)
  if candidate and corroboration:
   categories=[re.findall(r'\[[^\]]+\]',re.sub(r'\s+','',s)) for s in (candidate,corroboration)]
   numbers=[re.findall(r'\d+',s) for s in (candidate,corroboration)]
   if categories[0] and categories[0]==categories[1] and numbers[0] and numbers[1] and numbers[0][-1]==numbers[1][-1] and agree_titles(candidate,corroboration,.60):left,right,weak=candidate,corroboration,True
 ui._owner_last_mission_read={'clicked_y':y,'selected_y':center,'row':left_rows,'detail':right_rows}
 # Paired, actual highlighted row is the primary identity. This also avoids
 # truncating a long name in the much narrower detail header.
 if not left or not re.search(r'\[[^\]]+\]',left):
  raise MissionRowUnreadable('선택 임무 행 제목 두 화면 확인 필요')
 if right and not agree_titles(left,right,.60 if weak else .70):raise MissionRowUnreadable('선택 행과 상세 제목 불일치')
 if selected_center(ui.frame())!=center:raise MissionRowUnreadable('제목 판독 후 선택 행 변경')
 return left,center
