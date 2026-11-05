"""Discard changed quest click candidates and reclassify, never click stale."""
from functools import wraps
import logging,threading,time
from owner_skill_goal import Pending
LOG=logging.getLogger('project_gui.DKB');LOCAL=threading.local();CHANGED=object()

def step(runner,context,changes):
 from project_adapter.guide_rewards import CandidateSceneChanged
 previous=getattr(LOCAL,'context',None);LOCAL.context=context
 try:
  try:return runner.step()
  except CandidateSceneChanged:
   context.checkpoint();now=time.monotonic();changes[:]=[at for at in changes if now-at<10];changes.append(now)
   if len(changes)>5:raise Pending('임무 버튼 위치 변경이 10초 안에 6회 반복 · 진단 확인 필요')
   LOG.info('임무 버튼 위치 변경 · 이전 클릭 폐기 · 최신 화면 재판정')
   context.wait(.12);return CHANGED
 finally:LOCAL.context=previous

def install():
 from project_adapter.sleep_mode import SleepModeActions
 if getattr(SleepModeActions.click,'_owner_quest_scene_retry',False):return
 ordinary=SleepModeActions.click
 @wraps(ordinary)
 def click(self,name,hit,threshold=.9,region=None,**kwargs):
  if getattr(LOCAL,'context',None) is self.context:
   # The native method performs its original target/template/hit guard and
   # raises CandidateSceneChanged before mouse-down instead of RuntimeError.
   # Its fresh validation and input transaction are retained unchanged.
   kwargs['retry_on_change']=True
  return ordinary(self,name,hit,threshold=threshold,region=region,**kwargs)
 click._owner_quest_scene_retry=True;SleepModeActions.click=click
