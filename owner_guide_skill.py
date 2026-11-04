"""Finish the guide quest that asks for a skill.

A new character's main quest stops at '[길라잡이] 도술 장착!' until the skill is learned.
Learning it through the skill window's green button also puts it in a free slot. Runs only
while that exact tracker title is on screen, so a character past the guide never enters here.
"""
from functools import lru_cache
from pathlib import Path
import logging,time
LOG=logging.getLogger('project_gui.DKB')
TRACKER=(46,68,738,830);LEARN_ALL='버튼_메인퀘_도술모두배우기';CONFIRM=(489,314,(452,303,527,325));COOLDOWN=180

@lru_cache(maxsize=1)
def title():
 import numpy as np
 from PIL import Image
 return np.asarray(Image.open(Path(__file__).parent/'assets/guide-skill/skill-equip-title.png').convert('RGB'))

def on_tracker(frame):
 import cv2
 if getattr(frame,'shape',None)!=(479,897,3):return False
 y1,y2,x1,x2=TRACKER
 return float(cv2.matchTemplate(frame[y1:y2,x1:x2],title(),cv2.TM_CCOEFF_NORMED).max())>=.90

def run(ui):
 """True when a skill was learned. Spends the skill fragments the guide quest asks for."""
 from owner_skill_ui import Pending,skill_screen,match
 adapter=ui.adapter
 if time.monotonic()-getattr(adapter,'_owner_guide_skill_at',-1e30)<COOLDOWN:return False
 first=ui.frame()
 if not on_tracker(first):return False
 ui.context.wait(.12)
 if not on_tracker(ui.frame()):return False
 adapter._owner_guide_skill_at=time.monotonic()
 learned=False
 try:
  ui.open_skills()
  for _ in range(6):
   ui.context.checkpoint();frame=ui.frame()
   hit=ui.service.detector.find(LEARN_ALL,frame)
   if not hit:break
   ui.service.check();ui.service.click_hit(hit);ui.context.wait(.8)
   frame=ui.frame()
   if match(frame,'learn-confirm',(378,148,150,28),.96) is None:
    LOG.info('길라잡이 도술 · 학습 확인창 미표시 · 다음 확인까지 대기');break
   ui.service.check();ui.service.click_hit(CONFIRM);ui.context.wait(1.2)
   if not skill_screen(ui.frame()):ui.context.wait(.8)
   learned=True
 except Pending as exc:
  LOG.info('길라잡이 도술 보류 · %s',exc)
 finally:
  ui.close_known()
 LOG.info('길라잡이 도술 · %s',('모두 배우기 완료 · 슬롯 자동 장착' if learned else '배울 도술 없음 · 다음 확인까지 대기'))
 return learned
