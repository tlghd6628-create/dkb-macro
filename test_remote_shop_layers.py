"""Saved actual frames and isolated fake navigation only; no live UI."""
import contextlib,json,threading,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap,numpy as np
from PIL import Image
import owner_membership as m
import owner_shop_runtime_candidate as shop
from owner_skill_goal import Pending
from biol_base.session import Cancelled

def image(name):return np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261102'/name/'screen.png').convert('RGB')).copy()

class SavedLayers(unittest.TestCase):
 def test_actual_previous_box_remains_while_underlying_merchant_still_matches(self):
  for n,expected in (('20261102T143757-d7067a72','energy_selection'),('20261102T143758-398631fc','box_detail'),('20261102T143800-5fb61aaa','box_detail'),('20261102T143802-97bfc661','box_detail')):
   f=image(n);self.assertEqual(m._inventory_popup(f),expected)
   self.assertIsNotNone(m.hit(f,'remote-merchant',(670,43,36,39)))
   self.assertFalse(m.remote_shop_screen(f))
 def test_two_saved_shop_frames_have_independent_foreground_and_list_proof(self):
  for n in ('20261102T030220-b0ce4cbf','20261102T030223-41e178cb'):
   f=image(n);self.assertTrue(m.remote_shop_screen(f))
   dim=(f.astype(float)*.65).astype('uint8');self.assertFalse(m.remote_shop_screen(dim))
   no_label=f.copy();no_label[69:80,49:133]=0;self.assertFalse(m.remote_shop_screen(no_label))
   no_title=f.copy();no_title[9:28,40:117]=0;self.assertFalse(m.remote_shop_screen(no_title))
 def test_shop_title_background_change_cannot_hide_foreground_or_authorize_a_different_label(self):
  f=image('20261102T030220-b0ce4cbf');found=m.hit(f,'remote-shop-title',(35,4,110,30));l,t,r,b=found[2]
  mask=m.asset('remote-shop-title').min(axis=2)>170
  moved=f.copy();patchpart=moved[t:b,l:r];patchpart[~mask]=np.minimum(patchpart[~mask].astype('uint16')+2,255).astype('uint8')
  self.assertTrue(m.remote_shop_screen(moved))
  exact=f.copy();region=exact[t:b,l:r];foreground=m.asset('remote-shop-title').min(axis=2)>170
  region[~foreground]=np.array((80,10,90),dtype='uint8')
  self.assertTrue(m.remote_shop_screen(exact))

class Navigation(unittest.TestCase):
 def case(self,kind):
  actions=[];scope=['same'];ctx=S(checkpoint=lambda:None,wait=lambda _:None,stop=threading.Event())
  adapter=S(project=S(root=Path('unused')),exit_sleep_mode=lambda *a:None,values={'common.potion_and_favorite.potion_tier':'1단물약'})
  ui=S(kind=kind,adapter=adapter,context=ctx,inputs=S(),normal_frame=lambda f:f=='field')
  ui.frame=lambda:ui.kind
  ui.service=S(key=lambda vk:actions.append(('key',vk)),click_hit=lambda h:actions.append(('click',h)))
  def click(x,y,proof):
   if not proof(ui.kind):raise Pending('changed')
   actions.append(('merchant',x,y));ui.kind='unknown'
  ui.click=click;ui.wait=lambda *a,**kw:(_ for _ in ()).throw(Pending('도술 화면 전환 확인 시간 초과'))
  class Port:
   def __init__(self,*a):self.service=S(key=lambda vk:actions.append(('known-key',vk)),click_hit=lambda h:actions.append(('known-x',h)))
   def close_known(self):self.service.click_hit((510,106));self.service.key(0x49);ui.kind='field'
  stack=contextlib.ExitStack();self.addCleanup(stack.close)
  for cm in (patch('owner_skill_ui.SkillUI',return_value=ui),patch('owner_energy_box_port_candidate.Port',Port),patch('owner_progression.state',return_value=S(character='char')),patch('owner_hunt_rules_candidate.configured_identity',side_effect=lambda *a:scope[0]),patch('owner_progression.inventory_parts',side_effect=lambda f:(True,True) if f in ('inventory','box_detail','energy_selection') else (False,False)),patch('owner_progression.open_inventory_by_key',side_effect=lambda service:setattr(ui,'kind','inventory')),patch.object(m,'_inventory_popup',side_effect=lambda f:f if f in ('box_detail','energy_selection') else None),patch.object(m,'remote_shop_screen',side_effect=lambda f:f=='shop'),patch.object(m,'hit',side_effect=lambda f,n,b,*a:(686,61,(675,48,697,74)) if n=='remote-merchant' and f=='inventory' else None)):
   stack.enter_context(cm)
  return ui,adapter,ctx,actions,scope
 def test_previous_known_box_uses_only_existing_x_close_then_defers_potion(self):
  ui,a,c,actions,_=self.case('box_detail')
  with patch('owner_remote_potion_limit_candidate.cached_full',return_value=False):self.assertIs(m.remote_purchase(a,c,ui.inputs),False)
  self.assertEqual(actions,[('known-x',(510,106)),('known-key',0x49)])
  self.assertEqual(a._owner_remote_potion_navigation_hold,'box_detail')
  self.assertEqual(ui.kind,'field')
 def test_known_popup_after_inventory_does_not_click_merchant_behind_it(self):
  ui,a,c,actions,_=self.case('field')
  with patch('owner_progression.open_inventory_by_key',side_effect=lambda _:setattr(ui,'kind','energy_selection')):
   with self.assertRaises(m.RemoteShopDeferred):m.open_remote(a,c,ui.inputs)
  self.assertFalse(any(x[0]=='merchant' for x in actions))
 def test_unknown_post_click_stays_blocked_with_specific_shop_error(self):
  ui,a,c,actions,_=self.case('field')
  with self.assertRaisesRegex(Pending,'원격 잡화상점 진입 시간 초과'):m.open_remote(a,c,ui.inputs)
  self.assertEqual(actions,[('merchant',686,61)]);self.assertIsNone(a._owner_remote_potion_navigation_hold)
 def test_cancel_during_known_close_propagates_without_further_input(self):
  ui,a,c,actions,_=self.case('box_detail')
  count=[0]
  def checkpoint():
   count[0]+=1
   if count[0]>=3:raise Cancelled('Stopped')
  c.checkpoint=checkpoint
  with self.assertRaises(Cancelled):m.open_remote(a,c,ui.inputs)
  self.assertEqual(actions,[])
 def test_changed_profile_before_known_close_blocks_all_input(self):
  ui,a,c,actions,scope=self.case('box_detail');count=[0]
  def checkpoint():
   count[0]+=1
   if count[0]>=3:scope[0]='foreign'
  c.checkpoint=checkpoint
  with self.assertRaises(Pending):m.open_remote(a,c,ui.inputs)
  self.assertEqual(actions,[])
 def test_unconfirmed_known_close_remains_fatal_instead_of_false_success(self):
  ui,a,c,actions,_=self.case('box_detail')
  class BadPort:
   def __init__(self,*args):self.service=S(key=lambda *a:None,click_hit=lambda *a:None)
   def close_known(self):raise RuntimeError('unknown overlay')
  with patch('owner_energy_box_port_candidate.Port',BadPort):
   with self.assertRaisesRegex(Pending,'이전 상자 창 종료 미확인'):m.open_remote(a,c,ui.inputs)
  self.assertEqual(actions,[])
 def test_verified_unchanged_field_after_timeout_defers_without_close_or_spend(self):
  ui,a,c,actions,_=self.case('field')
  ui.wait=lambda *args,**kwargs:(setattr(ui,'kind','field'),(_ for _ in ()).throw(Pending('timeout')))[1]
  with self.assertRaises(m.RemoteShopDeferred):m.open_remote(a,c,ui.inputs)
  self.assertEqual(actions,[('merchant',686,61)]);self.assertEqual(a._owner_remote_potion_navigation_hold,'unchanged_field')

class Wrapper(unittest.TestCase):
 def test_navigation_hold_skips_configured_shop_and_restores_priority(self):
  from project_adapter._entry import Adapter
  from owner_schedule_priority import LOCAL
  a=S(_owner_remote_potion_navigation_hold='box_detail');c=S(checkpoint=lambda:None)
  original_attrs={n:getattr(Adapter,n,None) for n in ('run_potion_purchase','owner_inspect_current_shop','owner_buy_remote_one','_owner_shop_runtime_installed')};absent={n for n in original_attrs if n not in Adapter.__dict__}
  try:
   Adapter.run_potion_purchase=lambda *args:False
   if '_owner_shop_runtime_installed' in Adapter.__dict__:del Adapter._owner_shop_runtime_installed
   with patch.object(shop,'dispatch_configured',side_effect=AssertionError('must not buy after navigation hold')):
    shop.install();self.assertIs(Adapter.run_potion_purchase(a,c,None),False)
   self.assertIsNone(LOCAL.feature)
  finally:
   for n,v in original_attrs.items():
    if n in absent:
     if n in Adapter.__dict__:delattr(Adapter,n)
    else:setattr(Adapter,n,v)

if __name__=='__main__':unittest.main()
