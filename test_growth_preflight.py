from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import time,unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
import owner_progression,owner_quest_preflight
from owner_program_runtime import fresh_growth_identity,install_identity_preflight
class Tests(unittest.TestCase):
 def test_new_context_cannot_reuse_previous_character_receipt(self):
  old=NS(character='A',level=50,observed=time.monotonic());adapter=NS();ctx=NS(checkpoint=lambda:None)
  with patch.object(owner_progression,'state',return_value=old),patch.object(owner_quest_preflight,'read_power',return_value=False) as read:
   self.assertFalse(fresh_growth_identity(adapter,ctx,None));read.assert_called_once()
 def test_fresh_actual_character_can_allow_growth_with_unknown_power(self):
  receipt=NS(character=None,level=None,observed=0);adapter=NS();ctx=NS(checkpoint=lambda:None)
  def read(*a):receipt.character='A';receipt.level=50;receipt.power=None;receipt.observed=time.monotonic();return False
  with patch.object(owner_progression,'state',return_value=receipt),patch.object(owner_quest_preflight,'read_power',side_effect=read):
   self.assertTrue(fresh_growth_identity(adapter,ctx,None))
   self.assertIs(adapter._owner_growth_identity_context,ctx)
 def test_stale_same_context_requires_new_pair(self):
  ctx=NS(checkpoint=lambda:None);adapter=NS(_owner_growth_identity_context=ctx)
  receipt=NS(character='A',level=50,observed=time.monotonic()-181)
  with patch.object(owner_progression,'state',return_value=receipt),patch.object(owner_quest_preflight,'read_power',return_value=False):
   self.assertFalse(fresh_growth_identity(adapter,ctx,None))
 def test_energy_identity_hold_continues_without_calling_native_or_completion(self):
  called=[];module=NS(run_energy_entry=lambda *a,**kw:called.append('native'))
  install_identity_preflight(module,'run_energy_entry',())
  adapter=NS(values={'auto_growth.energy.enabled':True})
  with patch('owner_program_runtime.fresh_growth_identity',return_value=False):
   self.assertTrue(module.run_energy_entry(adapter,None,None,process=True))
  self.assertEqual(called,[])
  self.assertEqual(adapter._owner_energy_outcome['status'],'held')
 def test_energy_navigation_exception_is_not_hidden(self):
  def native(*args,**kwargs):raise RuntimeError('navigation failed')
  module=NS(run_energy_entry=native);install_identity_preflight(module,'run_energy_entry',())
  with patch('owner_program_runtime.fresh_growth_identity',return_value=True),self.assertRaises(RuntimeError):
   module.run_energy_entry(NS(values={'auto_growth.energy.enabled':True}),None,None,process=True)
 def test_paired_current_context_receipt_avoids_reopening_during_transition(self):
  ctx=NS(checkpoint=lambda:None);receipt=NS(character='A',level=50,observed=time.monotonic())
  adapter=NS(_owner_progression_observation=(ctx,receipt.observed,'A'))
  with patch.object(owner_progression,'state',return_value=receipt),patch.object(owner_quest_preflight,'read_power') as read:
   self.assertTrue(fresh_growth_identity(adapter,ctx,None));read.assert_not_called()
 def test_another_context_receipt_cannot_authorize_current_growth(self):
  ctx=NS(checkpoint=lambda:None);receipt=NS(character='A',level=50,observed=time.monotonic())
  adapter=NS(_owner_progression_observation=(object(),receipt.observed,'A'))
  with patch.object(owner_progression,'state',return_value=receipt),patch.object(owner_quest_preflight,'read_power',return_value=False):
   self.assertFalse(fresh_growth_identity(adapter,ctx,None))
 def test_growth_identity_hold_is_nonfatal_and_marked_incomplete(self):
  called=[];module=NS(run_growth_entry=lambda *a,**kw:called.append('native'))
  install_identity_preflight(module,'run_growth_entry',());adapter=NS(values={'auto_growth.equipment.enabled':True})
  with patch('owner_program_runtime.fresh_growth_identity',return_value=False):
   self.assertTrue(module.run_growth_entry(adapter,None,None))
  self.assertEqual(called,[]);self.assertTrue(adapter._owner_growth_pending_hold)
  self.assertTrue(adapter._owner_growth_preflight_hold)
if __name__=='__main__':unittest.main()
