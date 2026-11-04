from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest,tempfile
import owner_energy_box_runtime_candidate as r
class Tests(unittest.TestCase):
 def test_disabled_respects_user_without_reader_or_navigation(self):
  with patch.object(r,'run_after_inventory') as action:
   self.assertEqual(r.attempt(NS(values={}),object(),object()),'disabled')
  action.assert_not_called()
 def test_box_hold_is_not_fatal_or_success(self):
  with patch.object(r,'run_after_inventory',side_effect=r.Hold('pending')):
   self.assertEqual(r.attempt(NS(values={'auto_rewards.inventory_use.enabled':True}),object(),object()),'held')
 def test_unknown_navigation_still_propagates(self):
  with patch.object(r,'run_after_inventory',side_effect=RuntimeError('unknown screen')):
   with self.assertRaises(RuntimeError):r.attempt(NS(values={'auto_rewards.inventory_use.enabled':True}),object(),object())
 def test_completed_starter_receipt_defers_energy_until_quest_auto(self):
  from owner_startup_receipts import Preparation
  from owner_mission_controller import prepare
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as folder:
   root=Path(folder);preparation=Preparation(root,'paired-character')
   preparation.worn({'무기':True,'반지':True,'팔찌':True})
   context=NS(checkpoint=lambda:None)
   adapter=NS(mode='sub_quest',project=NS(root=root),exit_sleep_mode=lambda *args:None,
      values={'auto_rewards.inventory_use.enabled':True})
   progress=NS(character='paired-character',level=50,power=103976)
   with patch('owner_progression.state',return_value=progress),patch('owner_quest_preflight.read_power',return_value=True),patch('owner_growth_recovery.recover'),patch('owner_energy_next_integration_candidate.attempt',return_value='held') as boxes:
    self.assertIs(prepare(adapter,context,None),progress)
    self.assertIs(adapter._owner_bootstrapped_context,context)
    boxes.assert_not_called()
    self.assertIn('auto_rewards.inventory_use.enabled',adapter._owner_pending_services['keys'])
    prepare(adapter,context,None)
    boxes.assert_not_called()
if __name__=='__main__':unittest.main()
