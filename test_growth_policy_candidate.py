import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unittest
from owner_growth_policy_candidate import *
class Policy(unittest.TestCase):
 def test_targets(self):
  self.assertEqual((GEAR_TARGETS['희귀'].enhance,GEAR_TARGETS['희귀'].breakthrough,GEAR_TARGETS['희귀'].awakening),(50,3,1));self.assertEqual(GEAR_TARGETS['영웅'].breakthrough,2)
 def test_grade_transition_only(self):
  for a in ('일반','희귀','영웅'):
   for b in ('일반','희귀','영웅'):self.assertEqual(should_replace(a,b),(a,b)==('일반','희귀'))
 def test_box_requires_level_and_evidence(self):
  s={x:False for x in SKILL_BOX_ORDER};self.assertIsNone(skill_box_next(s,29));self.assertEqual(skill_box_next(s,30),SKILL_BOX_ORDER[0]);s[SKILL_BOX_ORDER[0]]=True;self.assertEqual(skill_box_next(s,30),SKILL_BOX_ORDER[1]);s[SKILL_BOX_ORDER[1]]=None;self.assertIsNone(skill_box_next(s,30))
 def test_destination_requires_proven_exhaustion(self):
  rules=[{'power':120000,'slot':2},{'power':200000,'slot':3}]
  self.assertIsNone(hunt_destination(None,130000,rules));self.assertEqual(hunt_destination(True,130000,rules),'quests');self.assertEqual(hunt_destination(False,119999,rules),'둘러보기 추천');self.assertEqual(hunt_destination(False,120000,rules),rules[0]);self.assertEqual(hunt_destination(False,220000,rules),rules[1]);self.assertIsNone(hunt_destination(False,None,rules))
 def test_invalid_or_ambiguous_rules_are_rejected(self):
  with self.assertRaises(ValueError):choose_hunt_rule(120000,[{'power':120000,'slot':2},{'power':120000,'slot':3}])
  with self.assertRaises(ValueError):choose_hunt_rule(120000,[{'power':100,'slot':0}])
 def test_aoe(self):
  self.assertEqual(len(AOE_SKILLS),8);self.assertEqual(set(AOE_EQUIP),set(AOE_SKILLS));self.assertEqual(ULTIMATE,'대폭발');self.assertEqual(ULTIMATE_USE_INDEX,2)
  self.assertEqual(len(set(AOE_EQUIP[:5]) & {'연쇄 번개','번개 폭풍','요기 폭발','하늘의 심판'}),3)
 def test_two_confirmed_hunt_deaths_use_recommendation(self):
  self.assertEqual(hunt_death_policy(1,{'slot':2}),'재시도');self.assertEqual(hunt_death_policy(2,{'slot':2}),'둘러보기 추천')
  with self.assertRaises(ValueError):hunt_death_policy(None,{'slot':2})
if __name__=='__main__':unittest.main()
