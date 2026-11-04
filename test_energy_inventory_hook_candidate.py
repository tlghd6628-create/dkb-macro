import unittest,types
from unittest.mock import patch
import owner_equipment_boxes as b
class Tests(unittest.TestCase):
 def setUp(self):
  self.a=types.SimpleNamespace(_owner_inventory_skip_generation=4);self.c=types.SimpleNamespace(checkpoint=lambda:None);self.calls=[]
  self.mods={'owner_schedule_priority':types.SimpleNamespace(hold_reason=lambda a:None),'owner_energy_next_integration_candidate':types.SimpleNamespace(attempt=lambda *a:self.calls.append('energy') or 'ok')}
 def test_admitted_opportunity_calls_same_worker(self):
  with patch.dict('sys.modules',self.mods):self.assertEqual(b.energy_after_inventory(self.a,self.c,None,4),'ok')
  self.assertEqual(self.calls,['energy'])
 def test_scheduler_skip_generation_prevents_any_dispatch(self):
  with patch.dict('sys.modules',self.mods):self.assertEqual(b.energy_after_inventory(self.a,self.c,None,3),'inventory_skipped')
  self.assertEqual(self.calls,[])
 def test_boss_or_combat_hold_prevents_dispatch(self):
  self.mods['owner_schedule_priority'].hold_reason=lambda a:'보스 출발'
  with patch.dict('sys.modules',self.mods):self.assertEqual(b.energy_after_inventory(self.a,self.c,None,4),'priority_hold')
  self.assertEqual(self.calls,[])
 def test_user_stop_prevents_dispatch(self):
  self.c.checkpoint=lambda:(_ for _ in ()).throw(RuntimeError('stop'))
  with patch.dict('sys.modules',self.mods),self.assertRaises(RuntimeError):b.energy_after_inventory(self.a,self.c,None,4)
  self.assertEqual(self.calls,[])
if __name__=='__main__':unittest.main()
