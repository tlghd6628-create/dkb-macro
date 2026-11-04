"""Actual saved 14:16 frames and fake services; never capture/input the game."""
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import unittest
import bootstrap
import numpy as np
from PIL import Image
from owner_energy_box_detail_candidate import box_candidates,stable_box_candidates
from owner_energy_generic_port_candidate import GenericPort
from owner_energy_legacy_reconcile_candidate import _character
from owner_energy_box_runtime_candidate import Hold
from owner_progression import inventory_parts
from owner_movement import field_hud

FIX=bootstrap.T/'log_review_20261102_1416'
CHAR='256b0f6111f96bcaaf78501c'
def image(name):return np.asarray(Image.open(FIX/name).convert('RGB')).copy()

class Frames(unittest.TestCase):
 def port(self):
  p=GenericPort.__new__(GenericPort)
  p.context=S(checkpoint=lambda:None,wait=lambda delay:None)
  self.current=image('inventory2.png');self.closed=[]
  p.service=S(check=lambda:None,capture=lambda:self.current.copy(),click_hit=lambda hit:self.fail('Unexpected UI input'))
  p.opened=True;p.view='inventory';p.inventory_reference=None
  p.evidence_identity={'character':CHAR};p._last_pair=None
  return p
 def close_inventory(self,service):self.closed.append('known_inventory');self.current=image('error-native.png')
 def test_independent_native_inventory_pairs_locate_the_visible_stack(self):
  a,b=image('inventory1.png'),image('inventory2.png')
  self.assertIn((765,365),box_candidates(a))
  self.assertIn((765,365),box_candidates(b))
  self.assertEqual(stable_box_candidates(a,b),[(765,365)])
 def test_removed_icon_and_field_never_authorize_an_icon_click(self):
  f=image('inventory2.png');f[354:376,754:776]=0
  self.assertEqual(box_candidates(f),[])
  self.assertIsNone(box_candidates(image('error-native.png')))
 def test_actual_map_label_cannot_be_used_as_inventory_character(self):
  field=image('error-native.png')
  self.assertTrue(field_hud(field));self.assertEqual(inventory_parts(field),(False,False))
  self.assertNotEqual(_character(field),CHAR)
  self.assertEqual(_character(image('inventory2.png')),CHAR)
 def test_generic_cleanup_returns_to_actual_field_without_weakening_resource_pair(self):
  import owner_equipment_boxes
  p=self.port()
  with patch.object(owner_equipment_boxes,'close_inventory',side_effect=self.close_inventory):p.close_known()
  self.assertFalse(p.opened);self.assertEqual(p.view,'field');self.assertEqual(self.closed,['known_inventory'])
  self.assertIsNone(p.pair(lambda a,b:self.fail('Resource reader ran on map-name pixels')))
  p.close_known();self.assertEqual(self.closed,['known_inventory'])
 def test_changed_inventory_character_still_blocks_cleanup_input(self):
  import owner_equipment_boxes
  p=self.port();self.current[9:25,68:101]=0
  with patch.object(owner_equipment_boxes,'close_inventory',side_effect=self.close_inventory):
   with self.assertRaises(RuntimeError):p.close_known()
  self.assertEqual(self.closed,[])
 def test_unknown_return_screen_still_stops(self):
  import owner_equipment_boxes
  p=self.port()
  def unknown(service):
   self.close_inventory(service);self.current[440:471,660:790]=0
  with patch.object(owner_equipment_boxes,'close_inventory',side_effect=unknown):
   with self.assertRaises(RuntimeError):p.close_known()
  self.assertTrue(p.opened)
 def test_stop_before_cleanup_does_not_send_input(self):
  import owner_equipment_boxes
  from biol_base.session import Cancelled
  p=self.port();p.context.checkpoint=lambda:(_ for _ in ()).throw(Cancelled())
  with patch.object(owner_equipment_boxes,'close_inventory',side_effect=self.close_inventory):
   with self.assertRaises(Cancelled):p.close_known()
  self.assertEqual(self.closed,[])
 def test_primary_hold_remains_optional_when_proved_cleanup_succeeds(self):
  from test_energy_next_integration_candidate import Tests as Setup
  import owner_energy_next_integration_candidate as integration
  import owner_equipment_boxes
  setup=Setup('test_confirmation_only_without_pending_does_not_construct_ui');setup.setUp();self.addCleanup(setup.doCleanups)
  setup.mods['owner_progression'].inventory_parts=inventory_parts
  setup.p.character=CHAR;setup.a._owner_progression_observation=(setup.ctx,setup.p.observed,CHAR)
  setup.data['pending']={'phase':'sent','operation_id':'a'*32,'name':'생명','quantity':1,'boxes_before':47}
  setup.j.save(setup.data);p=self.port()
  p.current_detail=lambda guard:(_ for _ in ()).throw(Hold('기운 선택상자 아이콘 확인 필요'))
  setup.a._owner_energy_generic_port_factory=lambda *args:p
  with patch.dict('sys.modules',setup.mods),patch.object(owner_equipment_boxes,'close_inventory',side_effect=self.close_inventory):
   self.assertEqual(integration.attempt(setup.a,setup.ctx,None),'held')
  self.assertEqual(setup.j.read()['pending'],setup.data['pending'])
  outcome=setup.a._owner_energy_box_outcome
  self.assertEqual(outcome['reason'],'기운 선택상자 아이콘 확인 필요')
  self.assertTrue(outcome['reconcile_only'])

if __name__=='__main__':unittest.main()
