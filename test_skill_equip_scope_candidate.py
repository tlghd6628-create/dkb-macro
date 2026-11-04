"""Verify target row only, using fake UI; no game input."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_skill_ui as mod

class UI:
 def __init__(self,state):
  self.state=state;self.actions=[];self.equipped=False
  self.context=SimpleNamespace(wait=lambda _:None)
 def current_slots(self,unlocked):
  out=[None]*8
  if self.equipped:out[0]=84
  return out
 def find_skill(self,sid):return {'y':130,'id':sid}
 def rows(self,box):
  if box!=(798,115,35,30):raise AssertionError('must read only requested row')
  return [{'text':self.state,'score':.99}]
 def click_word(self,text,box,proof,**kwargs):
  if not proof(object()):raise mod.Pending('row changed')
  self.actions.append((text,box))
  if text=='장착':self.equipped=True
 def click(self,x,y,proof):
  if not proof(object()):raise mod.Pending('screen changed')
  self.actions.append(('slot',x,y))
 def wait(self,predicate):return None

class Tests(unittest.TestCase):
 def test_only_matching_row_can_be_removed_and_equipped(self):
  for state in ('해제','장착'):
   ui=UI(state)
   with patch.object(mod,'skill_screen',return_value=True),patch.object(mod,'identify_icon',return_value=84):
    mod.SkillUI.equip(ui,84,0)
   self.assertEqual(ui.actions[-1],('장착',(798,115,35,30)))
   self.assertEqual(sum(a[0]=='해제' for a in ui.actions),int(state=='해제'))
 def test_unreadable_or_changed_row_cannot_click(self):
  ui=UI('확인 중')
  with patch.object(mod,'skill_screen',return_value=True),patch.object(mod,'identify_icon',return_value=84):
   with self.assertRaises(mod.Pending):mod.SkillUI.equip(ui,84,0)
  self.assertEqual(ui.actions,[])
  ui=UI('해제')
  with patch.object(mod,'skill_screen',return_value=True),patch.object(mod,'identify_icon',return_value=89):
   with self.assertRaises(mod.Pending):mod.SkillUI.equip(ui,84,0)
  self.assertEqual(ui.actions,[])
if __name__=='__main__':unittest.main(verbosity=2)
