"""Normalize only bright, known root menus before the original start flow."""
from pathlib import Path
from functools import lru_cache,wraps
import logging
LOG=logging.getLogger('project_gui.DKB')

@lru_cache(maxsize=2)
def growth_title(name='growth'):
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/start-menu'/(name+'-title.png')).convert('RGB'))

def kind(frame):
 if getattr(frame,'shape',None)!=(479,897,3):return None
 from owner_skill_ui import skill_screen,quest_screen
 if skill_screen(frame):return '도술'
 if quest_screen(frame):return '임무'
 import cv2,numpy as np
 for source,label in (('growth','성장'),('blessing','가호')):
  title=growth_title(source);patch=frame[7:30,36:101]
  scores=cv2.matchTemplate(patch,title,cv2.TM_CCOEFF_NORMED)
  scores=np.where(np.isfinite(scores),scores,-1)
  _,score,_,pos=cv2.minMaxLoc(scores)
  if score<.97:continue
  h,w=title.shape[:2];actual=patch[pos[1]:pos[1]+h,pos[0]:pos[0]+w]
  foreground=title.min(axis=2)>170
  if foreground.sum()>=8 and float((actual.min(axis=2)[foreground]>150).mean())>=.8:return label
 return None

def normalize(service):
 """No confirmations, claims, purchases, growth actions or unknown ESC."""
 for attempt in range(3):
  service.context.checkpoint();service.check()
  from owner_worn_stats import popup as worn_popup
  initial=service.capture()
  if worn_popup(initial):
   service.context.wait(.12)
   if worn_popup(service.capture()):
    service.context.checkpoint();service.check()
    if worn_popup(service.capture()):
     service.click_hit((510,106,(503,99,518,113)));service.context.wait(.2)
     LOG.info('시작 위치 정리 · 착용 장비 상세창 닫기');continue
  first=kind(initial);service.context.wait(.12)
  second=kind(service.capture())
  if first is None or first!=second:return
  # The second observation and the final guarded frame must still be the
  # same visible foreground menu. Never press a back button behind a popup.
  frame=service.capture()
  if kind(frame)!=first:return
  hit=service.detector.find('버튼_나가기',frame,threshold=.96)
  if not hit:raise RuntimeError(first+' 시작 메뉴의 나가기 위치 확인 필요')
  service.context.checkpoint();service.check()
  service.click_hit(hit);service.context.wait(.25)
  LOG.info('시작 위치 정상화 · %s 메뉴 나가기 · 현재 위치 다시 판독',first)
 service.context.checkpoint()
 if kind(service.capture()) is not None:raise RuntimeError('시작 메뉴 닫힘을 확인하지 못했습니다')

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
