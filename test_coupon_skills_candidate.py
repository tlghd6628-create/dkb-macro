import unittest,sys,time,types
import numpy as np
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,r'C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/owner')
sys.path.insert(0,str(Path(__file__).parent))
import owner_coupon_skills_candidate as m
class Pending(RuntimeError):pass
class Context:
 def checkpoint(self):pass
class Store:
 known_names=set();saved=[]
 def __init__(self,*a):pass
 def known(self,name):return name in self.known_names
 def observed(self,name,*,verified):self.saved.append((name,verified));self.known_names.add(name)
class UI:
 calls=[];closed=0;intent=False
 def __init__(self,*args):self._owner_last_rows_pair=([np.zeros((1,1)),np.ones((1,1))],[time.monotonic(),time.monotonic()],[])
 def normal(self):return True
 def scan_owned(self):return self.skill_rows()
 def skill_rows(self):return []
 def learn_one(self,sid,ledger,**kwargs):
  self.calls.append(sid)
  if self.intent:ledger.item.setdefault('learning_intents',{})[str(sid)]={'status':'intent'};raise Pending('uncertain')
  if sid==84:return True
  raise Pending('not proved')
 def close_known(self):type(self).closed+=1
class Tests(unittest.TestCase):
 def setUp(self):
  Store.known_names=set();Store.saved=[];UI.calls=[];UI.closed=0;UI.intent=False
  self.ctx=Context();self.p=types.SimpleNamespace(character='c',level=30,observed=time.monotonic());self.a=types.SimpleNamespace(project=types.SimpleNamespace(root='x'),_owner_progression_observation=(self.ctx,self.p.observed,'c'))
  self.ledger=types.SimpleNamespace(receipt_key='r',character='c',item={})
  self.mods={'owner_progression':types.SimpleNamespace(state=lambda a:self.p),'owner_hunt_rules_candidate':types.SimpleNamespace(configured_identity=lambda r:'scope'),'owner_skill_goal':types.SimpleNamespace(runtime_ledger=lambda *a:self.ledger,Pending=Pending),'owner_skill_ui':types.SimpleNamespace(SkillUI=UI),'owner_learned_skills_candidate':types.SimpleNamespace(LearnedSkills=Store),'owner_starter_choice_candidate':types.SimpleNamespace(owned_filter_frame=lambda f:True,owned_filter_proved=lambda ui:True)}
 def test_only_positive_learn_recorded(self):
  with patch.dict(sys.modules,self.mods):out=m.process(self.a,self.ctx,None)
  self.assertEqual(UI.calls,[84,68,89]);self.assertEqual(Store.saved,[('생명의 흐름',True)]);self.assertEqual(UI.closed,1);self.assertEqual(out[1][1],'held')
 def test_previously_learned_never_repeated(self):
  Store.known_names={'생명의 흐름','방패 밀기','공간 결계'}
  with patch.dict(sys.modules,self.mods):self.assertEqual(m.process(self.a,self.ctx,None),'already_learned')
  self.assertEqual(UI.calls,[])
 def test_uncertain_sent_intent_stops(self):
  UI.intent=True
  with patch.dict(sys.modules,self.mods):m.process(self.a,self.ctx,None)
  self.assertEqual(UI.calls,[84]);self.assertEqual(Store.saved,[])
 def test_wrong_context_holds_without_ui(self):
  self.a._owner_progression_observation=(object(),self.p.observed,'c')
  with patch.dict(sys.modules,self.mods):self.assertEqual(m.process(self.a,self.ctx,None),'identity_or_level_hold')
  self.assertEqual(UI.calls,[])
 def test_missing_owned_filter_blocks_rows(self):
  self.mods['owner_starter_choice_candidate'].owned_filter_frame=lambda f:False
  ui=UI()
  with patch.dict(sys.modules,self.mods):
   m.require_owned_filter(ui,Pending)
   with self.assertRaises(Pending):ui.scan_owned()
if __name__=='__main__':unittest.main()
