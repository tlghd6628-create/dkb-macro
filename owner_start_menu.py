"""Normalize only bright, known root menus before the original start flow."""
from pathlib import Path
from functools import lru_cache,wraps
import logging
LOG=logging.getLogger('project_gui.DKB')

@lru_cache(maxsize=4)
def growth_title(name='growth'):
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/start-menu'/(name+'-title.png')).convert('RGB'))

@lru_cache(maxsize=1)
def training_banner():
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/start-menu/training-none.png').convert('RGB'))

def idle_training(frame):
 import cv2
 if getattr(frame,'hi',None) is not None:
  # A running training shows no such words, and goes to its own resume path.
  from owner_text import read,word_box,clean
  return any('수련이없습니다' in clean(r['text']) for r in read(None,frame,word_box((380,425,135,27))))
 return float(cv2.matchTemplate(frame[425:452,380:515],training_banner(),cv2.TM_CCOEFF_NORMED).max())>=.97

def help_card(frame):
 import cv2
 if getattr(frame,'shape',None)!=(479,897,3):return False
 return float(cv2.matchTemplate(frame[432:472,395:505],help_close(),cv2.TM_CCOEFF_NORMED).max())>=.95

@lru_cache(maxsize=1)
def help_close():
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/start-menu/help-close.png').convert('RGB'))

@lru_cache(maxsize=1)
def panel_header():
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/start-menu/menu-panel.png').convert('RGB'))

def menu_panel(frame):
 """The side menu from the top-right icon. A job that stopped left it open, and F1 then read an unknown screen for 40 s and quit (14:33)."""
 import cv2,numpy as np
 if getattr(frame,'shape',None)!=(479,897,3):return False
 if getattr(frame,'hi',None) is not None:
  # A guide dims this panel and points into it: dim words do not read, so it stays with the guide handler.
  from owner_text import read_area,clean
  words={clean(r['text']) for r in read_area(None,np.asarray(frame.hi)[40:70,970:1300],left=970,top=40)}
  return len(words&{'길라잡이','이벤트','거래소','영석상점','우편함','가방'})>=3
 needle=panel_header();area=frame[46:72,632:694]
 _,score,_,pos=cv2.minMaxLoc(cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED))
 if score<.95:return False
 # A guide dims this same panel and points into it. That one belongs to the guide handler.
 h,w=needle.shape[:2];patch=area[pos[1]:pos[1]+h,pos[0]:pos[0]+w]
 return float(np.abs(patch.astype('int16')-needle.astype('int16')).mean())<=15

# Full-screen menus a stop can leave open, named by the words at their top left.
TITLE_MENUS=('설정','성장','도술','임무','세계지도','가호','문파','몽련치료','탈것','내정보','우편함','이벤트','길라잡이','업적','거래소','잡화상점','보스토벌','도사수행록',
 '화첩','단봉인해제','내면의길','기운발현','의복','신수','칭호','친구','구인구직','아이템사전','제작','유물수집','요귀도감','보물찾기','비경탐험','승천의탑','플래너','순위','키설정','영석상점','문파전투','낙화의전장','차원점령전','도깨비수련장','만귀비경','모륭')

def title_menu(frame):
 """The menu these words name, or None. None too on a frame with no real pixels."""
 import re
 from owner_text import title
 # Letters only: the icons beside a title come back as stray marks (설정?).
 for words in title(frame) or ():
  name=re.sub(r'[^가-힣]','',str(words))
  if name in TITLE_MENUS:return name
 return None

# Windows in the middle of the screen a stopped job can leave open, with nothing to lose by closing.
WINDOW_TITLES=('이벤트',)
WINDOW_AREA=(210,125,950,70)

def game_start_word(frame):
    """The place of 게임 시작 on the first screen, in 897x479 terms, or None. The game logs out after a long idle spell."""
    if getattr(frame,'hi',None) is None:return None
    import numpy as np
    from owner_text import read_area,clean
    from owner_hd import logical_of
    rows=read_area(None,np.asarray(frame.hi)[585:635,500:870],left=500,top=585)
    found=[r for r in rows if clean(r['text'])=='게임시작']
    return logical_of(found[0]['rx'],found[0]['ry'],frame.layout) if len(found)==1 else None

def word_window(frame):
 """(title, place of its X in 897x479 terms) of a known window, or None."""
 if getattr(frame,'hi',None) is None:return None
 import numpy as np
 from owner_text import read_area,clean
 from owner_hd import logical_of
 x,y,w,h=WINDOW_AREA
 rows=read_area(None,np.asarray(frame.hi)[y:y+h,x:x+w],left=x,top=y)
 title=next((clean(r['text']) for r in rows if clean(r['text']) in WINDOW_TITLES),None)
 if not title:return None
 marks=[r for r in rows if clean(r['text']) in ('×','X','x','✕') and r['rx']>x+w/2]
 at=(marks[0]['rx'],marks[0]['ry']) if marks else (1123,162)
 return title,logical_of(at[0],at[1],frame.layout)

def kind(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return None
 if getattr(frame,'hi',None) is not None:
  name=title_menu(frame)
  if name:return name
  window=word_window(frame)
  return window[0] if window else '영기 수련' if idle_training(frame) else None
 from owner_skill_ui import skill_screen,quest_screen,map_screen
 if skill_screen(frame):return '도술'
 if quest_screen(frame):return '임무'
 # A stop during a potion or teleport trip can leave the world map open.
 if map_screen(frame):return '지도'
 # A guide can open spirit training with nothing running: '진행 중인 수련이 없습니다'. A running
 # training has no such banner, so it still goes to the existing resume path.
 if idle_training(frame):return '영기 수련'
 import cv2,numpy as np
 for source,label in (('growth','성장'),('blessing','가호'),('treatment','몽련 치료'),('clan','문파')):
  title=growth_title(source);patch=frame[7:30,36:101]
  scores=cv2.matchTemplate(patch,title,cv2.TM_CCOEFF_NORMED)
  scores=np.where(np.isfinite(scores),scores,-1)
  _,score,_,pos=cv2.minMaxLoc(scores)
  if score<.97:continue
  h,w=title.shape[:2];actual=patch[pos[1]:pos[1]+h,pos[0]:pos[0]+w]
  foreground=title.min(axis=2)>170
  if foreground.sum()>=8 and float((actual.min(axis=2)[foreground]>150).mean())>=.8:return label
 return None

# Menus a stop can leave open, with nothing to lose by backing out. Named by their title words, so a
# new menu needs one word here and no new picture. A menu not named here is left alone: a running
# spirit training also has a back button and has its own resume path.
PLAIN_MENUS=('우편함','이벤트','길라잡이','업적','거래소','잡화상점','보스토벌','상점','도사수행록','가호','성장','문파','제작','보물찾기','설정')

def plain_menu(service,frame):
 """The title word of a plain menu with its back button showing, or None."""
 detector,adapter=getattr(service,'detector',None),getattr(service,'adapter',None)
 if detector is None or adapter is None or not detector.find('버튼_나가기',frame,threshold=.96):return None
 import numpy as np
 from tools.ocr_support import get_paddle_engine
 from owner_progression import resized
 engine=get_paddle_engine(adapter.project.root,language='korean')
 for page in engine.predict(resized(frame,(36,4,110,30))):
  for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())):
   text=''.join(str(text).split())
   if float(score)>=.80 and text in PLAIN_MENUS:return text
 return None

def normalize(service):
 """No confirmations, claims, purchases, growth actions or unknown ESC."""
 for attempt in range(3):
  service.context.checkpoint();service.check()
  from owner_worn_stats import popup as worn_popup
  initial=service.capture()
  window=word_window(initial)
  if window:
   service.context.wait(.12)
   again=word_window(service.capture())
   if again and again[0]==window[0]:
    service.context.checkpoint();service.check()
    x,y=again[1];service.click_hit((x,y,(x-5,y-5,x+6,y+6)));service.context.wait(.6)
    LOG.info('시작 위치 정리 · %s 창 닫기',window[0]);continue
  # A first visit to a menu shows a picture card that only 닫기 closes.
  if help_card(initial):
   service.context.wait(.12)
   if help_card(service.capture()):
    service.context.checkpoint();service.check()
    service.click_hit((450,452,(420,441,480,464)));service.context.wait(.6)
    LOG.info('시작 위치 정리 · 안내 카드 닫기');continue
  if worn_popup(initial):
   service.context.wait(.12)
   if worn_popup(service.capture()):
    service.context.checkpoint();service.check()
    if worn_popup(service.capture()):
     service.click_hit((510,106,(503,99,518,113)));service.context.wait(.2)
     LOG.info('시작 위치 정리 · 착용 장비 상세창 닫기');continue
  if menu_panel(initial):
   service.context.wait(.12)
   if menu_panel(service.capture()):
    service.context.checkpoint();service.check()
    service.click_hit((875,19,(865,9,885,29)));service.context.wait(.4)
    LOG.info('시작 위치 정리 · 전체 메뉴 닫기');continue
  def name(frame):return kind(frame) or plain_menu(service,frame)
  first=name(initial);service.context.wait(.12)
  second=name(service.capture())
  if first is None or first!=second:return
  # The second observation and the final guarded frame must still be the
  # same visible foreground menu. Never press a back button behind a popup.
  frame=service.capture()
  if name(frame)!=first:return
  hit=service.detector.find('버튼_나가기',frame,threshold=.96)
  # The back arrow has no words, and every full-screen menu keeps it at the top left corner.
  if not hit and getattr(frame,'hi',None) is not None:hit=(22,19,(12,9,32,29))
  if not hit:raise RuntimeError(first+' 시작 메뉴의 나가기 위치 확인 필요')
  service.context.checkpoint();service.check()
  service.click_hit(hit);service.context.wait(.25)
  LOG.info('시작 위치 정상화 · %s 메뉴 나가기 · 현재 위치 다시 판독',first)
 service.context.checkpoint()
 frame=service.capture()
 if (kind(frame) or plain_menu(service,frame)) is not None:raise RuntimeError('시작 메뉴 닫힘을 확인하지 못했습니다')

def install():
 from project_adapter._entry import Adapter
 from project_adapter.town_services import TownServices
 if getattr(Adapter.run,'_owner_start_menu',False):return
 original=Adapter.run
 @wraps(original)
 def run(adapter,context,inputs):
  context.checkpoint()
  # Native sleep recognition/drag must precede the startup scene router.
  adapter.exit_sleep_mode(context,inputs)
  context.checkpoint()
  service=TownServices(adapter,context,inputs,['버튼_나가기'])
  normalize(service)
  return original(adapter,context,inputs)
 run._owner_start_menu=True;Adapter.run=run
