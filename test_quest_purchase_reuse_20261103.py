"""Fake native-call tests only; no game actions."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from contextlib import contextmanager
import bootstrap
import owner_quest_purchase as q

class Book:
 def __init__(self):
  self.item={'active':'q','quests':{'q':{'mode':'sub_quest','group':True,'title':'[외전] 메마른 늪의 여흠','completed':False}}};self.writes=[]
 def commit(self):self.writes.append(dict(self.item['quests']['q'].get('quest_purchase',{})))

class Service:
 calls=[]
 def __init__(self,context):self.context=context
 def button(self,name,*a,**k):self.calls.append(name);return True

class Tests(unittest.TestCase):
 def setUp(self):
  Service.calls=[];self.context=NS(checkpoint=lambda:None,wait=lambda *a:None)
  self.adapter=NS(project=NS(root='fake'),values={'common.potion_and_favorite.enabled':False})
  self.ui=NS(adapter=self.adapter,context=self.context,inputs=object(),normal=lambda:True,close_known=lambda:None)
 def test_counter_requires_strong_single_three_target(self):
  self.assertEqual(q.counter([{'text':'1/3','score':.99}]),1)
  for rows in ([{'text':'1/3','score':.8}],[{'text':'1/5','score':1}],[{'text':'0/3','score':1},{'text':'1/3','score':1}]):self.assertIsNone(q.counter(rows))
 def test_non_target_does_not_shop(self):
  self.assertFalse(q.eligible_root({'mode':'sub_quest','group':True,'title':'다른 서사'}))
 def test_sent_record_never_replays(self):
  for phase in ('purchase_sent','await_goal','use_sent'):
   with self.assertRaises(q.Pending):q.needs_purchase({'stage':2,'done':0},{'phase':phase})
 def test_later_stage_and_three_of_three_do_not_buy(self):
  self.assertFalse(q.needs_purchase({'stage':3,'done':None},{}))
  self.assertFalse(q.needs_purchase({'stage':2,'done':3},{}))
 def test_native_button_reused_once_with_durable_before_input(self):
  r={};writes=[]
  with patch('project_adapter.town_services.TownServices',Service),patch('owner_remote_potion_limit_candidate.observed_full',return_value=None):
   with q.native_purchase_watch(self.adapter,self.context,self.ui,r,lambda:writes.append(dict(r)),lambda:True) as e:
    Service(self.context).button('버튼_물약상인_구매')
    self.assertEqual(writes[-1]['phase'],'purchase_sent');self.assertTrue(e['buy_sent'])
    with self.assertRaises(q.Pending):Service(self.context).button('버튼_물약상인_구매')
  self.assertEqual(Service.calls,['버튼_물약상인_구매'])
 def test_full_proof_aborts_before_native_tier_input(self):
  from owner_remote_potion_limit_candidate import observed_full as old
  with patch('project_adapter.town_services.TownServices',Service),patch('owner_remote_potion_limit_candidate.observed_full',return_value=650):
   with q.native_purchase_watch(self.adapter,self.context,self.ui,{},lambda:None,lambda:True) as e:
    with self.assertRaises(q.PotionFull):Service(self.context).button('버튼_물약상인_1단물약')
    self.assertTrue(e['full']);self.assertFalse(e['buy_sent'])
  self.assertFalse(Service.calls)
 def test_other_worker_context_unchanged(self):
  with patch('project_adapter.town_services.TownServices',Service),patch('owner_remote_potion_limit_candidate.observed_full',return_value=650):
   with q.native_purchase_watch(self.adapter,self.context,self.ui,{},lambda:None,lambda:True):
    Service(object()).button('버튼_물약상인_1단물약')
  self.assertEqual(Service.calls,['버튼_물약상인_1단물약'])
 def test_hook_restored_on_error(self):
  original=Service.button
  with patch('project_adapter.town_services.TownServices',Service):
   with self.assertRaises(ValueError):
    with q.native_purchase_watch(self.adapter,self.context,self.ui,{},lambda:None,lambda:True):raise ValueError()
   self.assertIs(Service.button,original)
 def run_execute(self,b,stage):
  with patch.object(q,'observe_stage',return_value=stage),patch('owner_progression.state',return_value=NS(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):
   return q.execute(self.ui,b,'q')
 def test_execute_calls_existing_purchase_without_enabling_optional_feature(self):
  b=Book();calls=[]
  @contextmanager
  def watch(*args):yield {'buy_sent':True,'full':False}
  self.adapter.run_potion_purchase=lambda context,inputs:calls.append('existing')
  with patch.object(q,'native_purchase_watch',watch):self.assertTrue(self.run_execute(b,{'stage':2,'done':0}))
  self.assertEqual(calls,['existing']);self.assertFalse(self.adapter.values['common.potion_and_favorite.enabled'])
  self.assertEqual(b.item['quests']['q']['quest_purchase']['phase'],'await_goal')
  self.assertFalse(b.item['quests']['q']['completed'])
 def test_full_uses_three_then_retries_same_existing_purchase(self):
  b=Book();calls=[]
  @contextmanager
  def watch(*args):yield {'buy_sent':True,'full':False}
  def native(*a):
   calls.append('existing')
   if len(calls)==1:raise q.PotionFull()
  self.adapter.run_potion_purchase=native
  def consume(ui,r,commit,guard):calls.append('use3');r['used']=3
  with patch.object(q,'native_purchase_watch',watch),patch.object(q,'consume_three',consume):
   self.assertTrue(self.run_execute(b,{'stage':2,'done':0}))
  self.assertEqual(calls,['existing','use3','existing'])
 def test_next_stage_confirms_only_purchase_not_chapter(self):
  b=Book();b.item['quests']['q']['quest_purchase']={'phase':'await_goal'}
  self.assertFalse(self.run_execute(b,{'stage':3,'done':None}))
  self.assertEqual(b.item['quests']['q']['quest_purchase']['phase'],'confirmed')
  self.assertFalse(b.item['quests']['q']['completed'])

if __name__=='__main__':unittest.main()
