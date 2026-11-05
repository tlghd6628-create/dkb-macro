"""Exercise real transaction control with fake UI only; no game input."""
exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import json,tempfile,time,unittest,threading
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_shop_runtime_candidate as runtime,owner_membership,owner_progression,owner_quest_preflight,owner_skill_ui
import numpy as np
from owner_shop_settings_candidate import ShopSettingsStore
from owner_shop_transaction_candidate import Hold

ITEM='영웅 장비 강화 비법서'
class FakeUI:
 def __init__(self,journal):
  self.journal=journal;self.events=[];self.before_commit=lambda:None;self.last_text_frame=np.zeros((479,897,3),dtype=np.uint8)
  self.context=NS(wait=lambda *a:None,checkpoint=lambda:None)
 def normal(self):return True
 def click(self,x,y,proof):
  if not proof(self.last_text_frame):raise Hold('proof rejected')
  self.events.append({490:'cart',408:'close_popup',489:'add_one',507:'add_all'}.get(x,'open_item'))
 def wait(self,predicate,**kw):pass
 def click_word(self,*a,**k):
  assert self.journal._read()['transactions'][0]['state']=='pending';self.before_commit()
  if not a[2](self.last_text_frame):raise Hold('proof rejected')
  self.events.append('commit')

class Runtime(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'s','character_name':'c'}),encoding='utf8')
  self.profile=runtime.configured_identity(self.root);store=ShopSettingsStore(self.root,self.profile);doc=store.read_document()
  row=next(x for x in doc['items'] if x['shop']=='remote' and x['name']==ITEM);row.update(enabled=True,quantity=1)
  store.write(doc['items'],100000)
  self.adapter=NS(project=NS(root=self.root));self.context=NS(checkpoint=lambda:None);self.progress=NS(character='observed-hash',observed=0.)
  self.journal=runtime._journal(self.root);self.ui=FakeUI(self.journal);self.before_find=lambda:None
 def quote(self,used):
  return {'name':ITEM,'click_y':111,'row_proof':lambda f:True,'unit_price':15000,'remaining':50-used,'used':used,'limit':50,'kind':'observed_weekly_quote'}
 def go(self,*,quotes=None,totals=(0,15000,15000,0),owned=(116,117)):
  def refresh(*args):self.progress.observed=time.monotonic();return True
  quotes=iter(quotes if quotes is not None else (self.quote(0),self.quote(1)))
  def find(*a):self.before_find();return next(quotes)
  balance={'lower':567210,'upper':567230,'frame_ids':['a','b']}
  with patch.object(owner_membership,'paid',return_value=True),patch.object(owner_membership,'open_remote',return_value=self.ui),patch.object(owner_skill_ui,'SkillUI',return_value=self.ui),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_progression,'state',return_value=self.progress),patch.object(runtime,'_find_quote',side_effect=find),patch.object(runtime,'_balance',return_value=balance),patch.object(runtime,'_total',side_effect=list(totals)),patch.object(runtime,'_popup',side_effect=[(value,lambda f:True) for value in owned]),patch.object(runtime,'_paired',return_value=True),patch.object(runtime,'_close_known_shop'),patch.object(runtime,'_same_cart',return_value=True):
   return runtime.buy_remote_one(self.adapter,self.context,None,ITEM)
 def test_confirm_requires_counter_and_owned_and_target_prevents_repeat(self):
  self.assertEqual(self.go()['status'],'confirmed');self.assertEqual(self.ui.events,['open_item','cart','commit','open_item','close_popup'])
  self.assertEqual(self.journal._read()['transactions'][0]['state'],'confirmed')
  self.assertEqual(self.go(quotes=[self.quote(1)])['status'],'target_reached');self.assertEqual(self.ui.events.count('commit'),1)
 def test_intent_is_written_before_the_purchase_click_not_before_the_cart(self):
  self.go();self.assertEqual(self.journal._read()['transactions'][0]['quantity'],1)
 def test_unchanged_counter_is_not_a_purchase(self):
  with self.assertRaises(Hold):self.go(quotes=[self.quote(0),self.quote(0)])
  self.assertEqual(self.journal._read()['transactions'][0]['state'],'pending')
 def test_cut_off_run_settles_by_the_row_counter(self):
  self.assertEqual(self.go(totals=(0,15000,15000,15000))['status'],'no_coins')
  self.assertEqual(self.go(quotes=[self.quote(1)])['status'],'settled')
  self.assertEqual(self.journal._read()['transactions'][0]['state'],'confirmed');self.assertEqual(self.ui.events.count('commit'),1)
 def test_cut_off_run_that_did_not_buy_is_dropped(self):
  self.assertEqual(self.go(totals=(0,15000,15000,15000))['status'],'no_coins')
  self.assertEqual(self.go(quotes=[self.quote(0)])['status'],'settled')
  self.assertEqual(self.journal._read()['transactions'],[])
 def test_cart_total_that_is_no_multiple_or_too_many_never_buys(self):
  for total in (15001,30000):
   with self.assertRaises(Hold):self.go(totals=(0,total))
  self.assertNotIn('commit',self.ui.events);self.assertFalse(self.journal.path.exists())
 def test_quantity_uses_plus_and_full_remaining_uses_the_max_button(self):
  store=ShopSettingsStore(self.root,self.profile);doc=store.read_document()
  next(x for x in doc['items'] if x['shop']=='remote' and x['name']==ITEM)['quantity']=3;store.write(doc['items'],100000)
  self.assertEqual(self.go(quotes=[self.quote(0),self.quote(3)],totals=(0,45000,45000,0),owned=(116,119))['quantity'],3)
  self.assertEqual(self.ui.events.count('add_one'),2);self.assertEqual(self.ui.events.count('add_all'),0)
 def test_unselected_cannot_open_or_spend(self):
  with self.assertRaises(Hold):runtime.buy_remote_one(self.adapter,self.context,None,'전설 장비 강화 비법서')
  self.assertEqual(self.ui.events,[]);self.assertFalse(self.journal.path.exists())
 def test_cart_changes_at_input_boundary_fail(self):
  frame=np.random.default_rng(1).integers(0,255,(479,897,3),dtype=np.uint8)
  self.assertTrue(runtime._same_cart(frame,frame.copy()))
  shimmer=frame.copy();shimmer[320:325,335:350]=255;self.assertTrue(runtime._same_cart(shimmer,frame))
  bar=frame.copy();bar[315:351,330:572]=255;self.assertFalse(runtime._same_cart(bar,frame))
  total=frame.copy();total[392:408,430:505]=0;self.assertFalse(runtime._same_cart(total,frame))
 def test_changed_settings_or_character_before_commit_prevents_purchase(self):
  def mutate():
   store=ShopSettingsStore(self.root,self.profile);doc=store.read_document();store.write(doc['items'],200000)
  self.ui.before_commit=mutate
  with self.assertRaises(Hold):self.go()
  self.assertNotIn('commit',self.ui.events);self.assertEqual(self.journal._read()['transactions'][0]['state'],'pending')
 def test_selection_revoked_while_searching_prevents_any_item_input(self):
  def revoke():
   store=ShopSettingsStore(self.root,self.profile);doc=store.read_document()
   next(r for r in doc['items'] if r['shop']=='remote' and r['name']==ITEM)['enabled']=False
   store.write(doc['items'],doc['coin_reserve'])
  self.before_find=revoke
  with self.assertRaises(Hold):self.go()
  self.assertEqual(self.ui.events,[]);self.assertFalse(self.journal.path.exists())
 def test_dispatch_loops_only_verified_items_and_stops_at_target(self):
  import owner_schedule_priority
  calls=[]
  def buy(*args):
   calls.append(args[-1]);return {'status':'confirmed' if len(calls)<3 else 'target_reached'}
  with patch.object(owner_schedule_priority,'hold_reason',return_value=None),patch.object(runtime,'buy_one',side_effect=buy):
   self.assertEqual(runtime.dispatch_configured(self.adapter,self.context,None)['status'],'processed')
  self.assertEqual(calls,['remote']*3)
 def test_dispatch_stops_for_reservation_before_any_purchase(self):
  import owner_schedule_priority
  with patch.object(owner_schedule_priority,'hold_reason',return_value='보스 예약'),patch.object(runtime,'buy_one',side_effect=AssertionError('must not buy')):
   self.assertEqual(runtime.dispatch_configured(self.adapter,self.context,None)['status'],'reservation_hold')
 def test_unreadable_item_is_partial_not_completed(self):
  import owner_schedule_priority
  with patch.object(owner_schedule_priority,'hold_reason',return_value=None),patch.object(runtime,'buy_one',side_effect=Hold('화면 미확인')):
   outcome=runtime.dispatch_configured(self.adapter,self.context,None)
  self.assertEqual(outcome['status'],'partial');self.assertEqual(outcome['held_items'],[ITEM]);self.assertEqual(outcome['confirmed'],0)
 def test_no_settings_or_selection_never_navigates(self):
  store=ShopSettingsStore(self.root,self.profile);doc=store.read_document()
  for row in doc['items']:row['enabled']=False
  store.write(doc['items'],100000)
  with patch.object(runtime,'buy_one',side_effect=AssertionError('must not buy')):
   self.assertEqual(runtime.dispatch_configured(self.adapter,self.context,None)['status'],'no_selection')
 def test_installed_native_potion_path_does_not_chain_general_shopping(self):
  from project_adapter._entry import Adapter
  from owner_schedule_priority import LOCAL
  calls=[]
  def original(adapter,ctx,inputs):calls.append(('potion',LOCAL.feature));return True
  original_attrs={name:getattr(Adapter,name,None) for name in ('run_potion_purchase','owner_inspect_current_shop','owner_buy_remote_one','_owner_shop_runtime_installed')}
  absent={name for name in original_attrs if name not in Adapter.__dict__}
  try:
   Adapter.run_potion_purchase=original
   if '_owner_shop_runtime_installed' in Adapter.__dict__:del Adapter._owner_shop_runtime_installed
   with patch.object(runtime,'dispatch_configured',side_effect=lambda *a:calls.append(('shop',LOCAL.feature)) or {'status':'no_selection'}):
    runtime.install();self.assertTrue(Adapter.run_potion_purchase(self.adapter,self.context,None))
   # General shopping has its own appointment and never chains onto the potion trip.
   self.assertEqual(calls,[('potion','상점 구매')]);self.assertIsNone(LOCAL.feature)
  finally:
   for name,value in original_attrs.items():
    if name in absent:
     if name in Adapter.__dict__:delattr(Adapter,name)
    else:setattr(Adapter,name,value)
 def test_town_path_requires_detected_merchant_and_paired_shop_screen(self):
  from project_adapter import town_services
  calls=[];self.adapter.run_town_return=lambda *a:calls.append('town')
  service=NS(check=lambda:None,merchant=lambda:calls.append('merchant') or (1,2,(0,0,3,3)),click_hit=lambda hit:calls.append(('click',hit)))
  ui=NS(wait=lambda *a,**kw:calls.append('wait'))
  with patch.object(town_services,'TownServices',return_value=service),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(runtime,'_paired',side_effect=[False,True]):
   self.assertIs(runtime._open_town_shop(self.adapter,self.context,None),ui)
  self.assertEqual([x[0] if isinstance(x,tuple) else x for x in calls],['town','merchant','click','wait'])
 def test_town_missing_merchant_never_clicks(self):
  from project_adapter import town_services
  self.adapter.run_town_return=lambda *a:None
  service=NS(check=lambda:None,merchant=lambda:None,click_hit=lambda hit:self.fail('unexpected click'))
  with patch.object(town_services,'TownServices',return_value=service),patch.object(owner_skill_ui,'SkillUI',return_value=NS()),patch.object(runtime,'_paired',return_value=False):
   with self.assertRaises(Hold):runtime._open_town_shop(self.adapter,self.context,None)
 def test_cancel_never_emits_shop_cleanup_input(self):
  self.adapter._owner_shop_entered=True;stop=threading.Event();stop.set();self.context.stop=stop
  with patch.object(owner_skill_ui,'SkillUI',side_effect=AssertionError('no input after stop')):
   runtime._close_known_shop(self.adapter,self.context,None)
  self.assertFalse(self.adapter._owner_shop_entered)
if __name__=='__main__':unittest.main(verbosity=2)
