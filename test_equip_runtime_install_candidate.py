import bootstrap
from bootstrap import R,O,A,B,RT,T
C=T
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import owner_equip_runtime_install_candidate as runtime
import owner_equipment_tooltip_candidate as tooltip
import owner_equip_native_gate_candidate as gate

class InstallTests(unittest.TestCase):
 def test_install_preserves_original_and_runs_once_without_duplicate_worker(self):
  from project_adapter import market_inventory
  from project_adapter._entry import Adapter
  calls=[];gui=NS();ctx=NS(checkpoint=lambda:None);adapter=NS(values={'auto_rewards.inventory_use.enabled':True})
  def native(*_):calls.append('native');return True
  with patch.object(gate,'install'),patch.object(market_inventory,'run_inventory_use',native),patch.object(Adapter,'run_inventory_use',native),patch.object(runtime,'_run',side_effect=lambda *_:calls.append('guarded') or 'no_more_visible_candidates'):
   runtime.install(gui);self.assertTrue(market_inventory.run_inventory_use(adapter,ctx,None))
  self.assertEqual(calls,['native','guarded'])
 def test_unknown_modal_never_blindly_closes_or_resumes(self):
  from project_adapter import market_inventory,town_services
  from project_adapter.secret_exploration import AUTO_NAMES
  import owner_startup_stage,owner_progression,owner_equipment_boxes
  f=np.zeros((479,897,3),np.uint8);clicks=[]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  service=NS(check=lambda:None,capture=lambda:f.copy(),detector=NS(),click_hit=lambda x:clicks.append(x))
  adapter=NS()
  with patch.object(town_services,'TownServices',return_value=service),patch.object(owner_startup_stage,'scene',return_value='field'),patch.object(owner_progression,'inventory_parts',return_value=(True,True)),patch.object(market_inventory,'open_inventory',return_value=True),patch.object(tooltip,'run_in_open_inventory',side_effect=tooltip.Hold('unknown modal')),patch.object(owner_equipment_boxes,'close_inventory',side_effect=lambda *_:clicks.append('close')):
   with self.assertRaises(RuntimeError):runtime._run(adapter,ctx,None)
  self.assertEqual(clicks,[])
 def test_skipped_inventory_never_runs_gear_followup(self):
  from project_adapter import market_inventory
  from project_adapter._entry import Adapter
  adapter=NS(values={'auto_rewards.inventory_use.enabled':True});ctx=NS(checkpoint=lambda:None)
  def skipped(a,*_):a._owner_inventory_skip_generation=getattr(a,'_owner_inventory_skip_generation',0)+1;return True
  with patch.object(gate,'install'),patch.object(market_inventory,'run_inventory_use',skipped),patch.object(Adapter,'run_inventory_use',skipped),patch.object(runtime,'_run') as guarded:
   runtime.install(NS());self.assertTrue(market_inventory.run_inventory_use(adapter,ctx,None));guarded.assert_not_called()
 def test_master_off_runs_nothing(self):
  from project_adapter import market_inventory
  from project_adapter._entry import Adapter
  calls=[];adapter=NS(values={'auto_rewards.inventory_use.enabled':False});ctx=NS(checkpoint=lambda:None)
  def native(*_):calls.append('native');return True
  with patch.object(gate,'install'),patch.object(market_inventory,'run_inventory_use',native),patch.object(Adapter,'run_inventory_use',native),patch.object(runtime,'_run') as guarded:
   runtime.install(NS());self.assertFalse(market_inventory.run_inventory_use(adapter,ctx,None));guarded.assert_not_called()
  self.assertEqual(calls,[])
 def test_real_scene_detector_dependencies_on_saved_field(self):
  from owner_startup_stage import scene,DUNGEON,EXIT,MENU
  from roi_runtime import RoiDetector
  from PIL import Image
  names=runtime.scene_detector_names()
  for name in (DUNGEON,EXIT,MENU):self.assertIn(name,names)
  detector=RoiDetector(A/'profiles/DKB',names)
  frame=np.asarray(Image.open(A/'logs/quest-incidents/20261101T205743Z-1bafafd4/screen.png').convert('RGB'))
  self.assertEqual(scene(detector,frame),'field')
  from project_adapter import town_services,market_inventory
  service=NS(check=lambda:None,capture=lambda:frame.copy(),detector=detector)
  ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  with patch.object(town_services,'TownServices',return_value=service),patch.object(market_inventory,'open_inventory',return_value=False):
   with self.assertRaisesRegex(RuntimeError,'인벤토리 열기 미확인'):runtime._run(NS(),ctx,None)

if __name__=='__main__':unittest.main(verbosity=2)
