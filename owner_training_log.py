"""Weekly training log: open it, read the total score, close it.

Rewards start at 8,000 points and no character has shown how they are claimed yet, so nothing
is pressed here. At 8,000 or more the screen is saved for that work and the job stays open.
"""
from functools import lru_cache
from pathlib import Path
import logging,re,time
LOG=logging.getLogger('project_gui.DKB')
ENTRY_AREA=(640,290,897,400);TITLE_AREA=(30,5,150,32);SCORE_BOX=(740,442,120,18);FIRST_REWARD=8000

@lru_cache(maxsize=2)
def asset(name):
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/training-log'/(name+'.png')).convert('RGB'))

def find(frame,name,area,minimum=.90):
 """(x,y,bounds) of a template inside area, or None."""
 import cv2
 if getattr(frame,'shape',None)!=(479,897,3):return None
 l,t,r,b=area;needle=asset(name)
 values=cv2.matchTemplate(frame[t:b,l:r],needle,cv2.TM_CCOEFF_NORMED)
 _,score,_,pt=cv2.minMaxLoc(values)
 if score<minimum:return None
 x,y=l+pt[0],t+pt[1];h,w=needle.shape[:2]
 return x+w//2,y+h//2,(x,y,x+w,y+h)

def parse_score(text):
 found=re.search(r'([\d,]+)\s*점\s*$',str(text))
 return int(found[1].replace(',','')) if found else None

def read_score(root,frame):
 from tools.ocr_support import get_paddle_engine
 from owner_progression import resized
 values=[parse_score(text) for page in get_paddle_engine(root,language='korean').predict(resized(frame,SCORE_BOX))
         for text,score in zip(page.get('rec_texts',()),page.get('rec_scores',())) if float(score)>=.85]
 values=[value for value in values if value is not None]
 return values[0] if len(values)==1 else None

def run(adapter,context,inputs):
 """True when nothing is waiting to be claimed. False keeps the job open."""
 from owner_start_menu import normalize
 from project_adapter.town_services import TownServices
 service=TownServices(adapter,context,inputs,['버튼_전체매뉴','버튼_나가기'])
 try:return visit(adapter,context,service)
 finally:
  try:normalize(service)
  except RuntimeError as exc:LOG.info('도사 수행록 닫기 보류 · %s',exc)

def visit(adapter,context,service):
 context.checkpoint();service.check()
 service.button('버튼_전체매뉴',wait_before_click=.1,required=True)
 hit=None;end=time.monotonic()+3
 while hit is None and time.monotonic()<end:
  context.wait(.25);context.checkpoint();hit=find(service.capture(),'menu-entry',ENTRY_AREA)
 if hit is None:
  service.check();service.click_hit((875,19,(865,9,885,29)))
  LOG.info('도사 수행록 메뉴 미확인 · 다음 일정에 다시 확인');return False
 service.check();service.click_hit(hit)
 first=second=None;end=time.monotonic()+5
 while time.monotonic()<end:
  context.wait(.3);context.checkpoint();first,second=second,service.capture()
  if first is not None and find(first,'title',TITLE_AREA) and find(second,'title',TITLE_AREA):break
 else:
  LOG.info('도사 수행록 화면 미확인 · 다음 일정에 다시 확인');return False
 root=adapter.project.root
 score=read_score(root,first)
 if score is None or score!=read_score(root,second):
  LOG.info('도사 수행록 점수 판독 실패 · 다음 일정에 다시 확인');return False
 LOG.info('도사 수행록 점수 · %d점',score)
 if score<FIRST_REWARD:return True
 from owner_gear_hold_capture_candidate import enqueue
 enqueue(root,'training-log','보상 받는 화면 확인 필요 · %d점'%score,(second.copy(),))
 LOG.info('도사 수행록 보상 받기 미구현 · %d점 화면 저장 · 입력 없음',score)
 return False
