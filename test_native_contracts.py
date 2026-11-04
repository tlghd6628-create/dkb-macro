import bootstrap
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from owner_native_contracts import DetectorPool,NativeContractError,pool_for,region_names

class NativeContracts(unittest.TestCase):
 def test_all_production_definitions_load_from_actual_installed_profile(self):
  pool=DetectorPool(bootstrap.A/'profiles/DKB')
  for role in ('gear','gear_extra','blessing','energy'):
   detector=pool.get(role)
   self.assertTrue(set(region_names(role))<=set(detector.entries))
   next_view=pool.get(role)
   self.assertIsNot(detector,next_view)
   self.assertEqual(set(detector.entries),set(next_view.entries))
  self.assertEqual(pool.loads,4);self.assertEqual(pool.hits,4)
 def test_live_scene_hints_do_not_escape_the_current_borrower(self):
  pool=DetectorPool(bootstrap.A/'profiles/DKB');first=pool.get('gear')
  first._owner_activity_hint='inventory';first._last_frame='test-frame'
  region=next(iter(first.entries));first.entries[region]['x']=-999
  first.entries['temporary_test_region']={}
  second=pool.get('gear')
  self.assertFalse(hasattr(second,'_owner_activity_hint'));self.assertFalse(hasattr(second,'_last_frame'))
  self.assertNotIn('temporary_test_region',second.entries)
  self.assertNotEqual(second.entries[region]['x'],-999)
 def test_missing_original_region_is_rejected_before_navigation(self):
  from project_adapter import achievement_rewards as native
  with patch.object(native,'ENERGY_ENTRY2','버튼_전체매뉴_기운발현_NONEXIST'):
   with self.assertRaises(NativeContractError):DetectorPool(bootstrap.A/'profiles/DKB').get('energy')
 def test_a_different_profile_cannot_reuse_the_old_pool(self):
  service=NS(adapter=NS(project=NS(root=bootstrap.A)))
  first=pool_for(service);self.assertIs(first,pool_for(service))
  service.adapter.project.root=bootstrap.T/'test_scratch/other-project'
  self.assertIsNot(pool_for(service),first)
 def test_failed_preflight_cannot_issue_any_game_input(self):
  from owner_feature_check_live_candidate import MenuProbe
  import threading
  probe=MenuProbe(None,None,threading.Event());probe.service=NS();probe._init=lambda:None
  probe.context=NS(checkpoint=lambda:None)
  probe.button=lambda *a:self.fail('must not navigate')
  with patch('owner_feature_check_live_candidate.validate_feature',side_effect=NativeContractError('missing region')):
   row=probe({'id':'gear_enhance'},probe.cancel)
  self.assertEqual((row['stage'],row['finding']),('contract','contract_error'))
  self.assertEqual(probe.navigation,[])

if __name__=='__main__':unittest.main()
