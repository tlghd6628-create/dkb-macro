"""Read-only inspection of an already-open shop; never purchases anything.

The row rectangles are based on a saved 897x479 town-shop frame, not a proven
general layout. The observations are diagnostic and are deliberately NOT
ShopJournal purchase authorization. No install/automatic dispatch is provided.
"""
import re, math
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from functools import lru_cache
from owner_shop_settings_candidate import ShopSettingsStore
from owner_shop_transaction_candidate import Hold

def _clean(text):return re.sub(r'\s+','',text) if isinstance(text,str) else ''
def _exact(rows,text,minimum=.96):
 found=[r for r in rows if isinstance(r,dict) and r.get('score',0)>=minimum and _clean(r.get('text'))==_clean(text)]
 return found[0] if len(found)==1 else None

def displayed_balance_interval(text):
 """Return a conservative interval for a displayed numeric value.

 Compact K/M/B rounding policy is not yet known; widening by one last
 displayed unit covers both truncation and ordinary nearest rounding. This
 is diagnostic evidence only, never proof of currency or exact balance.
 """
 if not isinstance(text,str):return None
 value=text.strip().replace(' ','').upper()
 if ',' in value and not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?[KMB]?',value):return None
 value=value.replace(',','')
 match=re.fullmatch(r'(\d{1,12})(?:\.(\d{1,4}))?([KMB])?',value)
 if not match:return None
 whole,fraction,suffix=match.groups()
 if fraction is not None and suffix is None:return None
 try:
  scale={'K':1000,'M':1000000,'B':1000000000,None:1}[suffix]
  amount=Decimal(whole+('.'+fraction if fraction is not None else ''))*scale
  if amount>Decimal(10)**15:return None
  if suffix is None:
   exact=int(amount);return {'lower':exact,'upper':exact,'exact':True,'display':text}
  step=Decimal(scale)/(10**len(fraction or ''))
  lower=max(Decimal(0),amount-step)
  return {'lower':int(lower.to_integral_value(rounding=ROUND_FLOOR)),
          'upper':int((amount+step).to_integral_value(rounding=ROUND_FLOOR)),
          'exact':False,'display':text}
 except (InvalidOperation,OverflowError):return None

def balance_observation(rows,minimum=.97):
 """Only accept a single strong numeric OCR candidate; no currency assumption."""
 found=[]
 for row in rows:
  if not isinstance(row,dict) or type(row.get('score')) not in (int,float) or not math.isfinite(row['score']) or row['score']<minimum:continue
  interval=displayed_balance_interval(row.get('text'))
  if interval is not None:found.append(interval)
 return found[0] if len(found)==1 else None

# Templates are captured from an observed remote-shop screen. Name matches
# are valid only at the standardized 897x479 client size; other goods remain
# unrecognized until independently captured, never guessed from row order.
OBSERVED_NAMES=('1단 체력 회복 물약','영웅 장비 강화 비법서','영웅 가호의 정수',
                '전설 장비 강화 비법서','전설 가호의 정수','파멸 도술 강화 요령서',
                '연타 도술 강화 요령서','강타 도술 강화 요령서')

@lru_cache(maxsize=8)
def _templates(directory):
 import numpy as np
 from PIL import Image
 return tuple(np.asarray(Image.open(Path(directory)/(str(n)+'.png')).convert('RGB')) for n in range(len(OBSERVED_NAMES)))

def identify_shop_row(frame,row,asset_root=None):
 import cv2,numpy as np
 if type(row) is not int or row not in range(8) or getattr(frame,'shape',None)!=(479,897,3):return None
 root=Path(asset_root) if asset_root else Path(__file__).parent/'assets/shop-rows'
 crop=frame[65+46*row:79+46*row,49:165]
 scores=[]
 try:templates=_templates(str(root))
 except (OSError,ValueError):return None
 for name,template in zip(OBSERVED_NAMES,templates):
  if template.shape!=crop.shape:return None
  score=float(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED)[0][0])
  scores.append((score,name))
 scores.sort(reverse=True)
 if not np.isfinite(scores[0][0]) or scores[0][0]<.985 or scores[0][0]-scores[1][0]<.03:return None
 return scores[0][1]

def find_visible_row(frame,expected_item,asset_root=None):
 """Find observed text at any vertical offset; reject duplicate/tied labels."""
 import cv2,numpy as np
 if expected_item not in OBSERVED_NAMES or getattr(frame,'shape',None)!=(479,897,3):return None
 root=Path(asset_root) if asset_root else Path(__file__).parent/'assets/shop-rows'
 try:templates=_templates(str(root))
 except OSError:return None
 region=frame[64:435,49:165];idx=OBSERVED_NAMES.index(expected_item)
 values=cv2.matchTemplate(region,templates[idx],cv2.TM_CCOEFF_NORMED).reshape(-1)
 candidates=[int(y) for y in np.flatnonzero(np.isfinite(values)&(values>=.985))]
 # A text row may produce adjacent overlapping peaks; insist on one cluster.
 clusters=[]
 for y in candidates:
  if not clusters or y-clusters[-1][-1]>2:clusters.append([y])
  else:clusters[-1].append(y)
 if len(clusters)!=1:return None
 y=max(clusters[0],key=lambda j:values[j]);crop=region[y:y+14,:]
 competitors=[float(cv2.matchTemplate(crop,t,cv2.TM_CCOEFF_NORMED)[0,0]) for j,t in enumerate(templates) if j!=idx]
 if not competitors or values[y]-max(competitors)<.03:return None
 return int(y+64)

def find_ocr_row(ui,expected_item):
 """An untemplated row needs an exact, unique, high-confidence OCR pair."""
 ui.rows((44,61,153,370),language='korean');pair=getattr(ui,'_owner_last_rows_pair',None)
 if not pair:return None
 found=[]
 for answer in pair[2]:
  matches=[r for r in answer if r.get('score',0)>=.94 and _clean(r.get('text'))==_clean(expected_item)]
  if len(matches)!=1:return None
  found.append(matches[0])
 if abs(found[0]['y']-found[1]['y'])>1:return None
 y=round((found[0]['y']+found[1]['y'])/2)-9
 if not 64<=y<=395:return None
 return {'y':y,'samples':tuple(frame[y:y+14,44:165].copy() for frame in pair[0]),'rows':pair[2]}

def read_weekly_quote(ui,expected_item,*,allow_exhausted=False):
 """Two identical visual name readings and paired OCR of price/weekly count.

 This is a quote, not authority to add to cart or buy. The initial templates
 are from the remote shop and do not establish the shop's navigation origin.
 """
 import cv2,numpy as np
 from PIL import Image
 first=ui.frame();ui.context.wait(.12);second=ui.frame()
 first_y=find_visible_row(first,expected_item);y=find_visible_row(second,expected_item)
 source=None
 if first_y is None or y is None or first_y!=y:
  source=find_ocr_row(ui,expected_item)
  if not source:raise Hold('선택 상품의 두 화면 이름 확인 필요')
  y=source['y']
 def row_proof(frame):
  if source is None:return find_visible_row(frame,expected_item)==y
  patch=frame[y:y+14,44:165]
  return all(patch.shape==sample.shape and float(cv2.matchTemplate(patch,sample,cv2.TM_CCOEFF_NORMED)[0,0])>=.985 for sample in source['samples'])
 try:
  root=Path(__file__).parent/'assets/shop-rows'
  coins=[np.asarray(Image.open(root/name).convert('RGB')) for name in ('coin.png','coin-potion.png')]
 except OSError as exc:raise Hold('재화 표시 기준 이미지 확인 필요') from exc
 def icon_proof(frame):
  patch=frame[y+15:y+27,49:62]
  return any(patch.shape==coin.shape and float(cv2.matchTemplate(patch,coin,cv2.TM_CCOEFF_NORMED)[0][0])>=.97 for coin in coins)
 if not all(icon_proof(f) for f in (first,second)):raise Hold('엽전 가격 표시 확인 필요')
 rows=ui.rows((40,y,145,45),language='korean')
 prices=[];quotas=[]
 for item in rows:
  if type(item.get('score')) not in (int,float) or not math.isfinite(item['score']):continue
  text=str(item.get('text','')).strip()
  if item['score']>=.95 and re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)',text):prices.append(int(text.replace(',','')))
  if item['score']>=.84:
   match=re.search(r'(\d{1,4})\s*/\s*(\d{1,4})',text)
   if match:quotas.append((int(match[1]),int(match[2])))
 if len(prices)!=1 or len(quotas)!=1:raise Hold('가격 또는 주간 수량 판독 확인 필요')
 first_number,limit=quotas[0]
 if not 0<=first_number<=limit or limit==0:raise Hold('구매 가능 수량 없음 또는 미확인')
 # A quota label is mandatory: weekly shows used/limit; the observed potion
 # label shows currently available/maximum. Its reset semantics are unknown.
 try:
  weekly=np.asarray(Image.open(root/'weekly.png').convert('RGB'))
  available=np.asarray(Image.open(root/'available-label.png').convert('RGB'))
 except OSError as exc:raise Hold('주간 한도 기준 이미지 확인 필요') from exc
 def weekly_proof(frame):
  patch=frame[y+29:y+39,49:94]
  return patch.shape==weekly.shape and float(cv2.matchTemplate(patch,weekly,cv2.TM_CCOEFF_NORMED)[0][0])>=.97
 def available_proof(frame):
  patch=frame[y+29:y+39,49:79]
  return patch.shape==available.shape and float(cv2.matchTemplate(patch,available,cv2.TM_CCOEFF_NORMED)[0][0])>=.97
 frames=getattr(ui,'_owner_last_rows_pair',None)
 if not frames or not all(row_proof(f) and icon_proof(f) for f in frames[0]):
  raise Hold('주간 한도 또는 상품 화면 변경')
 is_weekly=all(weekly_proof(f) for f in frames[0]);is_available=all(available_proof(f) for f in frames[0])
 if is_weekly==is_available:raise Hold('구매 가능 수량의 표시 의미 확인 필요')
 used=first_number if is_weekly else limit-first_number
 remaining=limit-used
 if remaining==0 and not allow_exhausted:raise Hold('구매 가능 수량 없음 또는 미확인')
 icons={}
 for name in OBSERVED_NAMES:
  a,b=frames[0]
  top=find_visible_row(a,name)
  if top is not None and find_visible_row(b,name)==top and top+39<435:
   icons[name]={'popup':(a[top+1:top+29,14:42].copy(),b[top+1:top+29,14:42].copy()),
                'cart':(a[top+6:top+39,11:46].copy(),b[top+6:top+39,11:46].copy())}
 if expected_item not in icons and source is not None and all(row_proof(f) for f in frames[0]):
  a,b=frames[0];icons[expected_item]={'popup':(a[y+1:y+29,14:42].copy(),b[y+1:y+29,14:42].copy()),
                                    'cart':(a[y+6:y+39,11:46].copy(),b[y+6:y+39,11:46].copy())}
 if source is not None:
  # Anonymous visible alternatives serve only as icon competitors; OCR text
  # does not identify or enable them. Pair agreement is required.
  a,b=frames[0]
  for row in source['rows'][0]:
   top=row.get('y',0)-9
   if (len(re.findall(r'[가-힣]',str(row.get('text',''))))<3 or not 64<=top<=395
       or abs(top-y)<12 or top+39>=435):continue
   if not any(abs(other.get('y',0)-row.get('y',0))<=1 and _clean(other.get('text'))==_clean(row.get('text')) for other in source['rows'][1]):continue
   positions=[find_visible_row(a,name) for name in OBSERVED_NAMES]
   if any(pos is not None and abs(pos-top)<3 for pos in positions):continue
   icons['__visible_'+str(top)]={'popup':(a[top+1:top+29,14:42].copy(),b[top+1:top+29,14:42].copy()),
                                'cart':(a[top+6:top+39,11:46].copy(),b[top+6:top+39,11:46].copy())}
 if expected_item not in icons:raise Hold('선택 상품 이미지 두 화면 확인 필요')
 return {'name':expected_item,'row_y':y,'row_proof':row_proof,'currency':'엽전','unit_price':prices[0],
         'used':used,'limit':limit,'remaining':remaining,
         'kind':'observed_weekly_quote' if is_weekly else 'observed_available_quote','icons':icons}

def discover_visible_items(ui):
 """Inventory an already-open shop without inputs or purchase authority.

 Known-name results use two matching visual frames. Other OCR lines are
 explicitly unverified suggestions and must never become enabled settings
 or purchase authority automatically. There is no inferred scroll coverage.
 """
 from owner_membership import hit
 first=ui.frame();ui.context.wait(.12);second=ui.frame()
 if not all(hit(f,'remote-shop-title',(35,4,110,30)) is not None for f in (first,second)):
  raise Hold('상점 목록 화면 확인 필요')
 known=[]
 for name in OBSERVED_NAMES:
  a=find_visible_row(first,name);b=find_visible_row(second,name)
  if a is not None and a==b:known.append({'name':name,'y':a,'source':'paired_observed_template','purchase_permitted':False})
 rows=ui.rows((44,61,153,370),language='korean')
 suggestions=[]
 for row in rows:
  text=str(row.get('text','')).strip()
  if type(row.get('score')) not in (int,float) or not math.isfinite(row['score']) or row['score']<.9:continue
  if len(re.findall(r'[가-힣]',text))<3 or re.search(r'구매|가능|한정|상점|수량|재화',text):continue
  suggestions.append({'text':text[:100],'y':row.get('y'),'source':'ocr_unverified','purchase_permitted':False})
 return {'status':'visible_page_only','known':known,'suggestions':suggestions,
         'purchase_permitted':False,'coverage':'현재 화면만 · 전체 상점 목록 미검증'}

def inspect_visible_town(ui,root,character,journal,item_name,visible_row):
 """Use paired existing SkillUI OCR; returns an explicit non-authorizing result.

`visible_row` 0..5 only chooses a crop; it is not proof of item identity.
`character` names a settings/journal scope and is not proof of game identity.
    """
 if type(visible_row) is not int or visible_row not in range(6):raise Hold('보이는 상품 행 확인 필요')
 settings=ShopSettingsStore(root,character).read_document()
 if settings.get('enabled',True) is not True:raise Hold('상점 구매 사용 꺼짐')
 matched=[row for row in settings['items'] if row['shop']=='town' and row['name']==item_name and row['enabled'] is True]
 if len(matched)!=1:raise Hold('일반 상점 구매 설정 확인 필요')
 if settings['coin_reserve'] is None:raise Hold('남길 엽전 미설정')
 records=journal._read()['transactions']
 if any(r['state']=='pending' and r['character']==character and r['shop']=='town' and r['item']==item_name for r in records):
  raise Hold('이전 구매 결과 미확인 · 재구매 보류')
 out={'shop':'town','requested_item':item_name,'status':'hold','purchase_permitted':False,'reasons':[],'raw':{}}
 title=ui.rows((32,0,110,34),language='korean');out['raw']['title']=title
 if not _exact(title,'잡화상점',.95):raise Hold('일반 잡화상점 화면 확인 필요')
 top=109+46*visible_row
 row=ui.rows((44,top,145,47),language='korean');out['raw']['row']=row
 balance=ui.rows((392,2,63,26),language='korean');out['raw']['balance']=balance
 out['balance_interval']=balance_observation(balance)
 if not _exact(row,item_name):out['reasons'].append('상품명 정확 판독 미확인')
 # Abbreviated 5.42M cannot prove an exact balance or reserve.
 exact_balance=[r for r in balance if r.get('score',0)>=.97 and re.fullmatch(r'\d[\d,]*',str(r.get('text','')))]
 if len(exact_balance)!=1:out['reasons'].append('정확한 엽전 잔액 미확인')
 # Do not translate quota OCR into a purchase limit until both its semantics
 # and two-frame numeric reading have been established for this shop.
 out['reasons']+=['주간 구매 한도 의미·정확 수치 미검증','실제 캐릭터·재화 종류 미확인','상품별 구매 수량 및 결과 판독 미검증']
 return out

def inspect_current_town(adapter,context,inputs,character,journal,item_name,visible_row):
 """Create the existing image reader; no navigation, click or purchase."""
 from owner_skill_ui import SkillUI
 ui=SkillUI(adapter,context,inputs)
 return inspect_visible_town(ui,adapter.project.root,character,journal,item_name,visible_row)

def scan_current_town(ui,root,character,journal,checkpoint=lambda:None):
 """Read at most six visible rows of an already open town shop, with no input.

 Each OCR call uses SkillUI's paired-frame reader. Different row captures are
 not a single atomic shop snapshot; the result is therefore discovery only,
 not a transaction or purchase authorization. Unselected items are ignored.
 """
 settings=ShopSettingsStore(root,character).read_document()
 if settings.get('enabled',True) is not True:return {'status':'no_selected_items','items':[],'purchase_permitted':False}
 selected={r['name'] for r in settings['items'] if r['shop']=='town' and r['enabled'] is True}
 if not selected:return {'status':'no_selected_items','items':[],'purchase_permitted':False}
 checkpoint();title=ui.rows((32,0,110,34),language='korean')
 if not _exact(title,'잡화상점',.95):raise Hold('일반 잡화상점 화면 확인 필요')
 checkpoint();balance=ui.rows((392,2,63,26),language='korean')
 pending={r['item'] for r in journal._read()['transactions']
          if r['state']=='pending' and r['character']==character and r['shop']=='town'}
 found=[]
 for visible_row in range(6):
  checkpoint()
  rows=ui.rows((44,109+46*visible_row,145,47),language='korean')
  for name in selected:
   match=_exact(rows,name)
   if match is not None:
    found.append({'name':name,'visible_row':visible_row,'previous_pending':name in pending,
                  'ocr_score':match['score'],'purchase_permitted':False})
 return {'status':'review_required','items':found,'balance_interval':balance_observation(balance),
         'purchase_permitted':False,'reason':'상품 가격·한도·수량·재화 및 구매 결과 확인 필요'}

def open_remote_only(adapter,context,inputs):
 """Reuse existing membership navigation; performs input, but no purchase.

    Not installed or called by this module. A caller must own the input worker.
    """
 from owner_membership import open_remote,paid
 if not paid(adapter.project.root):raise Hold('멤버십 설정 확인 필요')
 context.checkpoint()
 return open_remote(adapter,context,inputs)
