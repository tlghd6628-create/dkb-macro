import unittest,sys,types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,r'C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/owner')
sys.path.insert(0,str(Path(__file__).parent))
from test_energy_box_port_candidate import Context,Service
from owner_energy_generic_port_candidate import GenericPort
class Tests(unittest.TestCase):
 def test_unknown_detail_count_uses_paired_selection_count_for_one(self):
  fake=types.ModuleType('project_adapter');fake.market_inventory=types.SimpleNamespace(open_inventory=lambda service:True)
  p=GenericPort.__new__(GenericPort);p.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root='.'));p.context=Context();p.service=Service();p.opened=False
  with patch.dict(sys.modules,{'project_adapter':fake}),patch('owner_energy_generic_port_candidate.detail',return_value=None):
   q=p.prepare_one('여명',lambda:True)
  self.assertEqual(q['boxes'],49);self.assertEqual(q['quantity'],1);self.assertIsNone(q['detail_boxes']);self.assertIs(q['detail_identity'],True)
 def test_paired_known_detail_disagreement_blocks(self):
  from owner_energy_box_runtime_candidate import Hold
  fake=types.ModuleType('project_adapter');fake.market_inventory=types.SimpleNamespace(open_inventory=lambda service:True)
  p=GenericPort.__new__(GenericPort);p.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root='.'));p.context=Context();p.service=Service();p.opened=False
  with patch.dict(sys.modules,{'project_adapter':fake}),patch('owner_energy_generic_port_candidate.detail',return_value=48),self.assertRaises(Hold):p.prepare_one('여명',lambda:True)
  self.assertNotIn((449,356),p.service.clicks)
if __name__=='__main__':unittest.main()
