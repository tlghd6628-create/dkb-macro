"""Observed remote-shop flow, on the existing input-owning worker only.

Observed list names are candidates; each transaction must separately verify
its current item, quantity, price and cart. Unknown or ambiguous screens hold.
"""
import json,logging,time,re,uuid,hashlib,math
from pathlib import Path
from owner_shop_reader_candidate import scan_current_town,read_weekly_quote,balance_observation,find_visible_row,find_ocr_row,discover_visible_items
from owner_shop_settings_candidate import ShopSettingsStore
from owner_shop_settings_candidate import NAMES
from owner_shop_transaction_candidate import ShopJournal,Hold
from biol_base.session import Cancelled
LOG=logging.getLogger('project_gui.DKB')
class ShopNavigationError(Hold):
 """The game may still be in a shop; caller must not continue another job."""

def configured_identity(root):
 # Exactly the same configured-profile key as the existing settings editor.
 from owner_hunt_rules_candidate import configured_identity as resolve
 try:return resolve(root)
 except (OSError,ValueError,TypeError) as exc:raise Hold('서버·캐릭터 설정 확인 필요') from exc

def inspect_current_shop(adapter,context,inputs):
 """On a known already-open town screen, discover selected visible items.

 No menu navigation, purchases, state mutation, or game input is performed.
 The configured identity scopes settings; it is not proof of in-game identity.
 """
 from owner_skill_ui import SkillUI
 context.checkpoint();root=adapter.project.root;identity=configured_identity(root)
 ui=SkillUI(adapter,context,inputs)
 result=scan_current_town(ui,root,identity,ShopJournal(Path(root)/'settings/owner-shop-journal.json'),context.checkpoint)
 LOG.info('잡화상점 판독 · 선택 품목 %d개 · 게임 캐릭터와 구매 조건 미확인 · 구매 없음',len(result.get('items',())))
 return result

def _asset_match(frame,name,box,threshold=.97):
 import cv2,numpy as np
 from PIL import Image
 try:needle=np.asarray(Image.open(Path(__file__).parent/'assets/shop-rows'/(name+'.png')).convert('RGB'))
 except OSError:return False
 x,y,w,h=box;patch=frame[y:y+h,x:x+w]
 if patch.shape[0]<needle.shape[0] or patch.shape[1]<needle.shape[1]:return False
 score=cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)
 return bool(np.isfinite(score).all() and float(score.max())>=threshold)

def _paired(ui,proof):
 first=ui.frame();ui.context.wait(.12);second=ui.frame()
 return bool(proof(first) and proof(second))

def _balance(ui):
 rows=ui.rows((408,4,45,19),language='korean');value=balance_observation(rows)
 pair=getattr(ui,'_owner_last_rows_pair',None)
 if not value or not pair or not all(_asset_match(f,'header-coin',(393,8,16,17)) for f in pair[0]):
  raise Hold('현재 엽전 잔액 두 화면 확인 필요')
 value['frame_ids']=[hashlib.sha256(frame.tobytes()+str(tick).encode()).hexdigest() for frame,tick in zip(pair[0],pair[1])]
 if len(value['frame_ids'])!=2 or value['frame_ids'][0]==value['frame_ids'][1]:raise Hold('서로 다른 두 화면 필요')
 return value

def _number(ui,box,*,minimum=.95,prefix=False):
 rows=ui.rows(box,language='korean');matches=[]
 for row in rows:
  if not isinstance(row,dict) or type(row.get('score')) not in (int,float) or not math.isfinite(row['score']) or row['score']<minimum:continue
  text=str(row.get('text','')).strip()
  match=re.search(r'(?::|：)([0-9][0-9,]*)$',text) if prefix else re.fullmatch(r'([0-9][0-9,]*)',text)
  if match:matches.append(int(match[1].replace(',','')))
 if len(matches)!=1:raise Hold('수량 또는 금액 판독 확인 필요')
 return matches[0]

def _name_candidate(text,extra=()):
 from difflib import SequenceMatcher
 cleaned=re.sub(r'[^가-힣0-9]','',str(text));rank=[]
 for name in dict.fromkeys([*NAMES,*extra]):
  target=re.sub(r'[^가-힣0-9]','',name)
  rank.append((SequenceMatcher(None,cleaned,target,autojunk=False).ratio(),name))
 rank.sort(reverse=True)
 if len(rank)<2 or rank[0][0]<.66 or rank[0][0]-rank[1][0]<.10:return None
 return rank[0][1]

def _icon_name(frame,icons,kind):
 import cv2,numpy as np
 box=(369,185,414,225) if kind=='popup' else (330,315,368,352)
 x,y,r,b=box;patch=frame[y:b,x:r];scores=[]
 for name,variants in icons.items():
  choices=variants.get(kind,())
  if len(choices)!=2:continue
  per=[]
  for image in choices:
   if image.shape[0]>patch.shape[0] or image.shape[1]>patch.shape[1]:break
   matches=cv2.matchTemplate(patch,image,cv2.TM_CCOEFF_NORMED)
   per.append(float(np.nan_to_num(matches,nan=-1).max()))
  if len(per)==2:scores.append((min(per),name))
 scores.sort(reverse=True)
 threshold=.72 if kind=='popup' else .55
 if len(scores)<2 or scores[0][0]<threshold or scores[0][0]-scores[1][0]<.10:return None
 return scores[0][1]

def _popup(ui,price,item,icons):
 from owner_skill_ui import match
 def proof(frame):
  return (_asset_match(frame,'quantity-title',(421,162,59,15)) and _icon_name(frame,icons,'popup')==item and
          bool(match(frame,'quote-one',(432,239,21,20),.97)))
 if not _paired(ui,proof):raise Hold('선택한 상품·구매 수량 1 확인 필요')
 observed_titles={'영웅 장비 강화 비법서':'quantity-hero','영웅 가호의 정수':'quantity-hero-blessing'}
 exact=observed_titles.get(item)
 exact_proof=bool(exact and _paired(ui,lambda f:_asset_match(f,exact,(410,189,102,14),.985)))
 if not exact_proof:
  ui.rows((410,189,125,15),language='korean');pair=getattr(ui,'_owner_last_rows_pair',None)
  if not pair or any(len([r for r in answer if r.get('score',0)>=.84 and _name_candidate(r.get('text'),icons)==item])!=1 for answer in pair[2]):
   raise Hold('수량창 상품명 두 화면 확인 필요')
 if _number(ui,(458,200,60,15),minimum=.97,prefix=True)!=price:raise Hold('상품 개당 가격 불일치')
 try:owned=_number(ui,(460,213,55,12),minimum=.94,prefix=True)
 except Hold:owned=_number(ui,(445,212,75,15),minimum=.96,prefix=True)
 if not _paired(ui,proof):raise Hold('수량 화면 변경')
 return owned,proof

def _total(ui):
 try:return _number(ui,(428,388,80,20),minimum=.92)
 except Hold:return _number(ui,(390,385,115,25),minimum=.92)

def _find_quote(ui,item,on_page=None):
 """Bounded list-only navigation; an absent or moving row never buys."""
 from owner_membership import hit
 def list_proof(frame):
  return hit(frame,'remote-shop-title',(35,4,110,30)) is not None and _asset_match(frame,'cart-empty',(330,315,242,36))
 if not _paired(ui,list_proof) or _total(ui)!=0:raise Hold('빈 상점 목록 확인 필요')
 def present():
  first=ui.frame();ui.context.wait(.12);second=ui.frame()
  a=find_visible_row(first,item);b=find_visible_row(second,item)
  if a is not None and a==b:return True
  return find_ocr_row(ui,item) is not None
 if present():return read_weekly_quote(ui,item,allow_exhausted=True)
 # Return to list top once, then inspect a bounded number of pages.
 ui.drag((120,110),(120,390),list_proof)
 for _ in range(8):
  ui.context.checkpoint()
  if on_page is not None:on_page()
  if present():return read_weekly_quote(ui,item,allow_exhausted=True)
  ui.drag((120,390),(120,110),list_proof)
 raise Hold('선택 상품을 현재 보이는 상점 목록에서 찾지 못했습니다')

def _same_cart(frame,verified_cart,icons,item):
 import numpy as np
 if getattr(frame,'shape',None)!=(479,897,3) or getattr(verified_cart,'shape',None)!=(479,897,3):return False
 for l,t,r,b in ((330,315,572,351),(387,385,505,410)):
  a=verified_cart[t:b,l:r].astype(np.int16);current=frame[t:b,l:r].astype(np.int16)
  diff=np.max(np.abs(a-current),axis=2)
  if float(np.mean(diff>8))>.005:return False
 return _icon_name(frame,icons,'cart')==item

def _journal(root):return ShopJournal(Path(root)/'settings/owner-shop-remote-runtime.json')

def _record_intent(journal,identity,character,week,item,quote,owned,balance,reserve,shop='remote'):
 def write():
  data=journal._read();transactions=data['transactions']
  if any(r['state']=='pending' and r['character']==character and r['shop']==shop for r in transactions):
   raise Hold('이전 상점 구매 결과 미확인')
  stamp=time.time();entry={'id':uuid.uuid4().hex,'state':'pending','character':character,'profile':identity,
    'shop':shop,'week':week,'item':item,'currency':'엽전','unit_price':quote['unit_price'],'quantity':1,
    'remaining':quote['remaining'],'balance':balance['lower'],'minimum_balance':reserve,'prepared_at':stamp,
    'frame_ids':list(balance['frame_ids']),'owned_before':owned,'balance_interval':balance}
  transactions.append(entry);journal._write(data);return entry
 return journal._under_lock(write)

def _confirm_intent(journal,entry,owned_after,balance_after):
 def write():
  data=journal._read();rows=[r for r in data['transactions'] if r['id']==entry['id'] and r['state']=='pending']
  if len(rows)!=1:raise Hold('이전 구매 기록 확인 필요')
  before=entry['balance_interval'];price=entry['unit_price']
  if owned_after!=entry['owned_before']+1 or balance_after['upper']<before['lower']-price or balance_after['lower']>before['upper']-price:
   raise Hold('구매 후 보유 수량·잔액 변화 확인 필요')
  rows[0].update(state='confirmed',confirmed_at=time.time(),owned_after=owned_after,balance_after=balance_after)
  journal._write(data)
 return journal._under_lock(write)

def _open_town_shop(adapter,context,inputs):
 """Reuse original town return and merchant detection; require shop header."""
 from owner_skill_ui import SkillUI
 from owner_membership import hit
 from project_adapter.town_services import TownServices,POTION_NAMES
 LOG.info('잡화상점 이동 · 마을 복귀 시작')
 if adapter.run_town_return(context,inputs) is False:raise Hold('잡화상점 마을 복귀 미확인')
 context.checkpoint();LOG.info('잡화상점 이동 · 마을 복귀 처리 종료 · 상인 확인')
 service=TownServices(adapter,context,inputs,list(POTION_NAMES));ui=SkillUI(adapter,context,inputs)
 def shop(frame):return hit(frame,'remote-shop-title',(35,4,110,30)) is not None
 if _paired(ui,shop):return ui
 original_check=service.check;deadline=time.monotonic()+8
 def bounded_check():
  original_check()
  if time.monotonic()>=deadline:raise Hold('마을 상인 탐색 시간 초과 · 구매 미완료')
 service.check=bounded_check
 try:found=service.merchant()
 finally:service.check=original_check
 context.checkpoint()
 if not found:raise Hold('마을 상인 위치를 확인하지 못했습니다')
 adapter._owner_shop_entered=True
 service.click_hit(found)
 try:ui.wait(shop,seconds=10)
 except Cancelled:raise
 except Exception as exc:raise ShopNavigationError('마을 상점 진입 화면 미확인') from exc
 if not _paired(ui,shop):raise ShopNavigationError('마을 상점 두 화면 확인 필요')
 return ui

def _buy_one(adapter,context,inputs,item,shop):
 """Buy one explicitly enabled observed item, or hold before uncertain input.

 The purchase receipt path requires the existing exact success toast, empty
 cart, paired balance and owned-count increase. An interrupted operation is
 durably pending and will not be retried automatically.
 """
 from owner_membership import paid,open_remote
 from owner_quest_preflight import read_power
 from owner_progression import state
 from owner_skill_ui import SkillUI,match
 from owner_timetable import period,BY_KEY,now,day_at
 root=adapter.project.root;profile=configured_identity(root);store=ShopSettingsStore(root,profile);document,revision=store.snapshot()
 if document.get('enabled',True) is not True:raise Hold('상점 구매 사용 꺼짐')
 if shop not in ('town','remote'):raise Hold('상점 구분 확인 필요')
 chosen=[r for r in document['items'] if r['shop']==shop and r['name']==item and r['enabled'] is True]
 if len(chosen)!=1:raise Hold('체크한 상품 확인 필요')
 reserve=document['coin_reserve']
 if type(reserve) is not int or reserve<0:raise Hold('남길 엽전 확인 필요')
 if shop=='remote' and not paid(root):raise Hold('멤버십 설정 확인 필요')
 began=time.monotonic();read_power(adapter,context,inputs);progress=state(adapter)
 if not progress.character or progress.observed<began:raise Hold('현재 캐릭터 화면 확인 필요')
 observed_character=progress.character
 def guard():
  try:
   current=state(adapter);age=time.monotonic()-current.observed
   return (current.character==observed_character and 0<=age<=180
           and configured_identity(root)==profile and store.revision()==revision
           and not getattr(getattr(context,'stop',None),'is_set',lambda:False)())
  except (OSError,ValueError,TypeError):return False
 fingerprint=profile+' | '+progress.character;journal=_journal(root)
 records=journal._read()['transactions']
 if any(r['state']=='pending' and r['character']==fingerprint and r['shop']==shop for r in records):raise Hold('이전 구매 결과 확인 필요')
 probe=SkillUI(adapter,context,inputs)
 if not probe.normal():raise Hold('원격 상점 진입 전 일반 화면 확인 필요')
 ui=open_remote(adapter,context,inputs) if shop=='remote' else _open_town_shop(adapter,context,inputs)
 adapter._owner_shop_entered=True
 # Add visible OCR suggestions disabled, separately per navigation source;
 # never silently enable a new or misspelled product. A later actual screen
 # check is still required before any purchase.
 seen=getattr(adapter,'_owner_shop_discovered',None)
 if seen is None:seen=set();adapter._owner_shop_discovered=seen
 def sync_page():
  nonlocal document,revision
  from owner_skill_goal import Pending
  try:
   discovery=discover_visible_items(ui)
   names=[r['name'] for r in discovery['known']]+[r['text'] for r in discovery['suggestions']]
   added=store.merge_observed(shop,names)
   if added:LOG.info('상점 화면 후보 추가 · %s · %d개 · 기본 미선택',shop,len(added))
   document,revision=store.snapshot()
  except (Hold,Pending,OSError,ValueError,TypeError) as exc:
   LOG.info('상점 목록 자동 판독 보류 · %s',str(exc))
  current=[r for r in document['items'] if r['shop']==shop and r['name']==item and r['enabled'] is True]
  if len(current)!=1 or current[0]!=chosen[0] or document['coin_reserve']!=reserve:
   raise Hold('상점 구매 설정이 변경되어 다시 확인합니다')
 if shop not in seen:sync_page();seen.add(shop)
 quote=_find_quote(ui,item,on_page=sync_page)
 if quote['remaining']==0:return {'status':'quota_empty','item':item}
 # '구매 가능' is only an observed current limit; the game's reset semantics
 # are unknown. Its configured quantity is applied per scheduled game day.
 week=(day_at(now()).isoformat() if quote.get('kind')=='observed_available_quote'
       else period(BY_KEY['weekly_missions'],now()))
 bought=sum(r['quantity'] for r in records if r['state']=='confirmed' and r['character']==fingerprint and r['shop']==shop and r['item']==item and r['week']==week)
 if chosen[0]['mode']=='quantity' and bought>=chosen[0]['quantity']:return {'status':'target_reached','confirmed':bought}
 before=_balance(ui)
 if before['lower']-quote['unit_price']<reserve:raise Hold('남길 엽전 미달 또는 부족')
 if _total(ui)!=0 or not _paired(ui,lambda f:_asset_match(f,'cart-empty',(330,315,242,36))):
  raise Hold('기존 장바구니가 비어 있지 않거나 확인되지 않음')
 row_y=quote['row_y'];ui.click(110,row_y+7,lambda f:guard() and quote['row_proof'](f))
 owned,popup_proof=_popup(ui,quote['unit_price'],item,quote['icons']);adapter._owner_shop_popup_proof=popup_proof
 entry=_record_intent(journal,profile,fingerprint,week,item,quote,owned,before,reserve,shop=shop)
 # Confirmation here adds to cart; the quota can change before any purchase.
 ui.click(490,302,lambda f:guard() and popup_proof(f))
 ui.wait(lambda f:_icon_name(f,quote['icons'],'cart')==item)
 if not _paired(ui,lambda f:_icon_name(f,quote['icons'],'cart')==item):raise Hold('선택 상품 장바구니 확인 필요')
 if _total(ui)!=quote['unit_price']:raise Hold('장바구니 합계 불일치')
 verified_cart=ui.last_text_frame.copy()
 latest=_balance(ui)
 if latest['lower']-quote['unit_price']<reserve:raise Hold('구매 직전 엽전 잔액 확인 필요')
 ui.click_word('구매',(730,430,65,40),lambda f:guard() and _same_cart(f,verified_cart,quote['icons'],item),minimum=.96)
 # A generic native completion alone, and the increased quota while in the
 # cart, are not proof that a purchase completed.
 ui.word('아이템 구매를 완료',(230,80,440,250),minimum=.92)
 if _total(ui)!=0:raise Hold('구매 후 장바구니 비움 확인 필요')
 after=_balance(ui)
 after_quote=read_weekly_quote(ui,item,allow_exhausted=True);row_y=after_quote['row_y']
 ui.click(110,row_y+7,lambda f:guard() and after_quote['row_proof'](f))
 owned_after,proof=_popup(ui,quote['unit_price'],item,after_quote['icons']);adapter._owner_shop_popup_proof=proof
 # Exit only the proved quantity popup; this is not a purchase action.
 ui.click(408,302,proof)
 _confirm_intent(journal,entry,owned_after,after)
 return {'status':'confirmed','quantity':1,'item':item}

def _close_known_shop(adapter,context,inputs):
 """Close only our own proved menu, never send input after Stop."""
 if not getattr(adapter,'_owner_shop_entered',False):return
 adapter._owner_shop_entered=False
 if getattr(getattr(context,'stop',None),'is_set',lambda:False)():return
 from owner_skill_ui import SkillUI
 from owner_membership import hit
 ui=SkillUI(adapter,context,inputs)
 def quantity(frame):return _asset_match(frame,'quantity-title',(421,162,59,15))
 if _paired(ui,quantity):
  proof=getattr(adapter,'_owner_shop_popup_proof',None)
  if not callable(proof) or not _paired(ui,proof):raise ShopNavigationError('열린 수량창의 상품 확인 필요')
  ui.click(408,302,proof)
 adapter._owner_shop_popup_proof=None
 def shop(frame):return hit(frame,'remote-shop-title',(35,4,110,30)) is not None
 if not _paired(ui,shop):raise ShopNavigationError('상점 종료 보류 · 화면을 확인해 주세요')
 ui.click(22,19,shop)
 ui.wait(lambda f:ui.normal(),seconds=5)
 if not ui.normal():raise ShopNavigationError('상점 종료 후 일반 화면 미확인')

def buy_one(adapter,context,inputs,item,shop):
 from owner_skill_goal import Pending
 adapter._owner_shop_popup_proof=None
 try:
  try:return _buy_one(adapter,context,inputs,item,shop)
  except Pending as exc:raise Hold('상점 판독 확인 필요 · '+str(exc)) from exc
 finally:
  try:_close_known_shop(adapter,context,inputs)
  except Cancelled:raise
  except Exception as exc:
   LOG.warning('상점 화면 정리 미확인 · %s',str(exc))
   raise ShopNavigationError('상점 화면 정리 확인 필요') from exc

def buy_remote_one(adapter,context,inputs,item):return buy_one(adapter,context,inputs,item,'remote')

def dispatch_configured(adapter,context,inputs):
 """Run selected items only from the shop appointment on the same worker."""
 from owner_schedule_priority import hold_reason
 root=adapter.project.root;profile=configured_identity(root);store=ShopSettingsStore(root,profile)
 if not store.path.exists():return {'status':'no_settings'}
 document=store.read_document()
 if document.get('enabled',True) is not True:return {'status':'no_selection'}
 selected=[r for r in document['items'] if r['enabled']]
 if not selected:return {'status':'no_selection'}
 supported=selected
 holds=[];confirmed=0
 for setting in supported:
  # Bound the native weekly limit; each item gets its own fresh recheck,
  # durable intent and receipt, and the same input thread can yield to Stop.
  for _ in range(50):
   context.checkpoint()
   reason=hold_reason(adapter)
   if reason:LOG.info('원격 상점 구매 보류 · %s',reason);return {'status':'reservation_hold'}
   try:result=buy_one(adapter,context,inputs,setting['name'],setting['shop'])
   except ShopNavigationError:raise
   except Hold as exc:
    LOG.warning('상점 품목 미완료 · %s · %s',setting['name'],str(exc));holds.append(setting['name']);break
   if result.get('status') in ('target_reached','quota_empty'):break
   if result.get('status')!='confirmed':return result
   confirmed+=1
  else:
   LOG.warning('상점 품목 50회 제한 · %s',setting['name']);holds.append(setting['name'])
 summary={'status':('partial' if holds else 'processed'),'held_items':holds,'confirmed':confirmed,
          'retryable':bool(holds),'retry_mode':'recheck',
          'reason':'상점 품목 미완료: '+', '.join(holds) if holds else ''}
 adapter._owner_shop_outcome=summary
 return summary

def install():
 from project_adapter._entry import Adapter
 if getattr(Adapter,'_owner_shop_runtime_installed',False):return Adapter.owner_inspect_current_shop
 Adapter.owner_inspect_current_shop=inspect_current_shop
 Adapter.owner_buy_remote_one=buy_remote_one
 original=Adapter.run_potion_purchase
 from functools import wraps
 @wraps(original)
 def run_potion_purchase(adapter,context,inputs):
  # Native idle waits also drive the timetable. While inside a shop, they
  # must never re-enter an unrelated job on the same input-owning worker.
  from owner_schedule_priority import LOCAL
  previous=getattr(LOCAL,'feature',None);LOCAL.feature='상점 구매'
  try:
   result=original(adapter,context,inputs)
   context.checkpoint()
   if result is False and getattr(adapter,'_owner_remote_potion_navigation_hold',None):
    LOG.info('원격 물약 탐색 보류 · 같은 차례 설정 상점 구매도 생략 · 기존 매크로 계속')
    return False
   # Potion replenishment is startup-critical. General shopping has its own
   # appointment: never chain town travel/merchant search before the quest.
   # Keep enabled item choices; every later attempt still checks its journal.
   return result
  finally:LOCAL.feature=previous
 Adapter.run_potion_purchase=run_potion_purchase
 Adapter._owner_shop_runtime_installed=True
 return Adapter.owner_inspect_current_shop
