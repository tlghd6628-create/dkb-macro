"""Observed remote-shop flow, on the existing input-owning worker only.

Observed list names are candidates; each transaction must separately verify
its current item, quantity, price and cart. Unknown or ambiguous screens hold.
"""
import json,logging,time,re,uuid,hashlib,math
from pathlib import Path
from owner_shop_reader_candidate import scan_current_town
from owner_skill_goal import Pending
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
 """Same rectangle, same threshold; `name.png` plus optional `name.N.png` cut
 from lossless product frames. The first JPEG-cut originals stay as they are."""
 import cv2,numpy as np
 from PIL import Image
 root=Path(__file__).parent/'assets/shop-rows'
 x,y,w,h=box;patch=frame[y:y+h,x:x+w]
 for path in [root/(name+'.png')]+sorted(root.glob(name+'.[0-9].png')):
  try:needle=np.asarray(Image.open(path).convert('RGB'))
  except OSError:continue
  if patch.shape[0]<needle.shape[0] or patch.shape[1]<needle.shape[1]:continue
  score=cv2.matchTemplate(patch,needle,cv2.TM_CCOEFF_NORMED)
  if np.isfinite(score).all() and float(score.max())>=threshold:return True
 return False

def _paired(ui,proof):
 first=ui.frame();ui.context.wait(.12);second=ui.frame()
 return bool(proof(first) and proof(second))

def _not_read():
 """Coins are not read any more. The purchase record still has its fields, and wants two distinct ids."""
 return {'lower':0,'upper':0,'exact':False,'display':'미확인','frame_ids':[uuid.uuid4().hex,uuid.uuid4().hex]}

def _name_candidate(text,extra=()):
 from difflib import SequenceMatcher
 cleaned=re.sub(r'[^가-힣0-9]','',str(text));rank=[]
 for name in dict.fromkeys([*NAMES,*extra]):
  target=re.sub(r'[^가-힣0-9]','',name)
  rank.append((SequenceMatcher(None,cleaned,target,autojunk=False).ratio(),name))
 rank.sort(reverse=True)
 if len(rank)<2 or rank[0][0]<.66 or rank[0][0]-rank[1][0]<.10:return None
 return rank[0][1]

TITLE=(421,162,59,15)
ADD_ONE=(489,247);ADD_ALL=(507,247);POPUP_CANCEL=(408,302);POPUP_CONFIRM=(490,302)

def _same_patch(frame,sample,box):
 import cv2
 x,y,w,h=box;patch=frame[y:y+h,x:x+w]
 return patch.shape==sample.shape and float(cv2.matchTemplate(patch,sample,cv2.TM_CCOEFF_NORMED)[0,0])>=.985

def _price(text):
 """Digits only; the number reader sometimes takes a comma for a point."""
 text=str(text).strip().replace('.',',')
 return int(text.replace(',','')) if re.fullmatch(r'\d{1,3}(?:,\d{3})*',text) else None

REAL_LIST=(10,90,300,678)
ROW_SHIFT=8  # real pixels a row may have glided since it was read; the rows are 74 apart

def quote_from_words(rows,item):
 """This item's row from the words of the list, top to bottom: name, price, then the limit under it. None when it
 is not all on screen. Places are real pixels, so a row is what stands within one row height under its name."""
 names=[r for r in rows if r['bounds'][0]>=60 and re.search(r'[가-힣]{2}',r['text']) and _name_candidate(r['text'],(item,))==item]
 if len(names)>1:raise Hold('같은 상품으로 읽힌 행이 둘 이상입니다')
 if not names:return None
 top=names[0]['ry'];below=[r for r in rows if top<r['ry']<=top+60]
 price=[v for v in (_price(r['text']) for r in below if r['score']>=.85) if v is not None]
 limit=[re.search(r'(\d{1,4})\s*/\s*(\d{1,4})',r['text']) for r in below]
 limit=[(m[1],m[2],r) for m,r in zip(limit,below) if m]
 if len(price)!=1 or len(limit)!=1:return None
 used,maximum,row=int(limit[0][0]),int(limit[0][1]),limit[0][2]
 words=dict(name=item,name_row=names[0],price=price[0],first=used,limit=maximum,bracketed='(' in row['text'],
            sold_out=any(re.sub(r'\s','',r['text']).startswith('구매불가') for r in below))
 return words


def row_on_screen(frame,item,ry):
 """The list is in front, no popup is over it, and this item's name stands where it was read. Words, because the rows are
 see-through and the world moves behind them: comparing their pictures failed a list that had not changed."""
 from owner_membership import shop_title
 from owner_text import read
 if not shop_title(frame) or _quantity_shown(frame):return False
 rows=read(None,frame,(REAL_LIST[0],max(0,ry-22),REAL_LIST[2],44),scale=3)
 names=[r for r in rows if r['bounds'][0]>=60 and re.search(r'[가-힣]{2}',r['text']) and _name_candidate(r['text'],(item,))==item]
 return len(names)==1 and abs(names[0]['ry']-ry)<=ROW_SHIFT


def _real_quote(ui,item):
 """The whole list once, for the words of every row. A name that is not there needs no second look; a row that is gets
 its second frame from its own band, which reads in a fraction of the two seconds the whole list takes."""
 from owner_text import read
 first=ui.frame()
 if getattr(first,'hi',None) is None:raise Hold('상점 구매는 실제 화면에서만 합니다')
 rows=read(ui.adapter.project.root,first,REAL_LIST,scale=3)
 ui._owner_shop_last_page=[r['text'] for r in rows if re.search(r'[가-힣]{2}',r['text']) and '한정' not in r['text'] and '구매' not in r['text']]
 a=quote_from_words(rows,item)
 if a is None:return None
 ui.context.wait(.12)
 top=a['name_row']['ry']-18
 b=quote_from_words(read(ui.adapter.project.root,ui.frame(),(REAL_LIST[0],max(0,top),REAL_LIST[2],84),scale=3),item)
 if b is None or any(a[key]!=b[key] for key in ('price','first','limit','bracketed','sold_out')):raise Pending('상점 목록 두 화면 확인 필요')
 limit,first_number=a['limit'],a['first']
 # A row saying 구매 불가 can hold over its limit (구매 가능 320/250), and is simply used up.
 if limit==0 or (first_number>limit and not a['sold_out']):raise Pending('구매 수량 판독 확인 필요')
 kind,used=('observed_weekly_quote',first_number) if a['bracketed'] else ('observed_available_quote',limit-first_number)
 if a['sold_out']:used=limit
 # The row's name line, in the 897x479 terms the buying steps click in.
 ry=a['name_row']['ry']
 return {'name':item,'click_y':a['name_row']['y']+8,'row_proof':lambda frame:row_on_screen(frame,item,ry),
         'currency':'엽전','unit_price':a['price'],'used':used,'limit':limit,'remaining':limit-used,'kind':kind}


_read_quote=_real_quote

REAL_POPUP=(540,290,420,80)

def popup_from_words(rows,item):
 """(name is this item, price, owned) from the words of the quantity popup, or None for what did not read."""
 named=any(_name_candidate(r['text'],(item,))==item for r in rows)
 def number(word):
  for row in rows:
   found=re.search(word+r'[^0-9]*([0-9][0-9,]*)',re.sub(r'\s','',row['text']))
   if found:return int(found[1].replace(',',''))
  return None
 return named,number('가격'),number('개수')


REAL_POPUP_TITLE=(600,252,180,36);REAL_CART_LABEL=(430,618,240,46)

def _quantity_shown(frame):
 """The quantity popup's title: its words on the real screen, the old picture otherwise."""
 if getattr(frame,'hi',None) is None:return _asset_match(frame,'quantity-title',TITLE)
 from owner_text import find,read
 return bool(find(read(None,frame,REAL_POPUP_TITLE),'수량 입력'))

def _cart_bar(frame):
 """The cart bar is on screen. Its picture on the old frame also proves it is empty; on the real screen the label says
 it is there, and every caller reads a total of 0 for the rest."""
 if getattr(frame,'hi',None) is None:return _asset_match(frame,'cart-empty',(330,315,242,36))
 from owner_text import find,read
 return bool(find(read(None,frame,REAL_CART_LABEL),'합계'))

def _popup(ui,price,item):
 """Owned count and a proof of this popup, after reading its name and price from two frames."""
 from owner_text import read
 title=_quantity_shown
 def words(frame):return popup_from_words(read(ui.adapter.project.root,frame,REAL_POPUP,scale=3),item)
 ui.wait(title,seconds=5)
 reason='수량창 판독 확인 필요'
 for attempt in range(6):
  if attempt:ui.context.wait(.3)
  frames=[ui.frame()];ui.context.wait(.12);frames.append(ui.frame())
  if not all(title(frame) for frame in frames):raise Hold('수량 화면 변경')
  a,b=(words(frame) for frame in frames)
  if not (a[0] and b[0]):reason='수량창 상품명 두 화면 확인 필요';continue
  if None in a or a!=b:reason='수량 또는 금액 판독 확인 필요';continue
  if a[1]!=price:raise Hold('상품 개당 가격 불일치')
  def proof(frame):
   # The bag count can rise while the character picks things up, so only the name and the price must still stand.
   shown=words(frame)
   return title(frame) and shown[0] and shown[1]==price
  return a[2],proof
 raise Hold(reason)

# The town merchant totals two currencies side by side, which pushes the coin total left of the remote shop's.
TOTAL_BOXES={'remote':(428,388,80,20),'town':(380,388,85,24)}

def _total_values(root,frame,box):
 """The numbers in the cart's total. A lone 0 is only read reliably at 3 times, and it comes back at any place in the pill."""
 from owner_text import read
 from owner_hd import real_box
 x,y,w,h=real_box(box,frame.layout)
 rows=read(root,frame,(max(0,x-10),max(0,y-6),w+20,h+12),language='number',scale=3)
 return [v for v in (_price(r['text']) for r in rows if r['score']>=.85) if v is not None]

def _total(ui):
 """The cart total, once two frames agree. It counts up right after an item goes in."""
 box=TOTAL_BOXES[getattr(ui,'_owner_shop_kind','remote')]
 for attempt in range(6):
  if attempt:ui.context.wait(.3)
  frames=[ui.frame()]
  ui.context.wait(.12);frames.append(ui.frame())
  if getattr(frames[0],'hi',None) is None:raise Hold('상점 구매는 실제 화면에서만 합니다')
  values=[_total_values(ui.adapter.project.root,frame,box) for frame in frames]
  if len(values[0])==1 and values[0]==values[1]:
   ui.last_text_frame=frames[-1];ui.last_text_tick=time.monotonic()
   return values[0][0]
 raise Hold('장바구니 합계 판독 확인 필요')

TOP_ROW='1단 체력 회복 물약'

def _find_quote(ui,item):
 """Bounded list-only navigation; an absent or moving row never buys. Goes on down from where the last item left the
 list, and back to the top only for an item already passed or when the end was reached without starting at the top."""
 from owner_membership import shop_title
 def list_proof(frame):return shop_title(frame) and _cart_bar(frame)
 if not _paired(ui,list_proof) or _total(ui)!=0:raise Hold('빈 상점 목록 확인 필요')
 def visible():
  # The list keeps gliding after a drag, so a page that does not agree yet is read again.
  for attempt in range(4):
   ui.context.checkpoint()
   try:return _read_quote(ui,item)
   except Pending:
    if attempt==3:raise
    ui.context.wait(.5)
 def on_page():
  return {_name_candidate(text) for text in getattr(ui,'_owner_shop_last_page',None) or ()}-{None}
 def to_top():
  ui.drag((120,110),(120,400),list_proof);ui.drag((120,110),(120,400),list_proof)
  ui._owner_shop_passed=set();ui._owner_shop_from_top=True
  ui.context.checkpoint();ui.context.wait(.4)
 quote=visible()
 if quote:return quote
 if TOP_ROW in on_page():ui._owner_shop_passed=set();ui._owner_shop_from_top=True
 if item in getattr(ui,'_owner_shop_passed',()):
  to_top();quote=visible()
  if quote:return quote
 before=getattr(ui,'_owner_shop_last_page',None)
 # The list flings: the same drag moved it 65 to 206 px and a long one skipped whole rows.
 # This one always leaves the rows of the page before on screen.
 for _ in range(14):
  ui.context.checkpoint()
  ui._owner_shop_passed=set(getattr(ui,'_owner_shop_passed',()))|on_page()
  ui.drag((120,400),(120,130),list_proof,hold=.3)
  ui.context.wait(.4)
  quote=visible()
  if quote:return quote
  page=getattr(ui,'_owner_shop_last_page',None)
  # A page unchanged by a drag is the end of the list.
  if page and page==before:
   if getattr(ui,'_owner_shop_from_top',False):break
   to_top();quote=visible()
   if quote:return quote
   page=getattr(ui,'_owner_shop_last_page',None)
  before=page
 LOG.info('상점 목록 마지막 화면 · %s',getattr(ui,'_owner_shop_last_page',None))
 raise Hold('선택 상품을 현재 보이는 상점 목록에서 찾지 못했습니다')

def _same_cart(frame,verified_cart,total=None,box=TOTAL_BOXES['remote']):
 """On the real screen the bar is see-through and the world moves behind it: its label and the total itself say it is the
 same cart. On a frame with no real pixels, the bar may differ a little and only the total itself must match."""
 import numpy as np
 if getattr(frame,'hi',None) is not None:
  return total is not None and _cart_bar(frame) and _total_values(None,frame,box)==[total]
 if getattr(frame,'shape',None)!=(479,897,3) or getattr(verified_cart,'shape',None)!=(479,897,3):return False
 l,t,r,b=(330,315,572,351)
 changed=float(np.mean(np.max(np.abs(verified_cart[t:b,l:r].astype(np.int16)-frame[t:b,l:r].astype(np.int16)),axis=2)>8))
 x,y,w,h=(430,392,75,16)
 if changed>.10 or not _same_patch(frame,verified_cart[y:y+h,x:x+w],(x,y,w,h)):
  LOG.info('상점 장바구니 화면 차이 · %.3f',changed);return False
 return True

def _journal(root):return ShopJournal(Path(root)/'settings/owner-shop-remote-runtime.json')

def _record_intent(journal,identity,character,week,item,quote,owned,balance,reserve,shop='remote',quantity=1):
 def write():
  data=journal._read();transactions=data['transactions']
  if any(r['state']=='pending' and r['character']==character and r['shop']==shop and r['item']==item for r in transactions):
   raise Hold('이전 상점 구매 결과 미확인')
  stamp=time.time();entry={'id':uuid.uuid4().hex,'state':'pending','character':character,'profile':identity,
    'shop':shop,'week':week,'item':item,'currency':'엽전','unit_price':quote['unit_price'],'quantity':quantity,
    'remaining':quote['remaining'],'used':quote['used'],'balance':balance['lower'],'minimum_balance':reserve,'prepared_at':stamp,
    'frame_ids':list(balance['frame_ids']),'owned_before':owned,'balance_interval':balance}
  transactions.append(entry);journal._write(data);return entry
 return journal._under_lock(write)

def _confirm_intent(journal,entry,owned_after,balance_after):
 """The row's counter was checked by the caller; the bag must have at least that much more.
 It can have more, because the character keeps picking items up. The compact balance proves nothing."""
 def write():
  data=journal._read();rows=[r for r in data['transactions'] if r['id']==entry['id'] and r['state']=='pending']
  if len(rows)!=1:raise Hold('이전 구매 기록 확인 필요')
  if owned_after<entry['owned_before']+entry['quantity']:raise Hold('구매 후 보유 수량 변화 확인 필요')
  rows[0].update(state='confirmed',confirmed_at=time.time(),owned_after=owned_after,balance_after=balance_after)
  journal._write(data)
 return journal._under_lock(write)

def _settle_pending(journal,character,shop,item,used):
 """A run cut off after its intent: the bag count now says whether that purchase went through."""
 def write():
  data=journal._read();kept=[]
  for row in data['transactions']:
   if row['state']=='pending' and row['character']==character and row['shop']==shop and row['item']==item:
    # The row's counter decides: pickups raise the bag count too.
    bought=used>=row.get('used',0)+row.get('quantity',1)
    LOG.info('이전 상점 구매 정리 · %s · %s',item,'구매됨' if bought else '구매 안 됨')
    # The journal keeps pending and confirmed only, and a purchase that did not happen is neither.
    if not bought:continue
    row.update(state='confirmed',confirmed_at=time.time(),used_after=used)
   kept.append(row)
  data['transactions']=kept;journal._write(data)
 journal._under_lock(write)

class _ShopReached(BaseException):
 """Leaves the native potion path once it has opened the shop, before any purchase input."""

def _open_town_shop(adapter,context,inputs):
 """Reuse original town return and merchant detection; require shop header."""
 from owner_skill_ui import SkillUI
 from owner_membership import shop_title as shop
 from project_adapter.town_services import TownServices
 LOG.info('잡화상점 이동 · 마을 복귀 시작')
 if adapter.run_town_return(context,inputs) is False:raise Hold('잡화상점 마을 복귀 미확인')
 context.checkpoint();LOG.info('잡화상점 이동 · 마을 복귀 처리 종료 · 상인 확인')
 ui=SkillUI(adapter,context,inputs)
 if _paired(ui,shop):return ui
 # The merchant is an icon at a fixed spot on a map centred on the character, so it only matches right after a
 # return, and the native potion path retries that up to five times. Ride that path and leave at the first shop button.
 from project_adapter.town_services import run_potion_purchase
 previous=TownServices.button
 def button(service,name,*a,**k):
  if getattr(service,'context',None) is context and str(name).startswith('버튼_물약상인_'):raise _ShopReached()
  return previous(service,name,*a,**k)
 TownServices.button=button
 try:run_potion_purchase(adapter,context,inputs)
 except _ShopReached:pass
 finally:TownServices.button=previous
 context.checkpoint()
 adapter._owner_shop_entered=True
 try:ui.wait(shop,seconds=5)
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
 if shop=='remote' and not paid(root):raise Hold('멤버십 설정 확인 필요')
 visit=getattr(adapter,'_owner_shop_visit',None)
 if visit is not None and visit.ui is not None and (visit.shop!=shop or not character_read_recently(adapter,context)):
  # A character read needs the field, and another shop is another trip.
  visit.ui=None;_leave_shop(adapter,context,inputs)
 if character_read_recently(adapter,context):progress=state(adapter)
 else:
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
 ui=visit.ui if visit is not None else None
 if ui is None:
  probe=SkillUI(adapter,context,inputs)
  if not probe.normal():raise Hold('원격 상점 진입 전 일반 화면 확인 필요')
  ui=open_remote(adapter,context,inputs) if shop=='remote' else _open_town_shop(adapter,context,inputs)
  ui._owner_shop_kind=shop
  adapter._owner_shop_entered=True
  if visit is not None:visit.ui=ui;visit.shop=shop
 quote=_find_quote(ui,item)
 # '구매 가능' is only an observed current limit; the game's reset semantics
 # are unknown. Its configured quantity is applied per scheduled game day.
 week=(day_at(now()).isoformat() if quote['kind']=='observed_available_quote'
       else period(BY_KEY['weekly_missions'],now()))
 records=journal._read()['transactions']
 unsettled=any(r['state']=='pending' and r['character']==fingerprint and r['shop']==shop and r['item']==item for r in records)
 if unsettled:
  _settle_pending(journal,fingerprint,shop,item,quote['used'])
  return {'status':'settled','item':item}
 if quote['remaining']==0:return {'status':'quota_empty','item':item}
 bought=sum(r['quantity'] for r in records if r['state']=='confirmed' and r['character']==fingerprint and r['shop']==shop and r['item']==item and r['week']==week)
 wanted=quote['remaining'] if chosen[0]['mode']=='max' else chosen[0]['quantity']-bought
 if wanted<=0:return {'status':'target_reached','confirmed':bought}
 unit=quote['unit_price']
 count=min(wanted,quote['remaining'])
 if _total(ui)!=0 or not _paired(ui,_cart_bar):
  raise Hold('기존 장바구니가 비어 있지 않거나 확인되지 않음')
 ui.click(110,quote['click_y'],lambda f:guard() and quote['row_proof'](f))
 owned,popup_proof=_popup(ui,unit,item);adapter._owner_shop_popup_proof=popup_proof
 if count==quote['remaining']:ui.click(*ADD_ALL,lambda f:guard() and popup_proof(f))
 else:
  for _ in range(count-1):ui.click(*ADD_ONE,lambda f:guard() and popup_proof(f))
 ui.click(*POPUP_CONFIRM,lambda f:guard() and popup_proof(f))
 adapter._owner_shop_popup_proof=None
 ui.wait(lambda f:not _quantity_shown(f),seconds=5)
 # The popup's own limit can stop short of the count, so the cart says how many.
 total=_total(ui);quantity=total//unit
 if total%unit or not 1<=quantity<=count:raise Hold('장바구니 합계 불일치')
 entry=_record_intent(journal,profile,fingerprint,week,item,quote,owned,_not_read(),0,shop=shop,quantity=quantity)
 LOG.info('상점 구매 · %s %d개 · 합계 %d',item,quantity,total)
 total_now=_total(ui)
 if total_now!=total:raise Hold('장바구니 합계 불일치')
 verified_cart=ui.last_text_frame.copy()
 total_box=TOTAL_BOXES[getattr(ui,'_owner_shop_kind','remote')]
 ui.click_word('구매',(730,430,65,40),lambda f:guard() and _same_cart(f,verified_cart,total,total_box),minimum=.90)
 ui.context.wait(1)
 # Coins are not read: without enough of them the game's button does nothing and the cart stays full.
 if _total(ui)!=0:return {'status':'no_coins','item':item}
 after=_not_read()
 after_quote=_find_quote(ui,item)
 if after_quote['used']<quote['used']+quantity:raise Hold('구매 후 구매 횟수 변화 확인 필요')
 owned_after=owned+quantity
 if after_quote['remaining']>0:
  # A row at its limit opens no popup, and its counter has already said enough.
  ui.click(110,after_quote['click_y'],lambda f:guard() and after_quote['row_proof'](f))
  owned_after,proof=_popup(ui,unit,item);adapter._owner_shop_popup_proof=proof
  # Exit only the proved quantity popup; this is not a purchase action.
  ui.click(*POPUP_CANCEL,proof)
  adapter._owner_shop_popup_proof=None
  ui.wait(lambda f:not _quantity_shown(f),seconds=5)
 _confirm_intent(journal,entry,owned_after,after)
 done=(after_quote['remaining']==0 or (chosen[0]['mode']=='quantity' and bought+quantity>=chosen[0]['quantity']))
 return {'status':'confirmed','quantity':quantity,'item':item,'finished':done}

def _close_known_shop(adapter,context,inputs):
 """Close only our own proved menu, never send input after Stop."""
 if not getattr(adapter,'_owner_shop_entered',False):return
 adapter._owner_shop_entered=False
 if getattr(getattr(context,'stop',None),'is_set',lambda:False)():return
 from owner_skill_ui import SkillUI
 from owner_membership import shop_title as shop
 ui=SkillUI(adapter,context,inputs)
 quantity=_quantity_shown
 # Cancel buys nothing and needs only the popup itself to be there.
 if _paired(ui,quantity):
  ui.click(*POPUP_CANCEL,quantity)
  ui.wait(lambda f:not quantity(f),seconds=5)
 adapter._owner_shop_popup_proof=None
 if not _paired(ui,shop):raise ShopNavigationError('상점 종료 보류 · 화면을 확인해 주세요')
 ui.click(22,19,shop)
 ui.wait(lambda f:ui.normal(),seconds=5)
 if not ui.normal():raise ShopNavigationError('상점 종료 후 일반 화면 미확인')

def _leave_shop(adapter,context,inputs):
 try:_close_known_shop(adapter,context,inputs)
 except Cancelled:raise
 except Exception as exc:
  LOG.warning('상점 화면 정리 미확인 · %s',str(exc))
  raise ShopNavigationError('상점 화면 정리 확인 필요') from exc

class _Visit:
 """One trip into the shop for every selected item. The shop stays open only after an item that ended with an empty cart."""
 ui=None;shop=None

# Ended with nothing in the cart and no popup. 'no_coins' leaves the cart full, and only leaving the shop empties it.
LEAVES_SHOP_READY=('target_reached','quota_empty','settled','confirmed')
# The buying guard allows a character read 180 s old. This leaves room to finish the item that starts just under it.
CHARACTER_READ_SECONDS=100

def character_read_recently(adapter,context):
 """A paired bag read from this very run, of the character the program still has. Opening the bag again says nothing new."""
 from owner_progression import state
 receipt=getattr(adapter,'_owner_progression_observation',None)
 if not receipt or receipt[0] is not context:return False
 progress=state(adapter)
 return bool(progress.character) and receipt[1]==progress.observed and receipt[2]==progress.character and 0<=time.monotonic()-progress.observed<=CHARACTER_READ_SECONDS

def buy_one(adapter,context,inputs,item,shop):
 from owner_skill_goal import Pending
 adapter._owner_shop_popup_proof=None
 visit=getattr(adapter,'_owner_shop_visit',None);stay=False
 try:
  try:
   result=_buy_one(adapter,context,inputs,item,shop)
   stay=visit is not None and result.get('status') in LEAVES_SHOP_READY
   return result
  except Pending as exc:raise Hold('상점 판독 확인 필요 · '+str(exc)) from exc
 finally:
  if not stay:
   if visit is not None:visit.ui=None
   _leave_shop(adapter,context,inputs)

def buy_remote_one(adapter,context,inputs,item):return buy_one(adapter,context,inputs,item,'remote')

def dispatch_configured(adapter,context,inputs):
 """Run selected items only from the shop appointment on the same worker."""
 from owner_schedule_priority import hold_reason
 root=adapter.project.root;profile=configured_identity(root);store=ShopSettingsStore(root,profile)
 if not store.path.exists():return {'status':'no_settings'}
 document=store.read_document()
 selected=[r for r in document['items'] if r['enabled']]
 if document.get('enabled',True) is not True:
  # The master switch silently hides the whole appointment; say so once here.
  LOG.info('상점 구매 생략 · 설정 상품 구매 사용 꺼짐 · 선택 품목 %d개',len(selected))
  return {'status':'no_selection','reason':'설정 상품 구매 사용 꺼짐'}
 if not selected:return {'status':'no_selection','reason':'선택 품목 없음'}
 from owner_membership import paid
 # The same item checked in both shops is one purchase, reached the way this
 # account can: remotely with a membership, at the merchant without one.
 route='remote' if paid(root) else 'town'
 names={(r['shop'],r['name']) for r in selected}
 supported=[r for r in selected if r['shop']==route or (('remote' if r['shop']=='town' else 'town',r['name']) not in names)]
 holds=[];confirmed=0
 visit=_Visit();adapter._owner_shop_visit=visit
 try:
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
    status=result.get('status')
    if status in ('target_reached','quota_empty'):break
    if status=='no_coins':
     LOG.info('상점 구매 멈춤 · %s · 엽전 부족',setting['name']);break
    if status=='settled':continue
    if status!='confirmed':return result
    confirmed+=result.get('quantity',1)
    if result.get('finished'):break
   else:
    LOG.warning('상점 품목 50회 제한 · %s',setting['name']);holds.append(setting['name'])
 finally:
  adapter._owner_shop_visit=None
  entered=visit.ui is not None;visit.ui=None
  if entered:_leave_shop(adapter,context,inputs)
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
