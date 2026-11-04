import sys,unittest
from pathlib import Path
from PIL import Image
import numpy as np
sys.path.insert(0,r'C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/owner')
sys.path.insert(0,str(Path(__file__).parent))
from owner_energy_box_detail_candidate import detail,detail_screen,evidence_detail,box_location,box_candidates,generic_box_detail
from owner_energy_reward_candidate import dawn_one
from owner_energy_choice_reader_candidate import read_pair,read_open_pair,layout_screen
BASE=Path(__file__).parent/'live_fixtures'
def load(name):return np.array(Image.open(BASE/name).convert('RGB'))
class Tests(unittest.TestCase):
 def test_actual_reconcile_close_keeps_exact_x_when_backdrop_moves(self):
  f=load('energy_detail47_close_native_1.png')
  self.assertTrue(generic_box_detail(f));self.assertEqual(evidence_detail(f),47)
  f[99:112,502:518]=0
  self.assertFalse(generic_box_detail(f));self.assertIsNone(evidence_detail(f))
 def test_detail_real(self):
  for name,want in [('energy_box_detail_native_1.png',50),('energy_box_after49_native_1.png',49),('energy_box_after49_native_2.png',49)]:
   frame=load(name);self.assertEqual(detail(frame),want);self.assertEqual(box_location(frame),(728,328))
 def test_choice_real(self):
  a=load('energy_box_select_native_1.png');b=load('energy_box_select_native_2.png');self.assertEqual(read_pair(a,b)['quantity'],1);self.assertEqual(read_pair(a,b)['available_count'],50);self.assertEqual(read_pair(a,b)['selected'],'생명')
  self.assertIsNone(detail(a));self.assertIsNone(detail_screen(a))
 def test_detail_bad_visual(self):
  f=load('energy_box_after49_native_1.png');f[236:263,383:513]=0;self.assertIsNone(detail(f))
 def test_wrong_box_is_only_closable_not_energy(self):
  f=load('wrong_recalibration_box_044837.png');self.assertTrue(generic_box_detail(f));self.assertIsNone(detail(f))
 def test_two_candidates_not_unique_identity(self):
  f=load('inventory_before_energy_trial_044834.png');self.assertEqual(box_candidates(f),[(839,291),(728,328)]);self.assertIsNone(box_location(f))
 def test_real_unselected_layout_cannot_authorize_commit(self):
  f=load('energy_no_selection_050424.png');self.assertTrue(layout_screen(f))
  value=read_open_pair(f,f.copy());self.assertEqual((value['selected'],value['quantity'],value['available_count']),(None,1,49))
  self.assertIsNone(read_pair(f,f.copy()))
  f[201:220,365:385]=0;self.assertFalse(layout_screen(f))
 def test_stable_unselected_independent_saved_frames(self):
  a,b=(load('energy_initial_unselected_native_'+str(i)+'.png') for i in (1,2))
  value=read_open_pair(a,b);self.assertEqual((value['selected'],value['quantity'],value['available_count']),(None,1,49))
  self.assertIsNone(read_pair(a,b))
 def test_dawn_reward_and_box_48_real_independent_frames(self):
  for name in ('energy_after48_native_00.png','energy_after48_native_18.png'):
   self.assertEqual(evidence_detail(load(name)),48)
  for name in ('energy_reward_dawn_native_06.png','energy_reward_dawn_native_07.png'):
   self.assertTrue(dawn_one(load(name)))
  f=load('energy_reward_dawn_native_07.png');f[164:178,429:469]=0;self.assertFalse(dawn_one(f))
  f=load('energy_reward_dawn_native_07.png');f[151:160,455:465]=0;self.assertFalse(dawn_one(f))
if __name__=='__main__':unittest.main()
