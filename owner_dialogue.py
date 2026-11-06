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

TODAY_WORDS=(600,410,240,34)   # real: 오늘 하루 안 보기 left of the skip question, its box at ~(627,426) (pc2 11-06)


def tick_today(runner,frame):
 """The skip question's 오늘 하루 안 보기, ticked the first time it shows each game day (user 11-06: it came up on every
 skip, 11 times in 8 minutes). Once a day only: a second press would untick it."""
 if getattr(frame,'hi',None) is None:return False
 from owner_timetable import now,day_at
 adapter=getattr(runner,'adapter',None);today=day_at(now()).isoformat()
 holder=adapter if adapter is not None else runner
 if getattr(holder,'_owner_skip_today',None)==today:return False
 from owner_text import read,clean
 rows=[r for r in read(None,frame,TODAY_WORDS,scale=2,minimum=.6) if '오늘하루' in clean(r['text'])]
 if len(rows)!=1:return False
 import owner_hd as hd
 x,y,box=hd.real_hit(max(0,round(rows[0]['bounds'][0])-16),round(rows[0]['ry']))
 runner.context.checkpoint()
 with runner.inputs.transaction():runner.inputs.click(x,y,bounds=box)
 holder._owner_skip_today=today;runner.context.wait(.25)
 LOG.info('장면 넘기기 확인창 · 오늘 하루 안 보기 체크')
 return True


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
   tick_today(runner,current)
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
