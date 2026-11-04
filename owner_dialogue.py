"""Fast ESC only at the native positively-recognized cutscene skip state."""
from functools import wraps
import time,logging
LOG=logging.getLogger('project_gui.DKB')

def press(runner,vk):
 context=runner.context;inputs=runner.inputs
 context.checkpoint()
 with inputs.transaction():
  try:
   inputs.down('key',vk)
   context.wait(max(.025,min(.10,getattr(getattr(inputs,'backend',None),'minimum_hold_seconds',0))))
  finally:inputs.up('key',vk)

def skip(runner,spec,match,frame):
 first=runner.slots.match('skip',runner.capture())
 if not first.get('hit'):return False
 # Short, state-checked taps, never a held ESC or a blind key-spam loop.
 for attempt in range(3):
  runner.context.checkpoint()
  current=runner.capture()
  if not runner.slots.match('skip',current).get('hit'):return True
  press(runner,0x1b);runner.context.wait(.06)
  current=runner.capture()
  confirm=runner.slots.match('skip_confirm',current)
  if confirm.get('hit'):
   runner.input_one('skip_confirm',confirm,current);return True
  if not runner.slots.match('skip',current).get('hit'):return True
  runner.context.wait(.06)
 return True

def install(gui):
 if getattr(gui,'_owner_dialogue',False):return
 from project_adapter.main_quest import BoundedMainQuestRunner
 ordinary=BoundedMainQuestRunner.handle_skip
 @wraps(ordinary)
 def fast(runner,spec,match,frame):return skip(runner,spec,match,frame)
 BoundedMainQuestRunner.handle_skip=fast;gui._owner_dialogue=True
 LOG.info('대화 넘기기 준비 · 인식된 넘기기 화면에서 ESC · 짧은 입력·화면 재확인 · 최대 3회')
