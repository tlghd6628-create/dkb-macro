"""Opt-in generic 1/N selection port, separate from frozen recovery build."""
from owner_energy_box_port_candidate import Port
from owner_energy_box_detail_candidate import detail,detail_screen,generic_box_detail,box_candidates,stable_box_candidates
from owner_energy_choice_reader_candidate import read_pair,read_open_pair,layout_screen,layout_variant,rows_of,selected_of,asset,_score
from owner_energy_box_runtime_candidate import Hold
import logging
LOG=logging.getLogger('project_gui.DKB')

class GenericPort(Port):
 def ensure_inventory(self):
  if super().ensure_inventory() is False:return False
  from owner_inventory_filters import choose
  return choose(self.service,self.context,'consumables')

 def open_selection(self,guard):
  """Open an identified energy stack without changing or confirming quantity."""
  from project_adapter import market_inventory
  if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
  existing=self.pair(read_open_pair)
  if existing:
   self.opened=True;self.view='selection';known=None;pair=existing
  else:
   if self.pair(lambda a,b:True if detail_screen(a) and detail_screen(b) else None):self.opened=True;self.view='detail'
   if not (self.opened and self.view=='detail'):
    if self.ensure_inventory() is False:raise Hold('인벤토리 열기 확인 필요')
    self.opened=True;self.view='inventory'
    found=self.pair(stable_box_candidates)
    if not found:raise Hold('상자 후보 확인 필요')
    self.inventory_reference=tuple(f.copy() for f in self._last_pair);opened=False
    for x,y in found[0][:5]:
     self.click(x,y,guard,lambda f:(x,y) in (box_candidates(f) or ()),on_sent=lambda:setattr(self,'view','pending_detail'))
     if self.pair(lambda a,b:True if detail_screen(a) and detail_screen(b) else None):
      self.view='detail';opened=True;break
     if not self.pair(lambda a,b:True if generic_box_detail(a) and generic_box_detail(b) else None):raise Hold('상자 상세 확인 필요')
     self.view='detail';self.click(510,106,guard,generic_box_detail);self.view='inventory'
    if not opened:raise Hold('기운 선택상자 상세 확인 필요')
   current=self.pair(lambda a,b:(detail(a),detail(b)) if detail_screen(a) and detail_screen(b) else None)
   if not current:raise Hold('기운 선택상자 상세 확인 필요')
   a,b=current[0];known=a if a is not None and a==b else None
   self.click(450,363,guard,lambda f:bool(detail_screen(f)),on_sent=lambda:setattr(self,'view','pending_selection'))
   pair=self.wait_pair(read_open_pair)
   if not pair:raise Hold('선택창 확인 필요')
   self.view='selection'
  state=pair[0];total=state.get('available_count');quantity=state.get('quantity')
  if (known is None and getattr(self,'selection_total',None)==total
      and getattr(self,'detail_count_before',None)==total):known=total
  if (type(total) is not int or type(quantity) is not int or not 1<=quantity<=total
      or (known is not None and known!=total)):raise Hold('선택창 수량과 상자 잔량 확인 필요')
  self.detail_count_before=known;self.selection_total=total
  return dict(verified=True,selected=state.get('selected'),quantity=quantity,boxes=total,
              detail_boxes=known,detail_identity=True,frame_ids=pair[1],captured_at=pair[2])

 def quantity_control(self,frame,kind):
  offset=layout_variant(frame)
  if offset is None:return None
  if kind=='max':return self.service.detector.find('버튼_인벤_MAX',frame,threshold=.95)
  boxes={'plus':(503,322,515,333),'minus':(382,322,394,333),'min':(361,322,374,333)}
  if kind not in boxes:return None
  l,t,r,b=boxes[kind];t+=offset;b+=offset
  reference=asset('quantity-'+kind);patch=frame[t:b,l:r]
  if _score(patch,reference)<.98:return None
  return ((l+r)//2,(t+b)//2,(l,t,r,b))

 def prepare_batch(self,name,quantity,guard):
  """Set a proved slider using bounded single +/- or native MIN/MAX clicks."""
  if name not in ('생명','여명','몽환','홍염') or type(quantity) is not int or quantity<1:raise Hold('묶음 수령 수량 확인 필요')
  opened=self.open_selection(guard);total=opened['boxes']
  if quantity>total:raise Hold('묶음 수량이 상자 잔량을 초과합니다')
  pair=self.pair(read_open_pair)
  if not pair:raise Hold('기운 선택창 재확인 필요')
  state=pair[0]
  if state.get('selected')!=name:
   index=('생명','여명','몽환','홍염').index(name);offset=layout_variant(self._last_pair[1])
   self.click(450,rows_of(self._last_pair[1])[index]+17+offset,guard,lambda f:read_open_pair(f,f.copy())==state)
   pair=self.wait_pair(read_pair)
   if not pair:raise Hold('선택 기운 재확인 필요')
   state=pair[0]
  # Even an exact desired quantity needs independently fresh two-frame proof.
  for _ in range(1000):
   if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
   if state.get('selected')!=name or state.get('available_count')!=total:raise Hold('선택 기운 또는 잔량 변경')
   current=state.get('quantity')
   if current==quantity:break
   if type(current) is not int or not 1<=current<=total:raise Hold('현재 수량 판독 필요')
   frame=self.service.capture();options=[(abs(quantity-current),'plus' if current<quantity else 'minus')]
   if self.quantity_control(frame,'min'):options.append((quantity,'min'))
   if self.quantity_control(frame,'max'):options.append((1+total-quantity,'max'))
   _,kind=min(options,key=lambda p:p[0]);hit=self.quantity_control(frame,kind)
   if not hit:raise Hold('수량 조절 버튼 확인 필요')
   expected=1 if kind=='min' else total if kind=='max' else current+(1 if kind=='plus' else -1)
   # Steps are followed by the counter moving, not by reading it: OCR takes 3 for 8 at .90. The total is read at the end.
   counter=frame[317:337,405:491].copy()
   def same(f):return selected_of(f)==name and self.quantity_control(f,kind)==hit
   self.click(hit[0],hit[1],guard,same)
   def changed(a,b):
    import numpy as np
    x,y=a[317:337,405:491],b[317:337,405:491]
    if not np.array_equal(x,y) or np.array_equal(x,counter) or selected_of(a)!=name or selected_of(b)!=name:return None
    return dict(state,quantity=expected)
   pair=self.wait_pair(changed)
   if not pair:raise Hold('수량 변경 결과 재확인 필요 · %s에서 %s 기대'%(current,expected))
   state=pair[0]
  else:raise Hold('수량 조절 한도 초과')
  final=self.pair(read_pair)
  if not final or final[0].get('selected')!=name or final[0].get('quantity')!=quantity or final[0].get('available_count')!=total:raise Hold('묶음 확정 직전 수량 확인 필요')
  self.last_target=name;self.expected_boxes_before=total;self.expected_quantity=quantity
  return dict(verified=True,name=name,quantity=quantity,boxes=total,detail_boxes=self.detail_count_before,
              detail_identity=True,frame_ids=final[1],captured_at=final[2])

 def same_character(self,frame):
  character=(getattr(self,'evidence_identity',None) or {}).get('character')
  if not character:return False
  from owner_progression import inventory_parts
  if inventory_parts(frame)!=(True,True):return False
  from owner_ui_foreground import inventory_header,same_dimmed_text
  import time
  canonical=inventory_header(frame,character)
  if canonical is not None:
   # A name already proved by the canonical character ID is the reference;
   # never learn a new identity from a dimmed or unknown overlay.
   x,name=canonical
   self._character_reference={'character':character,'context':self.context,'at':time.monotonic(),'x':x,
      'name':name.copy(),'anchor':frame[11:23,34:53].copy()}
   return True
  reference=getattr(self,'_character_reference',None)
  if (not isinstance(reference,dict) or reference.get('character')!=character or reference.get('context') is not self.context
      or not 0<=time.monotonic()-reference.get('at',-1e30)<=180 or not layout_screen(frame)):return False
  x=reference['x']
  return same_dimmed_text(reference['name'],frame[9:25,x:x+33],reference['anchor'],frame[11:23,34:53])
 def pair(self,reader):
  if not getattr(self,'evidence_identity',None):return super().pair(reader)
  return super().pair(lambda a,b:reader(a,b) if self.same_character(a) and self.same_character(b) else None)
 def click(self,x,y,guard,predicate,on_sent=None):
  if not getattr(self,'evidence_identity',None):return super().click(x,y,guard,predicate,on_sent=on_sent)
  def proved(frame):
   same=self.same_character(frame);screen=bool(predicate(frame))
   if not (same and screen):LOG.info('상자 입력 전 확인 실패 · 캐릭터=%s · 화면=%s',same,screen)
   return same and screen
  return super().click(x,y,guard,proved,on_sent=on_sent)
 def __init__(self,adapter,context,inputs):
  super().__init__(adapter,context,inputs)
  # Initialize before capturing an action proof. A cold OCR load must never
  # turn an old screenshot into a supposedly fresh count.
  from owner_energy_box_detail_candidate import warm_count_reader
  context.checkpoint();warm_count_reader(adapter.project.root);context.checkpoint()
 def current_detail(self,guard):
  if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
  if self.opened and self.view=='detail':
   def same_detail(a,b):
    x,y=detail(a),detail(b)
    return x if x is not None and x==y else None
   pair=self.pair(same_detail)
   if not pair:raise Hold('현재 기운상자 잔량 재확인 필요')
   return dict(verified=True,boxes=pair[0],frame_ids=pair[1],captured_at=pair[2])
  return super().current_detail(guard)
 def prepare_one(self,name,guard):
  from project_adapter import market_inventory
  if guard() is not True:raise Hold('캐릭터 또는 설정 변경')
  if self.ensure_inventory() is False:raise Hold('인벤토리 열기 확인 필요')
  self.opened=True;self.view='inventory'
  pair=self.pair(stable_box_candidates)
  if not pair:raise Hold('상자 후보 확인 필요')
  self.inventory_reference=tuple(f.copy() for f in self._last_pair);found=False;known=None
  for x,y in pair[0][:5]:
   self.click(x,y,guard,lambda f:(x,y) in (box_candidates(f) or ()),on_sent=lambda:setattr(self,'view','pending_detail'))
   pair_detail=self.pair(lambda a,b:True if detail_screen(a) and detail_screen(b) else None)
   if pair_detail:
    a,b=self._last_pair;x1,x2=detail(a),detail(b)
    known=x1 if x1 is not None and x1==x2 else None
    self.view='detail';found=True;break
   other=self.pair(lambda a,b:True if generic_box_detail(a) and generic_box_detail(b) else None)
   if not other:raise Hold('상자 상세 확인 필요')
   self.view='detail';self.click(510,106,guard,generic_box_detail);self.view='inventory'
  if not found:raise Hold('기운상자 상세 확인 필요')
  self.click(450,363,guard,lambda f:bool(detail_screen(f)),on_sent=lambda:setattr(self,'view','pending_selection'))
  pair=self.wait_pair(read_open_pair)
  if not pair:raise Hold('선택창 확인 필요')
  self.view='selection';state=pair[0];total=state.get('available_count')
  if state.get('quantity')!=1 or type(total) is not int or total<1 or (known is not None and known!=total):raise Hold('1개와 현재 상자 개수 확인 필요')
  if state.get('selected')!=name:
   index=('생명','여명','몽환','홍염').index(name);y=rows_of(self._last_pair[1])[index]+17
   self.click(450,y,guard,lambda f:read_open_pair(f,f.copy())==state)
   pair=self.wait_pair(read_pair)
   if not pair:raise Hold('선택 기운 재확인 필요')
   state=pair[0]
  if state.get('selected')!=name or state.get('quantity')!=1 or state.get('available_count')!=total:raise Hold('선택 기운과 수량이 바뀌었습니다')
  self.last_target=name;self.expected_boxes_before=total
  return dict(verified=True,name=name,quantity=1,boxes=total,detail_boxes=known,detail_identity=True,frame_ids=pair[1],captured_at=pair[2])

def factory(adapter,context,inputs):return GenericPort(adapter,context,inputs)
