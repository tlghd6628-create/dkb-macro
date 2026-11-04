"""Original inventory category buttons; no item identity or consume authority."""
import numpy as np
from owner_progression import inventory_parts
from owner_energy_box_runtime_candidate import Hold

NAMES={'equipment':'버튼_인벤토리_장비탭','consumables':'버튼_인벤토리_소모품탭'}
BOXES={'equipment':(872,125,887,140),'consumables':(872,153,887,169)}

def selected(frame,kind):
 if kind not in BOXES or getattr(frame,'shape',None)!=(479,897,3):return False
 if inventory_parts(frame)!=(True,True):return False
 x,y,r,b=BOXES[kind]
 return int((frame[y:b,x:r].min(axis=2)>170).sum())>=30

def choose(service,context,kind):
 if kind not in NAMES:raise ValueError('Unknown inventory filter')
 context.checkpoint();service.check();a=service.capture();context.wait(.12)
 context.checkpoint();service.check();b=service.capture()
 if inventory_parts(a)!=(True,True) or inventory_parts(b)!=(True,True):raise Hold('필터 선택 전 인벤토리 확인 필요')
 from owner_worn_stats import popup as worn_popup
 from owner_membership import _inventory_popup
 if any(worn_popup(f) or _inventory_popup(f) is not None for f in (a,b)):
  raise Hold('인벤토리 필터 전 상세창 종료 확인 필요')
 if selected(a,kind) and selected(b,kind):return True
 first=service.detector.find(NAMES[kind],a,threshold=.95)
 second=service.detector.find(NAMES[kind],b,threshold=.95)
 if not first or first!=second:raise Hold('인벤토리 필터 버튼 확인 필요')
 context.checkpoint();service.check();fresh=service.capture()
 if inventory_parts(fresh)!=(True,True) or service.detector.find(NAMES[kind],fresh,threshold=.95)!=second:
  raise Hold('필터 입력 전 화면 변경')
 service.click_hit(second);context.wait(.2)
 a=service.capture();context.wait(.12);context.checkpoint();service.check();b=service.capture()
 if not selected(a,kind) or not selected(b,kind):raise Hold('인벤토리 필터 선택 결과 미확인')
 return True
