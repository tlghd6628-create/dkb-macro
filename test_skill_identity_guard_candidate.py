"""Simulated input-only checks; never connects to the game."""
import sys,unittest
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from owner_skill_ui import SkillUI,Pending

class Tests(unittest.TestCase):
 def setUp(self):
  self.calls=[];self.ui=object.__new__(SkillUI)
  self.ui.context=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None)
  self.ui.frame=lambda:object();self.ui.touched=False
  self.ui.service=SimpleNamespace(click_hit=lambda h:self.calls.append(('click',h)),key=lambda k:self.calls.append(('key',k)))
  self.ui.inputs=SimpleNamespace(transaction=lambda:nullcontext(),move=lambda *a:self.calls.append(('move',a)),
   down=lambda *a:self.calls.append(('down',a)),up=lambda *a:self.calls.append(('up',a)))
 def test_changed_identity_blocks_click_and_key(self):
  self.ui._owner_identity_guard=lambda:False
  with self.assertRaises(Pending):self.ui.click(1,2,lambda _:True)
  with self.assertRaises(Pending):self.ui.key(65)
  self.assertEqual(self.calls,[])
 def test_optional_guard_keeps_unrelated_mission_ui_behavior(self):
  self.ui.click(1,2,lambda _:True);self.ui.key(65)
  self.assertEqual([row[0] for row in self.calls],['click','key'])
 def test_identity_change_during_drag_still_releases_held_mouse(self):
  calls=[0]
  def guard():calls[0]+=1;return calls[0]<3
  self.ui._owner_identity_guard=guard
  with self.assertRaises(Pending):self.ui.drag((1,2),(4,5),lambda _:True)
  self.assertIn(('down',('mouse','left')),self.calls)
  self.assertIn(('up',('mouse','left')),self.calls)
 def test_guard_failure_before_press_does_not_emit_unneeded_release(self):
  calls=[0]
  def guard():calls[0]+=1;return calls[0]<2
  self.ui._owner_identity_guard=guard
  with self.assertRaises(Pending):self.ui.drag((1,2),(4,5),lambda _:True)
  self.assertFalse(any(item[0] in ('down','up') for item in self.calls))
 def test_guard_failure_during_clear_releases_only_pressed_control(self):
  calls=[0]
  def guard():calls[0]+=1;return calls[0]<2
  self.ui._owner_identity_guard=guard
  with self.assertRaises(Pending):self.ui.clear_text()
  self.assertEqual(self.calls,[('down',('key',0x11)),('up',('key',0x11))])
 def test_observed_character_scope_freshness_and_context_are_fenced(self):
  from owner_skill_goal import same_skill_context
  context=object();adapter=SimpleNamespace(project=SimpleNamespace(root='test'),_owner_skill_context=context)
  record=SimpleNamespace(character='A',observed=100.)
  with patch('owner_progression.state',return_value=record),\
       patch('owner_hunt_rules_candidate.configured_identity',return_value='server1'),\
       patch('owner_skill_goal.time.monotonic',return_value=200.):
   self.assertTrue(same_skill_context(adapter,context,'A','server1'))
   self.assertFalse(same_skill_context(adapter,context,'B','server1'))
   self.assertFalse(same_skill_context(adapter,context,'A','server2'))
   self.assertFalse(same_skill_context(adapter,object(),'A','server1'))
   record.observed=-101.
   self.assertFalse(same_skill_context(adapter,context,'A','server1'))
if __name__=='__main__':unittest.main(verbosity=2)
