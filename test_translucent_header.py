"""Independent actual modal frames and fake inputs; no UI/capture calls."""
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import time,unittest
import bootstrap
import numpy as np
from PIL import Image
from owner_ui_foreground import same_dimmed_text
from owner_energy_generic_port_candidate import GenericPort
from owner_energy_choice_reader_candidate import read_open_pair
from owner_energy_legacy_reconcile_candidate import _character
from owner_energy_box_runtime_candidate import Hold
from biol_base.session import Cancelled
CHAR='256b0f6111f96bcaaf78501c'
def frame(name):return np.asarray(Image.open(bootstrap.T/'translucent_20261102'/name).convert('RGB')).copy()

class Tests(unittest.TestCase):
 def port(self):
  p=GenericPort.__new__(GenericPort);self.current=frame('normal.png');self.actions=[]
  p.context=S(checkpoint=lambda:None,wait=lambda delay:None)
  p.service=S(check=lambda:None,capture=lambda:self.current.copy(),click_hit=lambda h:self.actions.append(h))
  p.evidence_identity={'character':CHAR};return p
 def compare(self,reference,current):
  return same_dimmed_text(reference[9:25,68:101],current[9:25,68:101],reference[11:23,34:53],current[11:23,34:53])
 def test_actual_both_dimmed_sources_restore_exact_original_name_pixels(self):
  original=frame('normal.png')
  for name in ('selection1.png','selection2.png'):
   current=frame(name)
   self.assertNotEqual(_character(current),CHAR)
   self.assertTrue(self.compare(original,current))
 def test_known_modal_two_frame_pair_is_readable_after_proved_plain_header(self):
  p=self.port();self.assertTrue(p.same_character(self.current))
  self.current=frame('selection1.png')
  result=p.pair(read_open_pair)
  self.assertEqual((result[0]['selected'],result[0]['quantity'],result[0]['available_count']),(None,1,46))
 def test_same_known_modal_allows_one_guarded_fake_selection_click(self):
  p=self.port();self.assertTrue(p.same_character(self.current));self.current=frame('selection2.png')
  state=read_open_pair(self.current,self.current.copy())
  p.click(450,169,lambda:True,lambda f:read_open_pair(f,f.copy())==state)
  self.assertEqual(len(self.actions),1)
 def test_dimmed_header_without_plain_character_proof_remains_blocked(self):
  p=self.port();self.current=frame('selection1.png')
  self.assertFalse(p.same_character(self.current))
 def test_changed_name_is_not_blessed_by_the_dimming_model(self):
  p=self.port();self.assertTrue(p.same_character(self.current));self.current=frame('selection1.png')
  self.current[9:25,68:101]=np.roll(self.current[9:25,68:101],2,axis=1)
  self.assertFalse(p.same_character(self.current))
  with self.assertRaises(Hold):p.click(449,356,lambda:True,lambda f:True)
  self.assertEqual(self.actions,[])
 def test_transition_and_unknown_overlay_are_not_accepted_as_ready_selection(self):
  p=self.port();self.assertTrue(p.same_character(self.current));self.current=frame('transition.png')
  self.assertFalse(p.same_character(self.current))
  self.current=frame('selection1.png');self.current[108:120,417:481]=0
  self.assertFalse(p.same_character(self.current))
 def test_reference_cannot_cross_context_character_or_lifetime(self):
  for change in ('context','character','age'):
   p=self.port();self.assertTrue(p.same_character(self.current));self.current=frame('selection1.png')
   if change=='context':p.context=S(checkpoint=lambda:None,wait=lambda delay:None)
   elif change=='character':p.evidence_identity['character']='other'
   else:p._character_reference['at']=time.monotonic()-181
   self.assertFalse(p.same_character(self.current),change)
 def test_anchor_shape_change_is_not_treated_as_global_dimming(self):
  a,b=frame('normal.png'),frame('selection1.png');b[11:23,34:53]=np.roll(b[11:23,34:53],2,axis=1)
  self.assertFalse(self.compare(a,b))
 def test_stop_still_prevents_any_click(self):
  p=self.port();self.assertTrue(p.same_character(self.current));self.current=frame('selection1.png')
  p.context.checkpoint=lambda:(_ for _ in ()).throw(Cancelled())
  with self.assertRaises(Cancelled):p.click(450,169,lambda:True,lambda f:True)
  self.assertEqual(self.actions,[])
 def test_existing_single_digit_level_name_location_is_supported(self):
  from owner_ui_foreground import inventory_header
  p=self.port();normal=self.current.copy();name=normal[9:25,68:101].copy()
  normal[9:25,62:101]=0;normal[9:25,62:95]=name
  self.assertEqual(inventory_header(normal,CHAR)[0],62)
  self.assertTrue(p.same_character(normal))
  dim=frame('selection1.png');name=dim[9:25,68:101].copy()
  dim[9:25,62:101]=0;dim[9:25,62:95]=name
  self.assertTrue(p.same_character(dim))

class CleanupTests(unittest.TestCase):
 def setup_case(self):
  from test_energy_next_integration_candidate import Tests as Setup
  test=Setup('test_confirmation_only_without_pending_does_not_construct_ui');test.setUp();self.addCleanup(test.doCleanups)
  test.data['pending']={'phase':'sent','operation_id':'a'*32,'name':'생명','quantity':1,'boxes_before':47};test.j.save(test.data)
  return test
 def test_failed_known_cleanup_does_not_fall_through_to_another_job(self):
  import owner_energy_next_integration_candidate as integration
  t=self.setup_case()
  port=S(current_detail=lambda guard:(_ for _ in ()).throw(Hold('ordinary resource hold')),
         close_known=lambda:(_ for _ in ()).throw(Hold('dialog still visible')))
  t.a._owner_energy_generic_port_factory=lambda *args:port
  with patch.dict('sys.modules',t.mods):
   with self.assertRaises(integration.NavigationError):integration.attempt(t.a,t.ctx,None)
  self.assertEqual(t.j.read()['pending'],t.data['pending'])
  self.assertEqual(t.a._owner_energy_box_outcome['state'],'cleanup_blocked')
 def test_cancel_during_cleanup_is_not_converted_into_navigation_failure(self):
  import owner_energy_next_integration_candidate as integration
  t=self.setup_case();port=S(current_detail=lambda guard:(_ for _ in ()).throw(Hold('ordinary hold')),
                           close_known=lambda:(_ for _ in ()).throw(Cancelled()))
  t.a._owner_energy_generic_port_factory=lambda *args:port
  with patch.dict('sys.modules',t.mods):
   with self.assertRaises(Cancelled):integration.attempt(t.a,t.ctx,None)

if __name__=='__main__':unittest.main()
