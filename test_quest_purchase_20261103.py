"""Isolated fake-port resource/quest contracts, not actual game acceptance."""
import unittest,copy
from types import SimpleNamespace as NS
from unittest.mock import patch
import bootstrap
import owner_quest_purchase as q

class Book:
 def __init__(self):
  self.item={'active':'q','quests':{'q':{'title':'[외전] 메마른 늪의 여흠','mode':'sub_quest','group':True,'completed':False}}};self.writes=[]
 def commit(self):self.writes.append(copy.deepcopy(self.item))

class Port:
 room=10;fail=None
 def __init__(self,ui,guard):self.owned=625;self.calls=[];ui.port=self
 def open(self):self.calls.append('open');return self.room if self.calls.count('open')==1 else 3
 def close(self):self.calls.append('close')
 def use_one(self):
  self.calls.append('use')
  if self.fail=='use':raise q.Pending('use unknown')
  return 625,624
 def select(self):self.calls.append('select');return self.owned
 def quantity(self,n):self.calls.append(('quantity',n))
 def add_cart(self,n):self.calls.append(('cart',n));return lambda f:True
 def purchase(self,proof):
  self.calls.append('purchase')
  if self.fail=='purchase':raise q.Pending('purchase unknown')
 def after(self,n):return self.owned+n

class Tests(unittest.TestCase):
 def test_actual_stored_purchase_step_and_dimmed_rejection(self):
  import numpy as np
  from PIL import Image
  from owner_quest_purchase_assets import purchase_step
  image=np.asarray(Image.open(bootstrap.A/'logs/manual-captures/20261103_175644_854e3445.png').convert('RGB')).copy()
  self.assertTrue(purchase_step(image));self.assertFalse(purchase_step((image*.4).astype('uint8')))
  image[78:100,685:836]=0;self.assertFalse(purchase_step(image))
 def test_empty_cart_accepts_current_variant_rejects_real_three_item_cart(self):
  import numpy as np
  from PIL import Image
  from owner_quest_purchase_assets import empty_cart
  p=bootstrap.A/'logs/manual-captures'
  self.assertTrue(empty_cart(np.asarray(Image.open(p/'20261103_180348_894a2d2e.png').convert('RGB'))))
  self.assertFalse(empty_cart(np.asarray(Image.open(p/'20261103_173550_d78c5682.png').convert('RGB'))))
 def setup_case(self,done=0,room=10,fail=None):
  b=Book();adapter=NS(project=NS(root='fake-root'));ui=NS(adapter=adapter,context=NS(checkpoint=lambda:None),close_known=lambda:None)
  goal={'done':done,'total':3,'remaining':3-done,'objective':'물건 3개 구매'}
  class P(Port):pass
  P.room=room;P.fail=fail
  return b,ui,goal,P
 def run_case(self,case):
  b,u,g,p=case
  with patch.object(q,'observe_goal',return_value=g),patch('owner_progression.state',return_value=NS(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):
   return q.execute(u,b,'q',port_factory=p)
 def test_exact_purchase_objective(self):
  rows=[{'text':'동록 살림꾼에게 물건 3개 구매','score':.99},{'text':'1/3','score':.99}]
  self.assertEqual(q.parse_goal(rows)['remaining'],2)
  for text in ('몬스터 3마리 처치','물건 5개 구매','구매','물건 구매 2/4'):
   self.assertIsNone(q.parse_goal([{'text':text,'score':.99}]))
 def test_non_target_roots_no_consumption(self):
  for row in ({'title':'다른 퀘스트','mode':'sub_quest','group':True},{'title':'메마른','mode':'main_quest','group':True},{'title':'메마른','mode':'sub_quest','group':True,'completed':True}):self.assertFalse(q.eligible_root(row))
 def test_buy_three_only_and_never_mark_story_complete(self):
  c=self.setup_case();self.assertTrue(self.run_case(c));b,u,_,_=c
  self.assertIn(('quantity',3),u.port.calls);self.assertNotIn('use',u.port.calls)
  self.assertFalse(b.item['quests']['q']['completed']);self.assertEqual(b.item['quests']['q']['quest_purchase']['bought'],3)
 def test_partial_objective_buys_two(self):
  c=self.setup_case(done=1);self.run_case(c);self.assertIn(('quantity',2),c[1].port.calls)
 def test_only_capacity_shortfall_is_consumed(self):
  c=self.setup_case(room=1);self.run_case(c);self.assertEqual(c[1].port.calls.count('use'),2)
 def test_unknown_use_persists_and_blocks_repeat(self):
  c=self.setup_case(room=0,fail='use')
  with self.assertRaises(q.Pending):self.run_case(c)
  r=c[0].item['quests']['q']['quest_purchase'];self.assertEqual(r['phase'],'use_sent')
  with self.assertRaises(q.Pending):q.remaining_budget(c[2],r)
 def test_unknown_purchase_persists_and_blocks_repeat(self):
  c=self.setup_case(fail='purchase')
  with self.assertRaises(q.Pending):self.run_case(c)
  r=c[0].item['quests']['q']['quest_purchase'];self.assertEqual(r['phase'],'purchase_sent')
  with self.assertRaises(q.Pending):q.remaining_budget(c[2],r)
 def test_bought_without_quest_progress_cannot_rebuy(self):
  with self.assertRaises(q.Pending):q.remaining_budget({'done':0,'total':3,'remaining':3},{'phase':'purchased','goal_before':0,'bought':3})
 def test_duplicate_bought_budget_remains_zero(self):
  self.assertEqual(q.remaining_budget({'done':3,'total':3,'remaining':0},{'phase':'confirmed','bought':3}),0)

if __name__=='__main__':unittest.main()
