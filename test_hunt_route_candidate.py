exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_hunt_route_candidate import route_hunt,hunt_scope
class Cases(unittest.TestCase):
 def test_saved_slot_for_highest_rule_and_restores_values(self):
  original={'keep':True};s=NS(available_slots=lambda *a:[0,1]);c=NS(checkpoint=lambda:None);events=[]
  a=NS(values=original)
  def hunt(*a2):events.append((a.values['common.potion_and_favorite.source'],a.values['common.potion_and_favorite.slot'],s.available_slots()));return True
  a.run_favorite_hunt=hunt
  self.assertTrue(route_hunt(a,c,None,120000,[{'power':120000,'slot':2}],lambda *a:False,s));self.assertEqual(events,[('저장위치','2번',[1])]);self.assertIs(a.values,original);self.assertEqual(s.available_slots(),[0,1])
 def test_missing_slot_must_not_use_another(self):
  s=NS(available_slots=lambda *a:[0]);a=NS(values={},run_favorite_hunt=lambda *args:s.available_slots());c=NS(checkpoint=lambda:None)
  with self.assertRaises(RuntimeError):route_hunt(a,c,None,120000,[{'power':120000,'slot':2}],lambda *a:False,s)
  self.assertEqual(s.available_slots(),[0])
 def test_low_power_uses_guide_unknown_never_guesses(self):
  s=NS(available_slots=lambda *a:[]);a=NS(values={});c=NS(checkpoint=lambda:None)
  self.assertEqual(route_hunt(a,c,None,119999,[{'power':120000,'slot':2}],lambda *a:'guide',s),'guide')
  with self.assertRaises(ValueError):route_hunt(a,c,None,None,[],lambda *a:'guide',s)
 def test_native_missing_favorite_is_not_silently_replaced(self):
  from owner_town_return import MissingFavorite
  def missing(*args):raise MissingFavorite()
  s=NS(available_slots=missing);a=NS(values={},run_favorite_hunt=lambda *args:s.available_slots());c=NS(checkpoint=lambda:None)
  with self.assertRaises(RuntimeError):route_hunt(a,c,None,120000,[{'power':120000,'slot':2}],lambda *a:'guide',s)
 def test_hunt_scope_preserves_slot_for_chores_and_restores_after_exception(self):
  seen=[];s=NS(available_slots=lambda *a:[0,1]);c=NS(checkpoint=lambda:None);old={'keep':True};a=NS(values=old)
  def hunt(*args):seen.append((a.values['common.potion_and_favorite.slot'],s.available_slots()));return True
  a.run_favorite_hunt=hunt
  with self.assertRaises(InterruptedError):
   with hunt_scope(a,NS(power=120000),[{'power':120000,'slot':2}],lambda *a:False,s):
    self.assertTrue(a.run_favorite_hunt(c,None));self.assertTrue(a.run_favorite_hunt(c,None));raise InterruptedError()
  self.assertEqual(seen,[('2번',[1]),('2번',[1])]);self.assertIs(a.run_favorite_hunt,hunt);self.assertIs(a.values,old)
if __name__=='__main__':unittest.main()
