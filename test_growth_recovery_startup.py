from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
from types import SimpleNamespace as NS
from unittest.mock import patch
import time,unittest
import owner_growth_recovery as r

class Tests(unittest.TestCase):
 def fixture(self):
  ctx=NS(checkpoint=lambda:None,input_depth=0)
  p=NS(character='actual',level=50,observed=time.monotonic())
  a=NS(project=NS(root=Path('unused')),values={'auto_growth.equipment.enabled':True},
   _owner_progression=p,_owner_progression_observation=(ctx,p.observed,'actual'))
  return a,ctx,NS(held=())
 def test_no_pending_avoids_all_navigation(self):
  a,c,i=self.fixture()
  with patch('owner_program_runtime.gear_identity',return_value='profile'),patch.object(r,'pending',return_value=None),patch('owner_gear_reconcile_entry_candidate.run') as run:
   self.assertEqual(r.recover(a,c,i),'no_pending');run.assert_not_called()
   self.assertEqual(r.recover(a,c,i),'already_checked')
 def test_sent_same_profile_runs_receipt_only_once(self):
  a,c,i=self.fixture();item={'phase':'sent','kind':'enhance','before':NS(character='profile')}
  with patch('owner_program_runtime.gear_identity',return_value='profile'),patch.object(r,'pending',return_value=item),patch('owner_gear_reconcile_entry_candidate.run',return_value={'state':'observed_progress'}) as run:
   self.assertEqual(r.recover(a,c,i),'observed_progress')
   self.assertEqual(r.recover(a,c,i),'already_checked');run.assert_called_once_with(a,c,i,'profile')
 def test_wrong_context_disabled_or_foreign_intent_never_navigates(self):
  a,c,i=self.fixture();a._owner_progression_observation=(object(),a._owner_progression.observed,'actual')
  with patch('owner_gear_reconcile_entry_candidate.run') as run:
   self.assertEqual(r.recover(a,c,i),'hold_identity');run.assert_not_called()
  a,c,i=self.fixture();a.values['auto_growth.equipment.enabled']=False
  self.assertEqual(r.recover(a,c,i),'disabled')
  a,c,i=self.fixture();item={'phase':'sent','kind':'enhance','before':NS(character='other')}
  with patch('owner_program_runtime.gear_identity',return_value='profile'),patch.object(r,'pending',return_value=item),patch('owner_gear_reconcile_entry_candidate.run') as run:
   self.assertEqual(r.recover(a,c,i),'hold_history');run.assert_not_called()
 def test_navigation_failure_is_not_claimed_or_swallowed(self):
  a,c,i=self.fixture();item={'phase':'sent','kind':'enhance','before':NS(character='profile')}
  with patch('owner_program_runtime.gear_identity',return_value='profile'),patch.object(r,'pending',return_value=item),patch('owner_gear_reconcile_entry_candidate.run',side_effect=RuntimeError('unknown screen')):
   with self.assertRaises(RuntimeError):r.recover(a,c,i)
if __name__=='__main__':unittest.main()
