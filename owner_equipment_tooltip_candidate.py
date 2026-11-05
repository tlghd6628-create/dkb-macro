"""Paired observed inventory-tooltip reader and guarded equipment port.

The real saved fixture is rare-worn versus normal-candidate (a rejected
transition). No real normal-to-rare or empty-slot example has been observed.
Unknown layouts and unverified item categories always hold.
"""
from pathlib import Path
from functools import lru_cache
import base64,hashlib,json,re,time,math
import cv2,numpy as np
from PIL import Image
from owner_equipment_upgrade_candidate import Hold,Journal,run_once,confirm_category,confirm,SLOTS

ASSET=Path(__file__).parent/'assets/gear-tooltip/worn-e.png'
PART_MAP={**{name:name for name in SLOTS},'부채':'무기'}
@lru_cache(maxsize=1)
def badge():return np.asarray(Image.open(ASSET).convert('RGB'))

def _score(area,needle):
 if area.shape[0]<needle.shape[0] or area.shape[1]<needle.shape[1]:return -1.
 values=cv2.matchTemplate(area,needle,cv2.TM_CCOEFF_NORMED)
 return float(np.where(np.isfinite(values),values,-1).max())

def _ocr(engine,frame,box,*,minimum=.90):
 x,y,w,h=box;part=frame[y:y+h,x:x+w]
 if part.shape!=(h,w,3):raise Hold('장비 상세 영역 확인 필요')
 img=cv2.resize(part,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
 rows=[(str(t),float(s)) for p in engine.predict(img) for t,s in zip(p.get('rec_texts',()),p.get('rec_scores',())) if float(s)>=minimum]
 if not rows:raise Hold('장비 상세 글자 판독 필요')
 return ''.join(re.sub(r'\s+','',t) for t,_ in rows)

def _observed_grade_colour(frame,box):
 x,y,w,h=box;area=frame[y:y+h,x:x+w]
 if area.shape!=(h,w,3):return None
 hsv=cv2.cvtColor(area,cv2.COLOR_RGB2HSV);hue,sat,val=(hsv[:,:,i] for i in range(3))
 blue=float(((hue>=90)&(hue<=130)&(sat>35)&(val>50)).mean())
 brown=float(((hue<=40)&(sat>20)&(val>35)).mean())
 if blue>=.70 and brown<.15:return '희귀'
 if brown>=.70 and blue<.15:return '일반'
 return None

def _item_token(title,icon):
 if icon.shape!=(20,20,3):raise Hold('장비 아이콘 확인 필요')
 mask=(title.min(axis=2)>170).astype(np.uint8);ys,xs=np.where(mask)
 if len(xs)<12:raise Hold('장비 이름 전경 확인 필요')
 mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
 return json.dumps({'title_shape':list(mask.shape),'title_mask':base64.b64encode(mask.tobytes()).decode('ascii'),
                    'title_edge':bool(xs.min()<2 or xs.max()>=title.shape[1]-2),
                    'icon_rgb':base64.b64encode(icon.tobytes()).decode('ascii')},sort_keys=True,separators=(',',':'))

def compare_frame(frame,engine):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:raise Hold('장비 비교 화면 확인 필요')
 # Two distinct, known tooltip panes: E on the worn left, absent on candidate.
 worn=_score(frame[116:135,345:365],badge());candidate=_score(frame[116:135,500:520],badge())
 if candidate>=.90:raise Hold('착용 표시 확인 필요')
 grades=(_ocr(engine,frame,(311,130,33,23)),_ocr(engine,frame,(467,130,33,23)))
 kinds=(_part_name(engine,frame,(404,128,38,22)),_part_name(engine,frame,(559,128,39,22)))
 buttons=(_ocr(engine,frame,(370,350,72,26)),_ocr(engine,frame,(526,350,72,26)))
 if any(grade not in ('일반','희귀','영웅') for grade in grades):raise Hold('장비 등급 글자 확인 필요')
 if kinds[0]!=kinds[1] or kinds[0] not in PART_MAP:raise Hold('같은 부위 장비 확인 필요')
 if buttons!=('장착해제','장착'):raise Hold('착용 중/후보 버튼 확인 필요')
 if worn<.96 and not (grades[0]=='일반' and comparison_shell(frame)):
  raise Hold('착용 표시 확인 필요')
 left_icon=frame[128:148,356:376].copy();right_icon=frame[128:148,511:531].copy()
 return {'slot':PART_MAP[kinds[0]],'current_grade':grades[0],'candidate_grade':grades[1],
         'current_item':_item_token(frame[97:115,313:425],left_icon),
         'candidate_item':_item_token(frame[97:115,468:568],right_icon),
         'target_bounds':[527,351,598,376]}

def worn_detail_frame(frame,engine):
 """Read the observed single equipped-weapon tooltip; no input."""
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:raise Hold('장착 장비 상세 확인 필요')
 if _score(frame[116:135,420:445],badge())<.96:raise Hold('장착 표시 확인 필요')
 grade=_ocr(engine,frame,(390,130,35,23));kind=_part_name(engine,frame,(483,128,33,22));button=_ocr(engine,frame,(450,350,70,26))
 if grade not in ('일반','희귀','영웅') or kind not in PART_MAP or button!='장착해제':raise Hold('장착 부위·등급·버튼 확인 필요')
 return {'slot':PART_MAP[kind],'grade':grade,'item':_item_token(frame[97:115,390:502],frame[128:148,434:454].copy())}

def _part_name(engine,frame,box):
 """The glyph 찌 reads near .70 and sometimes as 짜. Only an exact part name passes the caller's check."""
 text=_ocr(engine,frame,box,minimum=.60)
 return '팔찌' if text=='팔짜' else text

def initial_candidate_frame(frame,engine):
 """Single un-worn tooltip; blank slot must be proved separately."""
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:raise Hold('초기 장비 상세 확인 필요')
 if _score(frame[116:135,420:445],badge())>=.90:raise Hold('이미 착용한 장비')
 grade=_ocr(engine,frame,(390,130,35,23));kind=_part_name(engine,frame,(483,128,33,22));button=_ocr(engine,frame,(450,350,70,26))
 if grade not in ('일반','희귀','영웅') or kind not in PART_MAP or button!='장착':raise Hold('초기 장비 부위·등급·장착 버튼 확인 필요')
 return {'slot':PART_MAP[kind],'candidate_grade':grade,
         'candidate_item':_item_token(frame[97:115,390:502],frame[128:148,434:454].copy()),
         'target_bounds':[449,351,519,376]}

def already_worn_frame(frame,engine):
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return False
 if _score(frame[116:135,420:445],badge())<.96:return False
 try:return _ocr(engine,frame,(450,350,70,26))=='장착해제'
 except Hold:return False

def same_item(one,two):
 """Compare title foreground plus rendered item icon across tooltip layouts."""
 try:
  a,b=json.loads(one),json.loads(two)
  def title(v):
   shape=tuple(v['title_shape']);data=base64.b64decode(v['title_mask'],validate=True)
   if len(shape)!=2 or not 1<=shape[0]<=18 or not 1<=shape[1]<=112:return None
   return np.frombuffer(data,dtype=np.uint8).reshape(shape)>0
  def icon(v):return np.frombuffer(base64.b64decode(v['icon_rgb'],validate=True),dtype=np.uint8).reshape((20,20,3))
  x,y=title(a),title(b)
  ia,ib=icon(a),icon(b)
  aligned=(_score(ia,ib)>=.97 or (_score(ia,ib[2:18,2:18])>=.97 and _score(ib,ia[2:18,2:18])>=.97))
  if x is None or y is None or not aligned:return False
  if x.shape==y.shape:
   union=np.logical_or(x,y).sum()
   if union and np.logical_and(x,y).sum()/union>=.92:return True
  # Long item names scroll horizontally. Two positive views must share a
  # substantial identical name core, not merely an icon/type or a blank phase.
  # Short complete names still use the exact-shape path above.
  for dy in range(-2,3):
   ya,yb=max(0,dy),max(0,-dy);height=min(x.shape[0]-ya,y.shape[0]-yb)
   if height<7:continue
   for dx in range(-y.shape[1]+24,x.shape[1]-23):
    xa,xb=max(0,dx),max(0,-dx);width=min(x.shape[1]-xa,y.shape[1]-xb)
    if width<32 and width<.8*min(x.shape[1],y.shape[1]):continue
    p=x[ya:ya+height,xa:xa+width];q=y[yb:yb+height,xb:xb+width]
    union=np.logical_or(p,q).sum()
    overlap=np.logical_and(p,q).sum()
    if union>=30 and overlap/union>=.97:return True
    # Native marquee rasterization moves subpixel antialias edges between
    # comparison/single panes. Permit ONLY a one-pixel boundary difference,
    # with nearly all strokes identical in at least one direction. This is
    # not a low-confidence OCR/name-only fallback; both icons still need.97.
    if union>=40 and min(p.sum(),q.sum())>=30:
     ratios=(overlap/p.sum(),overlap/q.sum())
     if max(ratios)>=.95 and min(ratios)>=.85:
      dp=cv2.distanceTransform((~p).astype(np.uint8),cv2.DIST_C,3)
      dq=cv2.distanceTransform((~q).astype(np.uint8),cv2.DIST_C,3)
      if dp[q].max()<=1 and dq[p].max()<=1:return True
  return False
 except (ValueError,TypeError,KeyError):return False

def compare_pair(first,second,engine,character,ticks,*,clock=time.monotonic,defer_freshness=False):
 if first is second or not isinstance(first,np.ndarray) or not isinstance(second,np.ndarray) or np.shares_memory(first,second):raise Hold('서로 다른 두 화면 필요')
 if not isinstance(character,str) or not character.strip() or not isinstance(ticks,(tuple,list)) or len(ticks)!=2:raise Hold('캐릭터·화면 시각 확인 필요')
 a=compare_frame(first,engine);b=compare_frame(second,engine)
 fixed=('slot','current_grade','candidate_grade','target_bounds')
 if any(a[k]!=b[k] for k in fixed) or not all(same_item(a[k],b[k]) for k in ('current_item','candidate_item')):raise Hold('장비 비교 두 화면 불일치')
 now=clock()
 if any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in ticks) or ticks[1]<=ticks[0]:raise Hold('장비 비교 화면 시각 확인 필요')
 if not defer_freshness and any(not 0<=now-t<=2 for t in ticks):raise Hold('장비 비교 화면 판독 지연')
 out=[]
 for frame,tick in zip((first,second),ticks):
  row=dict(a,verified=True,character=character,captured_at=tick,
           observed_current_item=(a if frame is first else b)['current_item'],
           observed_candidate_item=(a if frame is first else b)['candidate_item'],identity_core_verified=True)
  row['frame_id']=hashlib.sha256(frame.tobytes()+repr(tick).encode()).hexdigest();out.append(row)
 return tuple(out)

@lru_cache(maxsize=1)
def comparison_right_close():
 return np.asarray(Image.open(ASSET.with_name('comparison-right-close.png')).convert('RGB')).min(axis=2)>190

def comparison_shell(frame):
 """Two exact original X glyphs; no assumption that normal gear has E."""
 from owner_energy_box_detail_candidate import asset
 from owner_progression import inventory_parts
 if getattr(frame,'shape',None)!=(479,897,3) or inventory_parts(frame)!=(True,True):return False
 expected=asset('detail-close').min(axis=2)>190
 right=comparison_right_close()
 left_actual=frame[99:112,424:440].min(axis=2)>190;right_actual=frame[99:112,580:596].min(axis=2)>190
 return bool(expected.sum()>=8 and right.sum()>=8 and np.array_equal(left_actual,expected)
             and (np.array_equal(right_actual,expected) or np.array_equal(right_actual,right)))

def _same_white_anchors(a,b,boxes):
 for x1,y1,x2,y2 in boxes:
  left=a[y1:y2,x1:x2].min(axis=2)>170;right=b[y1:y2,x1:x2].min(axis=2)>170
  if left.sum()<8 or not np.array_equal(left,right):return False
 return True

def _same_anchors(a,b):
 # Immediately before input, require all title/grade/type/icon/button pixels
 # from the last verified comparison. Background/game motion is irrelevant.
 # Moving title strips are independently revalidated by same_item. All other
 # input anchors remain exact, including grade/type/icon/worn badge/buttons.
 boxes=((300,115,443,155),(455,115,598,155),(369,350,442,377),(526,350,599,377))
 if all(np.array_equal(a[y1:y2,x1:x2],b[y1:y2,x1:x2]) for x1,y1,x2,y2 in boxes):return True
 if not comparison_shell(a) or not comparison_shell(b) or not _same_white_anchors(a,b,boxes):return False
 try:
  return all(same_item(_item_token(a[y1:y2,x1:x2],a[iy:iy+20,ix:ix+20].copy()),
                            _item_token(b[y1:y2,x1:x2],b[iy:iy+20,ix:ix+20].copy()))
             for x1,y1,x2,y2,ix,iy in ((313,97,425,115,356,128),(468,97,568,115,511,128)))
 except Hold:return False

def _same_single_anchors(a,b):
 boxes=((375,115,520,155),(449,350,519,377))
 if all(np.array_equal(a[y1:y2,x1:x2],b[y1:y2,x1:x2]) for x1,y1,x2,y2 in boxes):return True
 if not single_shell(a) or not single_shell(b) or not _same_white_anchors(a,b,boxes):return False
 try:return same_item(_item_token(a[97:115,390:502],a[128:148,434:454].copy()),
                      _item_token(b[97:115,390:502],b[128:148,434:454].copy()))
 except Hold:return False

def single_shell(frame):
 from owner_energy_box_detail_candidate import asset
 from owner_progression import inventory_parts
 if getattr(frame,'shape',None)!=(479,897,3) or inventory_parts(frame)!=(True,True):return False
 actual=frame[99:112,502:518].min(axis=2)>190
 return bool(np.array_equal(actual,asset('detail-close').min(axis=2)>190) or np.array_equal(actual,comparison_right_close()))

def grade_text_matches(proof,frame,engine):
 """Final equip permission reads names of grades, never a rarity color."""
 try:
  if proof.get('empty') is True:return _ocr(engine,frame,(390,130,35,23))==proof.get('candidate_grade')
  return (_ocr(engine,frame,(311,130,33,23))==proof.get('current_grade')
          and _ocr(engine,frame,(467,130,33,23))==proof.get('candidate_grade'))
 except (Hold,AttributeError,TypeError):return False

def comparison_item_proof(proof,frame):
 try:
  return (same_item(proof['current_item'],_item_token(frame[97:115,313:425],frame[128:148,356:376].copy()))
      and same_item(proof['candidate_item'],_item_token(frame[97:115,468:568],frame[128:148,511:531].copy())))
 except (Hold,KeyError):return False

def same_comparison_for_close(first,second):
 """Navigation only: unchanged known panes/items, ignoring enhancement glow."""
 if _same_anchors(first,second):return True
 if not comparison_shell(first) or not comparison_shell(second):return False
 if not _same_white_anchors(first,second,((369,350,442,377),(526,350,599,377))):return False
 for frame in (first,second):
  if _score(frame[116:135,345:365],badge())<.96 or _score(frame[116:135,500:520],badge())>=.90:return False
 try:
  proof={'current_item':_item_token(first[97:115,313:425],first[128:148,356:376].copy()),
         'candidate_item':_item_token(first[97:115,468:568],first[128:148,511:531].copy())}
  return comparison_item_proof(proof,second)
 except Hold:return False

def single_item_proof(token,frame):
 try:return same_item(token,_item_token(frame[97:115,390:502],frame[128:148,434:454].copy()))
 except Hold:return False

def ready_hit(detector,frame,excluded):
 """Reuse native masked marker; skip already inspected nearby candidates."""
 from project_adapter import market_inventory as native
 from roi_runtime import _match_ccoeff_normed_masked
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return None
 area=detector.entries.get('범위_인벤토리');needle=detector.templates.get(native.EQUIP_READY)
 if not isinstance(area,dict) or needle is None:return None
 x,y,w,h=(area[k] for k in ('x','y','w','h'));image=frame[y:y+h,x:x+w,::-1].copy()
 if image.shape[0]<needle.shape[0] or image.shape[1]<needle.shape[1]:return None
 mask=detector.masks.get(native.EQUIP_READY)
 values=cv2.matchTemplate(image,needle,cv2.TM_CCOEFF_NORMED) if mask is None else _match_ccoeff_normed_masked(image,needle,mask)
 ys,xs=np.where(np.isfinite(values)&(values>=.97));nh,nw=needle.shape[:2]
 for j in np.lexsort((xs,ys)):
  left,top=x+int(xs[j]),y+int(ys[j]);bounds=(left,top,left+nw,top+nh)
  if any(abs(left-old[0])<=max(nw,nh) and abs(top-old[1])<=max(nw,nh) for old in excluded):continue
  return (left+nw//2,top+nh//2,bounds)
 return None

def inventory_slots(detector,frame):
 """Classify visible normal-inventory cells using native grid and empty art.

 Low-contrast or uncertain cells stay unknown; they are not called empty.
 This function does not distinguish gear from other item categories.
 """
 from project_adapter import market_inventory as native
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:raise Hold('인벤토리 프레임 확인 필요')
 area=detector.entries.get('범위_인벤토리');empty=detector.entries.get(native.EMPTY);needle=detector.templates.get(native.EMPTY)
 if not isinstance(area,dict) or not isinstance(empty,dict) or needle is None:raise Hold('인벤토리 슬롯 기준 확인 필요')
 boxes=native.compute_slot_rects(tuple(area[k] for k in ('x','y','w','h')),tuple(empty[k] for k in ('x','y','w','h')),cols=4)
 result=[];gear_tab=equipment_tab_selected(frame)
 for slot in boxes:
  x,y,w,h=(slot[k] for k in ('cell_x','cell_y','cell_w','cell_h'))
  crop=frame[y:y+h,x:x+w,::-1].copy()
  if crop.shape!=(h,w,3) or h<needle.shape[0] or w<needle.shape[1]:raise Hold('인벤토리 슬롯 범위 오류')
  score=cv2.matchTemplate(crop,needle,cv2.TM_CCOEFF_NORMED)
  maximum=float(np.where(np.isfinite(score),score,-1).max())
  # The standard EMPTY asset uses a different panel. In the observed gear
  # tab, independently verified blank cells have a low-variance dark centre;
  # apply that classifier only while the gear tab is positively selected.
  core=frame[y+5:y+h-5,x+5:x+w-5]
  means=core.mean(axis=(0,1)) if core.size else (0,0,0)
  observed_blank=(gear_tab and core.size>0 and float(core.std())<6
                  and 42<=means[0]<=58 and 40<=means[1]<=54 and 38<=means[2]<=52)
  state='empty' if maximum>=.97 or observed_blank else ('occupied' if float(crop.std())>=20 else 'unknown')
  cx,cy=native._click_xy(slot)
  if not x<=cx<x+w or not y<=cy<y+h:raise Hold('인벤토리 슬롯 좌표 오류')
  result.append((state,(cx,cy,(x,y,x+w,y+h))))
 return result

def equipment_tab_selected(frame):
 """Observed gear-tab highlight, independently contrasted with all-items."""
 from owner_progression import inventory_parts
 if not isinstance(frame,np.ndarray) or frame.shape!=(479,897,3) or frame.dtype!=np.uint8:return False
 if inventory_parts(frame)!=(True,True):return False
 gear=int((frame[125:140,872:887].min(axis=2)>170).sum())
 all_items=int((frame[96:111,872:887].min(axis=2)>170).sum())
 return gear>=50 and all_items<=10

def same_inventory_cell(first,second,bounds):
 x1,y1,x2,y2=bounds
 delta=np.abs(first[y1:y2,x1:x2].astype(np.int16)-second[y1:y2,x1:x2].astype(np.int16))
 if not delta.size:return False
 if float(delta.mean())<=.35:return True
 a=first[y1+8:y1+24,x1+8:x1+24];b=second[y1+8:y1+24,x1+8:x1+24]
 if a.shape!=(16,16,3) or b.shape!=a.shape:return False
 if float(np.abs(a.astype(np.int16)-b.astype(np.int16)).mean())>.35:return False
 border=np.abs(first[y1:y2,x1:x1+3].astype(np.int16)-second[y1:y2,x1:x1+3].astype(np.int16))
 return bool(border.size and float(border.mean())<=.35)

def retain_rejected_cells(detector,first,second,excluded):
 """A change in an unseen cell cannot reset already rejected candidates.

 A genuine sort/drop clears only exclusions whose own original cell changed.
 Every following inspection/commit still proves the fresh item independently.
 """
 try:
  before={tuple(hit[2]):state for state,hit in inventory_slots(detector,first)}
  current={tuple(hit[2]):state for state,hit in inventory_slots(detector,second)}
 except (Hold,AttributeError,KeyError,TypeError):return []
 return [bounds for bounds in excluded if before.get(tuple(bounds))==current.get(tuple(bounds))=='occupied'
         and same_inventory_cell(first,second,tuple(bounds))]

def same_equipment_inventory(detector,first,second):
 """Reject changed cells while tolerating observed background animation."""
 if not equipment_tab_selected(first) or not equipment_tab_selected(second):return False
 a=inventory_slots(detector,first);b=inventory_slots(detector,second)
 if len(a)!=len(b):return False
 for (sa,ha),(sb,hb) in zip(a,b):
  if sa!=sb or ha!=hb:return False
  if not same_inventory_cell(first,second,ha[2]):return False
 return True

class Port:
 """Execute a single already-open tooltip on its existing input worker.

 No new native worker, no menu discovery, no starter automatic install. The
 caller must provide current observed character and a fresh identity guard.
 """
 def __init__(self,service,context,character,engine,identity_guard):
  self.service=service;self.context=context;self.character=character;self.engine=engine;self.identity_guard=identity_guard
  self.journal=Journal(service.adapter.project.root,character);self.last=None;self.before_inventory=None
  self.display_profile=character.rsplit('|',1)[0]
 def _frame(self):
  self.context.checkpoint();self.service.check()
  if self.identity_guard() is not True:raise Hold('캐릭터·설정 확인 필요')
  frame=self.service.capture().copy();return frame,time.monotonic()
 def cached_non_general_parts(self,first,second):
  """Retain candidate name hints; color alone cannot skip a worn part."""
  data=self.journal.read();catalog=data.get('candidate_catalog',{})
  self._candidate_catalog=catalog if isinstance(catalog,dict) else {}
  return set()
 def known_candidate_part(self,frame,hit):
  x,y,r,b=hit[2];cx,cy=x+8,y+8;core=frame[cy:cy+18,cx:cx+18]
  if core.shape!=(18,18,3):return None
  parts=set()
  for item in getattr(self,'_candidate_catalog',{}).values():
   if not isinstance(item,dict) or item.get('slot') not in SLOTS:continue
   try:ref=np.frombuffer(base64.b64decode(item['icon_rgb'],validate=True),np.uint8).reshape((20,20,3))
   except (ValueError,TypeError,KeyError):continue
   if _score(core,ref[2:18,2:18])>=.97:parts.add(item['slot'])
  return next(iter(parts)) if len(parts)==1 else None
 def select_equipment_tab(self):
  from owner_progression import inventory_parts
  from project_adapter import market_inventory as native
  a,_=self._frame();self.context.wait(.12);b,_=self._frame()
  if inventory_parts(a)!=(True,True) or inventory_parts(b)!=(True,True):raise Hold('장비탭 진입 전 인벤토리 미확인')
  x,y=equipment_tab_selected(a),equipment_tab_selected(b)
  if x and y:return 'already_selected'
  if x!=y:raise Hold('장비탭 전환 중')
  ha=self.service.detector.find(native.EQUIP_TAB,a,threshold=.95)
  hb=self.service.detector.find(native.EQUIP_TAB,b,threshold=.95)
  if not ha or ha!=hb:raise Hold('장비탭 버튼 확인 필요')
  final,_=self._frame()
  if self.service.detector.find(native.EQUIP_TAB,final,threshold=.95)!=hb:raise Hold('장비탭 입력 직전 변경')
  self.context.checkpoint();self.service.check();self.service.click_hit(hb)
  self.context.wait(.2);a,_=self._frame();self.context.wait(.12);b,_=self._frame()
  if not equipment_tab_selected(a) or not equipment_tab_selected(b):raise Hold('장비탭 선택 확인 필요')
  return 'selected'
 def open_candidate(self,excluded=()):
  """Open one visually occupied native-grid cell without an upgrade marker."""
  from project_adapter import market_inventory as native
  from owner_progression import inventory_parts
  skipped={tuple(x) for x in excluded}
  skipped_parts=set()
  def find(frame,preferred=None):
   if inventory_parts(frame)!=(True,True):return None
   if not equipment_tab_selected(frame):raise Hold('장비탭이 변경되어 장착 후보 확인을 보류합니다')
   occupied=[]
   for state,hit in inventory_slots(self.service.detector,frame):
    if tuple(hit[2]) in skipped or state=='empty':continue
    if state=='unknown':
     # An unreadable cell is neither empty nor a candidate. Preserve it
     # and inspect the other positively occupied cells on this visit.
     self.unknown_cells_held=True
     continue
    if self.known_candidate_part(frame,hit) in skipped_parts:continue
    occupied.append(hit)
   if preferred is not None:
    existing=next((hit for hit in occupied if tuple(hit[2])==tuple(preferred)),None)
    if existing:return existing
   # The moving green arrow is only a PRIORITY hint. An unmarked rare item
   # still gets inspected, and grade/part/identity are proved in its tooltip.
   green=ready_hit(self.service.detector,frame,()) if getattr(self.service.detector,'entries',None) else None
   if green and occupied:
    nearby=[hit for hit in occupied if abs(hit[0]-green[0])<=38 and abs(hit[1]-green[1])<=38]
    if nearby:return min(nearby,key=lambda hit:(hit[0]-green[0])**2+(hit[1]-green[1])**2)
   return occupied[0] if occupied else None
  a,_=self._frame();self.context.wait(.12);b,_=self._frame()
  if equipment_tab_selected(a) and equipment_tab_selected(b):skipped_parts=self.cached_non_general_parts(a,b)
  first=find(a);second=find(b,first[2] if first else None)
  if inventory_parts(a)!=(True,True) or inventory_parts(b)!=(True,True):raise Hold('장비 인벤토리 화면 확인 필요')
  if first is None and second is None:return None
  if not first or first!=second:raise Hold('장착 후보 두 화면 확인 필요')
  self.before_inventory=(a,b)
  final,_=self._frame()
  if find(final,second[2])!=second:raise Hold('장착 후보 선택 직전 변경')
  self.context.checkpoint();self.service.check()
  if self.identity_guard() is not True:raise Hold('장비 후보 선택 전 캐릭터 변경')
  self.service.click_hit(second)
  self.context.wait(.25)
  # Opening this screen is not proof of either item's grade or slot.
  return second
 def read_pair(self):
  a,t1=self._frame();self.context.wait(.12);b,t2=self._frame()
  # A known marquee may be momentarily blank. Wait for actual name evidence;
  # never replace it with a cached title or an assumed item name.
  end=time.monotonic()+4
  waiting_name=False
  while time.monotonic()<end:
   try:
    for f in (a,b):
     for title,icon in ((f[97:115,313:425],f[128:148,356:376].copy()),(f[97:115,468:568],f[128:148,511:531].copy())):
      token=json.loads(_item_token(title,icon))
      if token.get('title_edge') and token['title_shape'][1]<32:raise Hold('장비 이름 스크롤 부분 확인 중')
    waiting_name=False;break
   except Hold:
    if not all(_score(f[116:135,345:365],badge())>=.96 or comparison_shell(f) for f in (a,b)):break
    waiting_name=True
    self.context.wait(.12);a,t1=b,t2;b,t2=self._frame()
  if waiting_name:raise Hold('장비 이름 스크롤 확인 보류')
  try:
   # OCR may take longer than the input freshness window, especially on the
   # first real crop. Parse the original pair, then obtain fresh independent
   # frames and prove that every input-relevant anchor is still identical.
   rows=compare_pair(a,b,self.engine,self.character,(t1,t2),defer_freshness=True)
   c,t3=self._frame();self.context.wait(.12);d,t4=self._frame()
   if (not _same_anchors(b,c) or not _same_anchors(c,d)
       or not comparison_item_proof(rows[1],c) or not comparison_item_proof(rows[1],d)):raise Hold('장비 판독 중 비교창 변경')
   if not 0<=time.monotonic()-t3<=2 or not t3<t4:raise Hold('장비 비교 화면 재확인 지연')
   rows=tuple(dict(row,captured_at=t,frame_id=hashlib.sha256(frame.tobytes()+repr(t).encode()).hexdigest())
              for row,frame,t in zip(rows,(c,d),(t3,t4)))
   b,t2=d,t4
  except Hold:
   if self.before_inventory is None:raise
   # A known comparison with a different weapon kind is not a single-item
   # empty-slot dialog. Close it through the paired known-shell path below.
   if comparison_shell(a) or comparison_shell(b):raise
   if already_worn_frame(a,self.engine) and already_worn_frame(b,self.engine) and _same_single_anchors(a,b):
    self.last_worn=b;self.last=(b,t2,{'already_worn':True});return None
   from owner_equipment_boxes import agree
   first=initial_candidate_frame(a,self.engine);second=initial_candidate_frame(b,self.engine)
   if any(first[k]!=second[k] for k in ('slot','candidate_grade','target_bounds')) or not same_item(first['candidate_item'],second['candidate_item']):raise Hold('초기 장비 두 화면 불일치')
   if agree(*self.before_inventory).get(first['slot']) is not False:raise Hold('해당 슬롯이 빈 상태인지 확인 필요')
   c,t3=self._frame();self.context.wait(.12);d,t4=self._frame()
   if (not _same_single_anchors(b,c) or not _same_single_anchors(c,d)
       or not single_item_proof(first['candidate_item'],c) or not single_item_proof(first['candidate_item'],d)):raise Hold('초기 장비 판독 중 화면 변경')
   a,t1,b,t2=c,t3,d,t4
   now=time.monotonic()
   if not 0<=now-t1<=2 or not 0<=now-t2<=2 or t2<=t1:raise Hold('초기 장비 판독 지연')
   rows=tuple(dict(first,verified=True,character=self.character,empty=True,captured_at=t,
                   frame_id=hashlib.sha256(frame.tobytes()+repr(t).encode()).hexdigest()) for frame,t in ((a,t1),(b,t2)))
  self.journal.remember_pair(*rows)
  self.last=(b,t2,rows[1]);return rows
 def final(self,proof):
  frame,tick=self._frame()
  if self.last is None or tick-self.last[1]>2:return False
  same=_same_single_anchors if self.last[2].get('empty') is True else _same_anchors
  if not same(frame,self.last[0]):return False
  if self.last[2].get('empty') is True:
   if not single_item_proof(proof.get('candidate_item'),frame):return False
  elif not comparison_item_proof(proof,frame):return False
  initial=self.last[2].get('empty') is True
  if not grade_text_matches(dict(proof,empty=initial),frame,self.engine):return False
  # OCR may be slow. Prove the same independently read item and controls
  # again on a new frame before giving the caller permission to equip.
  fresh,now=self._frame()
  if not 0<=now-tick<=2 or not same(frame,fresh):return False
  if initial:
   if not single_item_proof(proof.get('candidate_item'),fresh):return False
  elif not comparison_item_proof(proof,fresh):return False
  return all(proof.get(k)==self.last[2].get(k) for k in ('character','slot','current_item','candidate_item','target_bounds'))
 def click(self,bounds):
  x1,y1,x2,y2=bounds
  self.context.checkpoint();self.service.check()
  if self.identity_guard() is not True:raise Hold('장착 직전 캐릭터 변경')
  self.service.click_hit(((x1+x2)//2,(y1+y2)//2,tuple(bounds)))
 def try_comparison(self):
  rows=self.read_pair()
  if rows is None:return 'already_worn'
  initial=rows[0].get('empty') is True
  allowed={(rows[0]['slot'],rows[0]['candidate_item'])} if initial else None
  return run_once(self.context,self.journal,lambda:rows,self.final,self.click,initial_allowed=allowed)
 def close_comparison(self):
  """Dismiss only the last positively identified, unchanged right tooltip."""
  frame,_=self._frame()
  if self.last is None:raise Hold('장비 비교창 종료 위치 확인 필요')
  initial=self.last[2].get('empty') is True;same=_same_single_anchors if initial else _same_anchors
  if not same(frame,self.last[0]):raise Hold('장비 비교창 종료 위치 확인 필요')
  self.context.checkpoint();self.service.check()
  self.service.click_hit((510,106,(503,99,517,113)) if initial else (588,106,(581,99,595,113)))
  from owner_progression import inventory_parts
  def inventory_only(frame):
   return (inventory_parts(frame)==(True,True)
           and _score(frame[116:135,345:365],badge())<.90
           and _score(frame[116:135,420:445],badge())<.90
           and not same(frame,self.last[0]))
  self.context.wait(.2);after,_=self._frame();self.context.wait(.12);after2,_=self._frame()
  if not inventory_only(after) or not inventory_only(after2):raise Hold('장비 비교창 종료 후 인벤토리 상태 미확인')
  self.last=None
  return 'inventory_restored'
 def close_unresolved_known(self):
  """Close a known paired tooltip without treating its unread grade as valid."""
  from owner_progression import inventory_parts
  a,_=self._frame();self.context.wait(.12);b,_=self._frame()
  from owner_worn_stats import popup
  from owner_energy_box_detail_candidate import close_mark
  # One X at this spot: a worn-item detail, or an unworn item on a blank slot.
  def single(frame):return popup(frame) or (inventory_parts(frame)==(True,True) and close_mark(frame) and not comparison_shell(frame))
  if single(a) and single(b):
   # It has only one X and nothing to equip; same close as the start menu's.
   final,_=self._frame()
   if not single(final):raise Hold('장비창 종료 전 화면 변경')
   self.context.checkpoint();self.service.check();self.service.click_hit((510,106,(503,99,518,113)))
   self.context.wait(.2);x,_=self._frame();self.context.wait(.12);y,_=self._frame()
   if single(x) or single(y) or inventory_parts(x)!=(True,True) or inventory_parts(y)!=(True,True):raise Hold('장비창 종료 후 인벤토리 미확인')
   return 'inventory_restored'
  # The clicked cell opened nothing (an empty cell read as occupied after a scroll). Nothing to close.
  if all(inventory_parts(f)==(True,True) and not close_mark(f) and not comparison_shell(f) and _score(f[116:135,345:365],badge())<.90 and _score(f[116:135,420:445],badge())<.90 for f in (a,b)):
   return 'inventory_restored'
  if not same_comparison_for_close(a,b):raise Hold('판독 불가 장비창 형태 확인 필요')
  for frame in (a,b):
   worn_mark=_score(frame[116:135,345:365],badge())>=.96
   normal_shell=not worn_mark and comparison_shell(frame) and _ocr(self.engine,frame,(311,130,33,23))=='일반'
   if ((not worn_mark and not normal_shell) or
       _score(frame[116:135,500:520],badge())>=.90 or
       _ocr(self.engine,frame,(370,350,72,26))!='장착해제' or
       _ocr(self.engine,frame,(526,350,72,26))!='장착'):
    raise Hold('판독 불가 장비창 종료 위치 확인 필요')
  final,_=self._frame()
  if not same_comparison_for_close(b,final):raise Hold('장비창 종료 전 화면 변경')
  self.context.checkpoint();self.service.check();self.service.click_hit((588,106,(581,99,595,113)))
  self.context.wait(.2);x,_=self._frame();self.context.wait(.12);y,_=self._frame()
  if inventory_parts(x)!=(True,True) or inventory_parts(y)!=(True,True) or not equipment_tab_selected(x) or not equipment_tab_selected(y):raise Hold('장비창 종료 후 인벤토리 미확인')
  return 'inventory_restored'
 def confirm_worn_detail(self):
  """Confirm after a caller has visibly opened the observed worn detail."""
  pending=self.journal.read()['pending']
  if not pending or pending.get('phase')!='sent':raise Hold('확인할 장비 교체 기록 없음')
  proof=pending['proof']
  evidence=[]
  def result():
   a,t1=self._frame();self.context.wait(.12);b,t2=self._frame()
   one=worn_detail_frame(a,self.engine);two=worn_detail_frame(b,self.engine)
   if one['slot']!=two['slot'] or one['grade']!=two['grade'] or not same_item(one['item'],two['item']):raise Hold('장착 결과 두 화면 불일치')
   if not same_item(one['item'],proof['candidate_item']) or not same_item(two['item'],proof['candidate_item']):
    raise Hold('장착된 장비 이름·아이콘이 실제 선택 후보와 다릅니다')
   c,t3=self._frame();self.context.wait(.12);d,t4=self._frame()
   if (not _same_single_anchors(b,c) or not _same_single_anchors(c,d)
       or not single_item_proof(proof['candidate_item'],c) or not single_item_proof(proof['candidate_item'],d)):raise Hold('착용 결과 판독 중 화면 변경')
   evidence.append(d)
   rows=[]
   for frame,tick,value in ((c,t3,one),(d,t4,two)):
    rows.append({'verified':True,'character':self.character,'slot':value['slot'],'item':proof['candidate_item'],
                 'observed_item':value['item'],'same_item_verified':True,
                 'grade':value['grade'],'worn':True,'captured_at':tick,
                 'frame_id':hashlib.sha256(frame.tobytes()+repr(tick).encode()).hexdigest()})
   return tuple(rows)
  result=confirm(self.context,self.journal,result)
  self.last_worn=evidence[-1]
  if proof.get('current_item'):
   from owner_growth_current import invalidate_item
   invalidate_item(self.service.adapter.project.root,self.display_profile,proof['current_item'],grade=proof.get('current_grade','일반'))
  return result
 def open_worn_for_confirmation(self):
  """Open only the already-worn slot named in the pending record."""
  from owner_progression import inventory_parts
  from owner_equipment_boxes import agree,SLOTS
  pending=self.journal.read()['pending']
  if not pending or pending.get('phase')!='sent':raise Hold('확인할 장비 교체 기록 없음')
  slot=pending['proof']['slot'];bounds=SLOTS.get(slot)
  if bounds is None:raise Hold('장착 슬롯 위치 확인 필요')
  x,y,w,h=bounds
  # The worn mark and the power toast animate for a moment right after equipping.
  end=time.monotonic()+4
  while True:
   a,_=self._frame();self.context.wait(.12);b,_=self._frame()
   if (inventory_parts(a)==(True,True) and inventory_parts(b)==(True,True) and agree(a,b).get(slot) is True
       and np.array_equal(a[y:y+h,x:x+w],b[y:y+h,x:x+w])):break
   if time.monotonic()>=end:raise Hold('장착 슬롯 확인 필요')
   self.context.wait(.25)
  final,_=self._frame()
  if inventory_parts(final)!=(True,True) or not np.array_equal(b[y:y+h,x:x+w],final[y:y+h,x:x+w]):raise Hold('장착 슬롯 재확인 필요')
  self.context.checkpoint();self.service.check()
  self.service.click_hit((x+w//2,y+h//2,(x,y,x+w,y+h)));self.context.wait(.25)
 def close_worn_detail(self):
  frame,_=self._frame();known=getattr(self,'last_worn',None)
  if known is None:raise Hold('착용 상세 종료 위치 확인 필요')
  if not _same_single_anchors(frame,known):
   def same_worn(f):
    # Long names scroll, so the title cannot prove sameness here. Closing any worn detail through
    # its one X changes nothing, and the worn mark and 장착해제 button prove that is what is open.
    try:return (single_shell(f) and _score(f[116:135,420:445],badge())>=.96
      and _ocr(self.engine,f,(450,350,70,26))=='장착해제')
    except Hold:return False
   self.context.wait(.12);other,_=self._frame()
   if not same_worn(frame) or not same_worn(other):raise Hold('착용 상세 종료 위치 확인 필요')
  self.context.checkpoint();self.service.check();self.service.click_hit((510,106,(503,99,517,113)))
  from owner_progression import inventory_parts
  self.context.wait(.2);a,_=self._frame();self.context.wait(.12);b,_=self._frame()
  if (inventory_parts(a)!=(True,True) or inventory_parts(b)!=(True,True)
      or _same_single_anchors(a,known) or _same_single_anchors(b,known)):raise Hold('착용 상세 종료 후 인벤토리 미확인')
  self.last_worn=None;self.last=None;return 'inventory_restored'

 def scroll_page(self):
  """Scroll only a proved bare equipment inventory; return actual movement."""
  ui=getattr(self,'scroll_ui',None)
  if ui is None:return False
  from owner_progression import inventory_parts
  def bare(frame):
   return (self.identity_guard() is True and inventory_parts(frame)==(True,True) and equipment_tab_selected(frame)
     and all(_score(frame[116:135,l:r],badge())<.90 for l,r in ((345,365),(420,445),(500,520))))
  # A tooltip that just closed and the moving upgrade arrow can differ between two frames.
  end=time.monotonic()+3
  while True:
   before,_=self._frame();self.context.wait(.12);other,_=self._frame()
   if bare(before) and bare(other) and same_equipment_inventory(self.service.detector,before,other):break
   if time.monotonic()>=end:raise Hold('장비 목록 스크롤 전 화면 확인 필요')
   self.context.wait(.25)
  area=self.service.detector.entries.get('범위_인벤토리')
  if not isinstance(area,dict):raise Hold('장비 목록 범위 확인 필요')
  x,y,w,h=(area[k] for k in ('x','y','w','h'));cx=x+w//2
  ui.drag((cx,y+h-35),(cx,y+35),bare);self.context.wait(.2)
  # The list keeps gliding after a drag, so give it a moment to settle.
  end=time.monotonic()+3
  while True:
   after,_=self._frame();self.context.wait(.12);final,_=self._frame()
   if bare(after) and bare(final) and same_equipment_inventory(self.service.detector,after,final):break
   if time.monotonic()>=end:raise Hold('장비 목록 스크롤 후 화면 확인 필요')
   self.context.wait(.25)
  return not same_equipment_inventory(self.service.detector,other,final)

def run_in_open_inventory(adapter,context,inputs):
 """One existing-worker inventory visit; caller must handle every outcome.

 A verified rejection restores inventory. On sent/uncertain input, return
 pending and the caller must stop further navigation until it is reconciled.
 This entry point is not installed in the product automatically.
 """
 from owner_progression import state
 from owner_hunt_rules_candidate import configured_identity
 from project_adapter import market_inventory as native
 from project_adapter.town_services import TownServices
 from tools.ocr_support import get_paddle_engine
 progress=state(adapter);start=time.monotonic();profile=configured_identity(adapter.project.root)
 if not progress.character or not 0<=start-progress.observed<=180:raise Hold('최신 캐릭터 확인 필요')
 fingerprint=progress.character;character=profile+'|'+fingerprint
 def guard():
  p=state(adapter);age=time.monotonic()-p.observed
  return p.character==fingerprint and 0<=age<=180 and configured_identity(adapter.project.root)==profile
 service=TownServices(adapter,context,inputs,[*native.INVENTORY_USE_NAMES,native.EMPTY])
 journal=Journal(adapter.project.root,character)
 pending=journal.read()['pending']
 if pending is not None and pending.get('phase')=='prepared':journal.abort_prepared();pending=None
 engine=get_paddle_engine(adapter.project.root,language='korean')
 # Do not capture evidence until model initialization is ready; timeouts or
 # interruptions must never cause a background worker to issue game input.
 import threading
 done=threading.Event();errors=[]
 def warm():
  try:engine.predict(np.full((32,80,3),255,dtype=np.uint8))
  except Exception as exc:errors.append(exc)
  finally:done.set()
 threading.Thread(target=warm,name='gear-tooltip-ocr-warm',daemon=True).start()
 deadline=time.monotonic()+25
 while not done.is_set() and time.monotonic()<deadline:context.wait(.05);service.check()
 if not done.is_set() or errors:raise Hold('장비 OCR 준비 미완료')
 port=Port(service,context,character,engine,guard);port.display_profile=profile;port.select_equipment_tab();excluded=[]
 from owner_skill_ui import SkillUI
 port.scroll_ui=SkillUI(adapter,context,inputs)
 port.scroll_ui._owner_identity_guard=guard
 if pending is not None:
  if pending.get('phase')!='sent':raise Hold('이전 장비 교체 기록 상태 확인 필요')
  # Restore the exact worn slot and prove the requested candidate. No new
  # equip click is allowed while the previous operation is unresolved.
  port.open_worn_for_confirmation();port.confirm_worn_detail();port.close_worn_detail()
  adapter._owner_equipment_upgrade_growth_pending={'character':character,'at':time.monotonic()}
 initial,_=port._frame();context.wait(.12);other,_=port._frame()
 from owner_progression import inventory_parts
 if inventory_parts(initial)!=(True,True) or inventory_parts(other)!=(True,True):raise Hold('장비 인벤토리 확인 필요')
 # A tab transition or animated cell is a pre-input hold, not an equip
 # failure. Wait only on a changed view; normal stable visits pay no delay.
 deadline=time.monotonic()+2
 while not same_equipment_inventory(service.detector,initial,other):
  if time.monotonic()>=deadline:
   from owner_gear_hold_capture_candidate import enqueue
   enqueue(adapter.project.root,'equipment-preinput','장비 목록 두 화면 변경 · 장착 입력 없음',(initial,other))
   return 'preinput_inventory_unstable_skip'
  initial=other;context.wait(.15);other,_=port._frame()
  if not equipment_tab_selected(initial) or not equipment_tab_selected(other):raise Hold('장비탭 전환 후 화면 확인 필요')
 inventory=other.copy()
 pages=0;reordered=0;confirmed_count=0;deadline=time.monotonic()+90
 for _ in range(160):
  context.checkpoint();service.check()
  if time.monotonic()>=deadline:return 'confirmed' if confirmed_count else 'equipment_scan_partial'
  hit=port.open_candidate(excluded)
  if hit is None:
   scroll=getattr(port,'scroll_page',None)
   if pages<8 and callable(scroll) and scroll():
    pages+=1;excluded=[];inventory,_=port._frame();continue
   return 'confirmed' if confirmed_count else ('visible_unknown_cells_held' if getattr(port,'unknown_cells_held',False) else 'no_more_visible_candidates')
  try:status=port.try_comparison()
  except Hold:
   if port.journal.read()['pending'] is not None:raise Hold('장비 입력 결과 미확인 · 추가 조작 보류')
   if port.last is None:port.close_unresolved_known()
   else:port.close_comparison()
   excluded.append(tuple(hit[2]))
   current,_=port._frame()
   if not same_equipment_inventory(service.detector,inventory,current):
    # A drop/sort invalidates the old row exclusions. Re-read the new layout
    # instead of applying an old row number to a different inventory cell.
    if not equipment_tab_selected(current):raise Hold('장비 목록이 바뀌어 후보 순회 보류')
    retained=retain_rejected_cells(service.detector,inventory,current,excluded)
    if len(retained)<len(excluded):
     reordered+=1
     if reordered>2:
      from owner_gear_hold_capture_candidate import enqueue
      enqueue(adapter.project.root,'equipment-rescan','확인한 후보 칸 변경 반복 · 장착 입력 없음',(inventory,current))
      return 'confirmed' if confirmed_count else 'equipment_inventory_changed_partial'
    excluded=retained;inventory=current
   continue
  if status=='pending_confirmation':
   try:confirmed=port.confirm_worn_detail()
   except Hold:
    try:port.open_worn_for_confirmation()
    except Hold:return 'pending_confirmation'
    # Moving scenery behind the detail can fail one look. Every check passes on a still frame.
    confirmed=None
    for _ in range(4):
     try:confirmed=port.confirm_worn_detail();break
     except Hold:context.wait(.5)
    if confirmed is None:return 'pending_confirmation'
   port.close_worn_detail()
   adapter._owner_equipment_upgrade_growth_pending={'character':character,'at':time.monotonic()}
   confirmed_count+=1;excluded=[];inventory,_=port._frame()
   if confirmed_count>=len(SLOTS):return 'confirmed'
   continue
  if status=='already_worn':
   port.close_worn_detail();excluded.append(tuple(hit[2]))
   current,_=port._frame()
   if not same_equipment_inventory(service.detector,inventory,current):
    if not equipment_tab_selected(current):raise Hold('장비 목록이 바뀌어 후보 순회 보류')
    retained=retain_rejected_cells(service.detector,inventory,current,excluded)
    if len(retained)<len(excluded):
     reordered+=1
     if reordered>2:return 'confirmed' if confirmed_count else 'equipment_inventory_changed_partial'
    excluded=retained;inventory=current
   continue
  raise Hold('장비 교체 처리 상태 확인 필요')
 return 'confirmed' if confirmed_count else 'visible_candidate_limit'
