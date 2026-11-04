"""Fake policy handoffs with stored list pixels, no game input."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
from owner_gear_settings_candidate import Store
import owner_blessing_navigation_candidate as nav
import owner_blessing_equip_candidate as equip
from owner_blessing_original_fence_candidate import install_runtime

class Tests(unittest.TestCase):
 def test_known_list_reconciles_sent_equip_before_any_next_candidate(self):
  frame=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/blessing_slot1_native_1.png').convert('RGB'))
  service=S(check=lambda:None,capture=lambda:frame.copy());context=S(checkpoint=lambda:None,wait=lambda n:None);seen=[]
  with patch.object(nav,'select_category',return_value=True),patch.object(equip,'scan_filtered',return_value='pending_confirmation'),patch.object(equip,'_paired_rows',return_value=((),[],0)),patch.object(equip,'equip_hit',return_value=None),patch.object(equip,'reconcile_worn_detail',side_effect=lambda *a,**k:seen.append(a[3]) or 'observed_equipped'):
   self.assertEqual(nav.scan_one(service,context,'char',1,[],settings_check=lambda:True),'observed_equipped')
  self.assertEqual(seen,[1])
 def test_unknown_post_equip_stays_held_not_reported_equipped(self):
  frame=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/blessing_slot1_native_1.png').convert('RGB'))
  service=S(check=lambda:None,capture=lambda:frame.copy());context=S(checkpoint=lambda:None,wait=lambda n:None)
  with patch.object(nav,'select_category',return_value=True),patch.object(equip,'scan_filtered',return_value='pending_confirmation'),patch.object(equip,'_paired_rows',return_value=((),[],0)),patch.object(equip,'equip_hit',return_value=None),patch.object(equip,'reconcile_worn_detail',return_value='hold_result_unknown'):
   self.assertEqual(nav.scan_one(service,context,'char',1,[],settings_check=lambda:True),'hold_result_unknown')
 def test_empty_native_rewards_do_not_disable_independent_field_checked_equip_policy(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   store=Store(root,'char');store.write(store.read());seen=[]
   market=S(inspect_growth_equipment=lambda *a,**k:[])
   module=S(run_blessing_rewards=lambda *a:False,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
   def run(*a,**kw):seen.append(kw['settings_check']());return {'state':'hold_field'}
   install_runtime(module,market,lambda a:'char',runner=run)
   adapter=S(project=S(root=Path(root)))
   self.assertIs(module.run_blessing_rewards(adapter,S(checkpoint=lambda:None),None),False)
   self.assertEqual(seen,[True]);self.assertEqual(adapter._owner_blessing_policy_outcome,{'state':'hold_field','native_rewards_confirmed':False})
 def test_native_error_propagates_and_never_enters_policy(self):
  seen=[]
  def fail(*a):raise RuntimeError('unknown navigation')
  module=S(run_blessing_rewards=fail,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
  install_runtime(module,S(inspect_growth_equipment=lambda *a,**k:[]),lambda a:'char',runner=lambda *a,**k:seen.append(1))
  with self.assertRaises(RuntimeError):module.run_blessing_rewards(S(),S(checkpoint=lambda:None),None)
  self.assertEqual(seen,[])

if __name__=='__main__':unittest.main()
