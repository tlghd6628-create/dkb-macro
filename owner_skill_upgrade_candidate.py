"""Same-worker skill breakthrough/awakening with durable result receipts.

Existing growth navigation, icon assets and paired OCR are reused. Unknown
stages/buttons/costs remain held. Saved-frame/fake-port checks are not a live
acceptance claim for an unobserved high-stage screen.
"""
import re,time,hashlib
import cv2,numpy as np
from owner_skill_goal import Pending

AWAKEN_STAGE=(355,127,74,20)
AWAKEN_RATIO=(370,389,50,25)
AWAKEN_PRICE=(339,435,60,30)
ACTION=(398,435,105,30)
BREAK_STAGE=(330,115,145,48)


def _g():
 import owner_skill_growth_candidate as g
 return g


def _text(row):return re.sub(r'\s+','',str(row.get('text','')))


def _one(rows,predicate,label):
 found=[r for r in rows if predicate(r)]
 if len(found)!=1:raise Pending('도술 '+label+' 두 화면 확인 필요')
 return found[0]


def _bounds(row):
 b=row.get('bounds')
 if not b or len(b)!=4:raise Pending('도술 판독 글자 위치 확인 필요')
 l,t,r,b=map(int,b)
 if not (0<=l<r<=897 and 0<=t<b<=479):raise Pending('도술 판독 글자 위치 변경')
 return l,t,r-l,b-t


def _blue_components(frame,box):
 x,y,w,h=box;crop=frame[y:y+h,x:x+w]
 hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV)
 mask=((hsv[:,:,0]>=85)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>110)&(hsv[:,:,2]>130)).astype('uint8')
 count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
 return [mask[y:y+h,x:x+w] for x,y,w,h,area in stats[1:] if area>=3]


def awaken_stage(frame):
 """Zero template, or one identical existing blue-star glyph on current side.

 The one-star mask comes from the observed NEXT side, never a generated
 success frame. Multiple or changed stars remain unknown until sampled.
 """
 g=_g()
 if not g.awakening_tab(frame):return None
 if g.awaken_zero_stage(frame):return 0
 from PIL import Image
 path=g.Path(__file__).parent/'skill_assets_candidate/awaken_zero_stage.png'
 if hashlib.sha256(path.read_bytes()).hexdigest()!='ca0893066d35099f4fe9aefd54a0762f2281e5cf0a7ebfa14728d3d045d390c0':return None
 source=np.asarray(Image.open(path).convert('RGB'))
 # The original saved template covers x355..429. Its rightmost blue star is
 # the observed first awakening glyph (10x10), with no current-side star.
 reference=_blue_components(source,(41,0,33,20))
 actual=_blue_components(frame,(355,127,41,20))
 label=(source[5:13,4:21].min(axis=2)>170).astype('uint8')
 current_label=(frame[127:147,355:396].min(axis=2)>170).astype('uint8')
 label_matches=cv2.matchTemplate(current_label,label,cv2.TM_SQDIFF)
 has_current_label=int((label_matches<.01).sum())==1
 if has_current_label and len(reference)==1 and len(actual)==1 and np.array_equal(reference[0],actual[0]):return 1
 return None


def parse_break_stage(rows):
 """Require explicit current/next breakthrough labels, not +50 alone."""
 text=''.join(_text(r) for r in rows if r.get('score',0)>=.98)
 pairs=[]
 for pattern in (r'(\d{1,3})돌파(?:[→>\-]+)?(\d{1,3})돌파',r'돌파(\d{1,3})(?:[→>\-]+)돌파(\d{1,3})'):
  for m in re.finditer(pattern,text):pairs.append(tuple(map(int,m.groups())))
 pairs=list(dict.fromkeys(pairs))
 if len(pairs)!=1 or pairs[0][1]!=pairs[0][0]+1:raise Pending('도술 현재·다음 돌파 단계 표시 확인 필요')
 return pairs[0]


def _bright_action(frame,point):
 x,y=point
 if not (320<=x<=503 and 435<=y<=465):return False
 # Style breakthrough reuses the same known bottom action region as style
 # enhancement, including its actually observed cursor-occlusion treatment.
 if _g().tab(frame) and _g().active(frame):return True
 crop=frame[max(435,y-4):min(464,y+5),max(320,x-20):min(503,x+21)]
 if crop.size==0:return False
 hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV)
 gold=(hsv[:,:,0]>=15)&(hsv[:,:,0]<=45)&(hsv[:,:,1]>50)&(hsv[:,:,2]>190)
 return float(gold.mean())>=.45


class SkillUpgradePort:
 """Read/action boundary for an already selected style or individual skill."""
 def __init__(self,ui,guard):self.ui=ui;self.guard=guard
 def observe(self,name,kind,*,need_quote=False):
  g=_g();ui=self.ui
  if not callable(getattr(ui,'rows_batch',None)):raise Pending('도술 각성·돌파 일괄 판독기 연결 필요')
  awaken=kind=='awaken'
  if kind not in ('awaken','breakthrough'):raise ValueError('도술 성장 종류 오류')
  exact=lambda r:r.get('score',0)>=.94 and _text(r)==re.sub(r'\s+','',name)
  specs=([((728,70,128,365),'korean',.94,'original',exact),((345,62,105,28),'korean',.94,'original',exact)]
   if awaken else [(g.LIST,'korean',.94,'original',lambda r:r.get('score',0)>=.94 and bool(re.fullmatch(re.escape(name)+r'\+50',_text(r)))),
    (BREAK_STAGE,'korean',.98)])
  base_count=len(specs)
  ratio=AWAKEN_RATIO if awaken else g.RATIO;price=AWAKEN_PRICE if awaken else g.PRICE
  if need_quote:specs.extend([(ratio,'number',.98,'original_or_clahe',None,g.numeric_pair_verifier('ratio')),(price,'number',.98),
   (g.BALANCE,'number',.90,'original_or_clahe',None,g.numeric_pair_verifier('balance',increasing=True)),(ACTION,'korean',.98)])
  answers=ui.rows_batch(specs);frames,ticks,_=ui._owner_last_rows_pair
  raw=getattr(ui,'_owner_last_rows_raw',None)
  first=answers[0];row=_one(first,exact if awaken else lambda r:r.get('score',0)>=.94 and bool(re.fullmatch(re.escape(name)+r'\+50',_text(r))),'대상')
  y=row.get('y')
  if type(y) is not int:raise Pending('도술 선택 행 위치 확인 필요')
  predicate=(lambda f:g.awakening_tab(f) and g.awaken_selected(f,y)) if awaken else (lambda f:g.tab(f) and g.selected(f,y))
  if not all(predicate(f) for f in frames):raise Pending('도술 성장 선택 대상 변경')
  proof_rows=[row]
  if awaken:
   proof_rows.append(_one(answers[1],exact,'중앙 이름'))
   stages=[awaken_stage(f) for f in frames]
   if stages[0] is None or stages[0]!=stages[1]:raise Pending('개별 도술 현재 각성 단계 확인 필요')
   current=stages[0];next_stage=1 if current==0 else None;stage_box=AWAKEN_STAGE
  else:
   current,next_stage=parse_break_stage(answers[1]);proof_rows.extend(answers[1]);stage_box=BREAK_STAGE
   g.bind_style_identity(ui,name,frames,y)
  source=frames[-1]
  proofs=[]
  def append_row(r):
   box=_bounds(r);x,t,w,h=box;patch=source[t:t+h,x:x+w].copy()
   # Disabled price/button glyphs can be darker than the white-text mask.
   # Exact RGB equality is stricter and can still prove their read-only state.
   mode='text' if g._same_pixels(source,box,patch,'text') else 'exact'
   proofs.append((box,patch,ticks[-1],mode))
  for r in proof_rows:
   append_row(r)
  x,t,w,h=stage_box;proofs.append((stage_box,source[t:t+h,x:x+w].copy(),ticks[-1],'text'))
  if not awaken:
   x,t,w,h=g.STYLE_ICON;proofs.append((g.STYLE_ICON,source[t:t+h,x:x+w].copy(),ticks[-1],'style_icon'))
  result={'name':name,'kind':kind,'current':current,'next':next_stage}
  changing_funds=bool(need_quote and raw and len(raw[2])==len(specs))
  if need_quote:
   if not all(g._fixed_template(f,'upgrade_coin.png',
     '5da1e8d46c60a0fa1b25255b220ab2fa3a06ad288e5ec1d915e85a7ddc95982c',(322,443,14,14),.98) for f in frames):
    raise Pending('도술 성장 엽전 비용 아이콘 확인 필요')
   proofs.append(((322,443,14,14),source[443:457,322:336].copy(),ticks[-1],'rgb'))
   have,need=g.number(answers[base_count],'ratio');cost=g.number(answers[base_count+1],'price');funds=g.number(answers[base_count+2],'balance')
   if changing_funds:
    first_funds,second_funds=raw[2][base_count+2]
    if not g.nondecreasing_balance(first_funds,second_funds):raise Pending('도술 성장 엽전 잔액 감소·판독 변경')
    funds=min(g.number(first_funds,'balance'),g.number(second_funds,'balance'))
   word='각성' if awaken else '돌파'
   action=_one(answers[base_count+3],lambda r:r.get('score',0)>=.98 and _text(r)==word,word+' 버튼')
   box=_bounds(action);point=(box[0]+box[2]//2,box[1]+box[3]//2)
   for index,kind_of_number in ((base_count,'ratio'),(base_count+1,'price'),(base_count+2,'balance')):
    if changing_funds and kind_of_number=='balance':continue
    r=_one(answers[index],lambda r:_valid_number(r,kind_of_number),'재료·비용')
    append_row(r)
   append_row(action)
   result.update(have=have,need=need,price=cost,funds=funds,point=point)
  result['proofs']=g.refresh_evidence(ui,self.guard,frames,ticks,proofs,predicate)
  if changing_funds:
   latest=ui.rows_batch([(g.BALANCE,'number',.90,'original_or_clahe',None,g.numeric_pair_verifier('balance',increasing=True))])[0]
   latest_frames,latest_ticks,_=ui._owner_last_rows_pair;latest_pair=ui._owner_last_rows_raw[2][0]
   if (not g.nondecreasing_balance(*latest_pair) or g.number(latest_pair[0],'balance')<g.number(second_funds,'balance')
     or not all(predicate(f) for f in latest_frames) or any(not 0<=time.monotonic()-t<=3 for t in latest_ticks)):
    raise Pending('도술 성장 최신 엽전·대상 재확인 필요')
   if any(not g._same_pixels(f,p[0],p[1],p[3]) for f in latest_frames for p in result['proofs']):
    raise Pending('도술 성장 잔액 확인 중 대상·단계·비용 변경')
   item=_one(latest,lambda r:_valid_number(r,'balance'),'최신 엽전');box=_bounds(item);x,t,w,h=box
   result['proofs'].append((box,latest_frames[-1][t:t+h,x:x+w].copy(),latest_ticks[-1],'text'))
   result['funds']=min(result['funds'],g.number(latest_pair[0],'balance'),g.number(latest_pair[1],'balance'))
  result['predicate']=predicate
  return result
 def commit(self,observation,prepare):
  g=_g();ui=self.ui
  def proof(frame):
   ui.context.checkpoint()
   ok=(self.guard() is True and observation['predicate'](frame)
    and _bright_action(frame,observation['point']) and all(g._same(frame,p) for p in observation['proofs']))
   if not ok:return False
   prepare()
   return self.guard() is True and all(g._same(frame,p) for p in observation['proofs'])
  ui.click(*observation['point'],proof)
  ui.context.wait(.5)


def _valid_number(row,kind):
 try:_g().number([row],kind);return True
 except Pending:return False


class SkillUpgrade:
 """One durable resource action per confirmed stage, shared across restarts."""
 def __init__(self,port,ledger,guard,observe=None):self.port=port;self.ledger=ledger;self.guard=guard;self.observe=observe
 def check(self,*,budget=True):
  self.port.ui.context.checkpoint()
  deadline=getattr(self.port.ui,'_owner_growth_deadline',None)
  if budget and type(deadline) in (int,float) and time.monotonic()>=deadline:
   raise Pending('도술 성장 방문 시간 종료 · 나머지는 다음 점검에서 계속')
  if self.guard() is not True:raise Pending('현재 캐릭터·도술 설정 변경')
 def run(self,name,kind,target,*,max_steps=5,result_only=False):
  if kind not in ('awaken','breakthrough') or type(target) is not int or not 0<=target<=9999:raise Pending('도술 각성·돌파 목표 확인 필요')
  if type(max_steps) is not int or not 1<=max_steps<=10:raise ValueError('도술 성장 반복 한도 오류')
  intents=_intents(self.ledger);key=kind+':'+name
  section='individual' if kind=='awaken' else 'skills'
  field='awaken' if kind=='awaken' else 'breakthrough'
  for _ in range(max_steps):
   self.check();reading=self.port.observe(name,kind);current=reading['current'];prior=intents.get(key)
   if reading.get('name')!=name or reading.get('kind')!=kind or type(current) is not int or not 0<=current<=9999:
    raise Pending('도술 현재 대상·단계 판독 계약 불일치')
   if prior and prior.get('status') in ('prepared','intent','sent') and (
     prior.get('name',name)!=name or prior.get('kind',kind)!=kind
     or type(prior.get('before')) is not int or not 0<=prior['before']<9999):
    raise Pending('이전 도술 입력 기록의 대상·종류·단계 불일치')
   if prior and prior.get('status')=='prepared':
    prior['status']='aborted_before_input';self.ledger.event('skill_upgrade_aborted',key=key)
   if prior and prior.get('status') in ('intent','sent'):
    if kind=='breakthrough' and current==prior.get('before',-2):
     # Same stage: that attempt failed. Awakening has no failure.
     prior.update(status='observed_failure',after=current);self.ledger.event('skill_upgrade_failed',key=key,after=current)
     if result_only:return {'status':'observed_failure','name':name,'kind':kind,'current':current}
    elif current!=prior.get('before',-2)+1:raise Pending('이전 도술 '+field+' 입력 결과 확인 필요: '+name)
    else:prior.update(status='observed_after',after=current);self.ledger.event('skill_upgrade_reconciled',key=key,after=current)
   if self.observe:self.observe(section,name,{field:current})
   if current>=target:return {'status':'target_reached','name':name,'kind':kind,'current':current}
   if any(k!=key and r.get('status') in ('intent','sent') for k,r in intents.items()):
    raise Pending('다른 도술 입력의 미확인 결과 우선 확인 필요')
   self.check();quote=self.port.observe(name,kind,need_quote=True)
   if quote.get('name')!=name or quote.get('kind')!=kind or quote['current']!=current or quote.get('next')!=current+1:
    raise Pending('도술 다음 '+field+' 단계 실화면 검증 필요')
   if any(type(quote.get(k)) is not int for k in ('have','need','price','funds')) or quote['have']<0 or quote['need']<=0 or quote['price']<=0 or quote['funds']<0:
    raise Pending('도술 성장 재료·가격 판독 계약 불일치')
   if quote['have']<quote['need'] or quote['funds']<quote['price']:raise Pending('도술 '+field+' 재료·엽전 부족')
   from owner_coin_reserve import reserve
   if quote['funds']-quote['price']<reserve():raise Pending('도술 '+field+' 남길 엽전 도달')
   intents[key]={'status':'prepared','name':name,'kind':kind,'before':current,'next':current+1,
    'target':target,'price':quote['price'],'have':quote['have'],'need':quote['need'],'at':time.time()}
   self.ledger.event('skill_upgrade_prepared',key=key,before=current)
   def sent():
    self.check();intents[key]['status']='sent';self.ledger.event('skill_upgrade_sent',key=key,before=current)
   try:self.port.commit(quote,sent)
   except BaseException:
    if intents[key]['status']=='prepared':
     intents[key]['status']='aborted_before_input';self.ledger.event('skill_upgrade_aborted',key=key)
    raise
   if kind=='breakthrough':
    from owner_growth_reading import RESULT_SETTLE_SECONDS
    self.port.ui.context.wait(RESULT_SETTLE_SECONDS)
   self.check(budget=False);after=self.port.observe(name,kind)
   if kind=='breakthrough' and after.get('name')==name and after.get('kind')==kind and after.get('current')==current:
    intents[key].update(status='observed_failure',after=current);self.ledger.event('skill_upgrade_failed',key=key,after=current)
    continue
   if after.get('name')!=name or after.get('kind')!=kind or type(after.get('current')) is not int or after['current']!=current+1:
    raise Pending('도술 '+field+' 입력 후 결과 확인 필요: '+name)
   intents[key].update(status='confirmed',after=after['current']);self.ledger.event('skill_upgrade_verified',key=key,after=after['current'])
   if self.observe:self.observe(section,name,{field:after['current']})
   if after['current']>=target:return {'status':'target_reached','name':name,'kind':kind,'current':after['current']}
  return {'status':'partial','name':name,'kind':kind,'current':after.get('current',current)}


def _intents(ledger):
 rows=ledger.item.setdefault('skill_upgrade_intents',{})
 if not isinstance(rows,dict) or any(not isinstance(k,str) or not isinstance(v,dict) for k,v in rows.items()):
  raise Pending('도술 각성·돌파 입력 기록 형식 확인 필요')
 return rows


def has_pending(ledger):
 return any(r.get('status') in ('intent','sent') for r in _intents(ledger).values())
