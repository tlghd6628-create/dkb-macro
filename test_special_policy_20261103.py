"""Fake-call admission/routing only. No actual entry, purchase or gameplay."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import bootstrap
import owner_schedule_priority as p
from owner_chore_transition import ancillary_field_ready
import owner_membership as m

class SpecialPolicy(unittest.TestCase):
 def setUp(self):
  self.context=S(checkpoint=Mock());self.inputs=S()
  self.adapter=S(project=S(root=bootstrap.T/'test_scratch/never'),values={})
  self.previous=getattr(p.LOCAL,'combat',None);p.LOCAL.combat=None
  self.addCleanup(setattr,p.LOCAL,'combat',self.previous)
 def ui(self,kind):
  self.adapter._owner_mission_ui=S(context=self.context,inputs=self.inputs,
   frame=lambda:kind,normal_frame=lambda frame:frame in ('field_walking','field_hunting'))
 def test_walking_is_allowed_without_distance_or_auto_move_gate(self):
  self.ui('field_walking')
  self.adapter.auto_move=True;self.adapter.distance=1200
  self.assertTrue(ancillary_field_ready(self.adapter,self.context,self.inputs))
 def test_transition_instance_and_unknown_do_not_admit_new_chores(self):
  for kind in ('black','loading','boss','dungeon','dialogue','unknown'):
   with self.subTest(kind=kind):
    self.ui(kind);self.assertFalse(ancillary_field_ready(self.adapter,self.context,self.inputs))
 def test_field_return_admits_same_job_without_recording_completion(self):
  self.ui('black');self.adapter.intent={'phase':'sent','nonce':'keep'}
  self.assertFalse(ancillary_field_ready(self.adapter,self.context,self.inputs))
  self.ui('field_walking');self.assertTrue(ancillary_field_ready(self.adapter,self.context,self.inputs))
  self.assertEqual(self.adapter.intent,{'phase':'sent','nonce':'keep'})
 def test_nested_instance_ownership_restores_even_on_unwind(self):
  with p.activity_scope('비경'):
   self.assertIn('비경',p.hold_reason(self.adapter))
   with self.assertRaises(ValueError):
    with p.activity_scope('보스'):raise ValueError('transition')
   self.assertEqual(p.LOCAL.combat,'비경')
  self.assertIsNone(p.LOCAL.combat)
 def test_native_dungeon_service_owns_instance_until_return(self):
  seen=[]
  def native(*a,**kw):seen.append(p.LOCAL.combat);return True
  def scheduled(original,label,args,kwargs,adapter):return original(*args,**kwargs)
  with patch.object(p,'reservation_hold',return_value=None),patch('owner_timetable.scheduled_call',side_effect=scheduled):
   self.assertTrue(p.service_wrapper(native,'비경탐험')(self.adapter,self.context,self.inputs))
  self.assertEqual(seen,['비경탐험']);self.assertIsNone(p.LOCAL.combat)
 def test_ancillary_service_is_deferred_not_called_inside_instance(self):
  native=Mock()
  with p.activity_scope('보스'):
   self.assertTrue(p.service_wrapper(native,'성장 장비·가호')(self.adapter,self.context,self.inputs))
  native.assert_not_called()
 def test_paid_potion_uses_only_existing_remote_route(self):
  ordinary=Mock(side_effect=AssertionError('no NPC travel'))
  with p.activity_scope('비경'),patch.object(m,'paid',return_value=True),patch.object(m,'remote_purchase',return_value=True) as remote:
   self.assertTrue(m.route_potion_purchase(ordinary,self.adapter,self.context,self.inputs))
  remote.assert_called_once_with(self.adapter,self.context,self.inputs);ordinary.assert_not_called()
 def test_unpaid_instance_never_falls_back_to_town(self):
  ordinary=Mock();remote=Mock()
  with p.activity_scope('비경'),patch.object(m,'paid',return_value=False),patch.object(m,'remote_purchase',remote):
   self.assertFalse(m.route_potion_purchase(ordinary,self.adapter,self.context,self.inputs))
  ordinary.assert_not_called();remote.assert_not_called()
 def test_unpaid_field_preserves_existing_town_route(self):
  ordinary=Mock(return_value=True)
  with patch.object(m,'paid',return_value=False):
   self.assertTrue(m.route_potion_purchase(ordinary,self.adapter,self.context,self.inputs))
  ordinary.assert_called_once_with(self.adapter,self.context,self.inputs)
 def test_initial_dungeon_resume_owns_scope(self):
  import owner_startup_stage as stage
  observed=[]
  with patch.object(stage,'_resume_dungeon',side_effect=lambda *a,goal=None:observed.append((p.LOCAL.combat,goal))):
   stage.resume_dungeon(None,self.adapter,self.context,self.inputs,None)
  self.assertEqual(observed[0][0],'비경·던전');self.assertEqual(len(observed),1);self.assertIsNone(p.LOCAL.combat)
 def test_original_detector_on_saved_field_and_real_black_transition(self):
  import numpy as np
  from PIL import Image
  from roi_runtime import RoiDetector
  from owner_equip_runtime_install_candidate import scene_detector_names
  from owner_startup_stage import scene
  detector=RoiDetector(bootstrap.A/'profiles/DKB',scene_detector_names())
  field=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261101T205743Z-1bafafd4/screen.png').convert('RGB'))
  black=np.asarray(Image.open(bootstrap.A/'logs/quest-incidents/20261103T031053Z-e4c09c90/screen.png').convert('RGB'))
  self.adapter._owner_mission_ui=S(context=self.context,inputs=self.inputs,
   frame=lambda:field,normal_frame=lambda f:scene(detector,f)=='field')
  self.assertTrue(ancillary_field_ready(self.adapter,self.context,self.inputs))
  self.adapter._owner_mission_ui.frame=lambda:black
  self.assertFalse(ancillary_field_ready(self.adapter,self.context,self.inputs))

if __name__=='__main__':unittest.main()
