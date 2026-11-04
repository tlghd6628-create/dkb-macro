"""Map-prefix and production-loop regression checks; no game input/state writes."""
from pathlib import Path
import sys,unittest,threading,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from PIL import Image
import numpy as np
from roi_runtime import RoiDetector
from biol_base.session import Cancelled
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES
import owner_startup_stage as st
import owner_dungeon_map as maps
import test_dungeon_exit_scene_20261104 as replay
load,DIPS,INSIDE,EXITED=replay.load,replay.DIPS,replay.INSIDE,replay.EXITED

class MapPrefix(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
 def test_saved_dungeon_maps_have_common_prefix_even_when_icons_dip(self):
  for name in (*DIPS,INSIDE):
   with self.subTest(name=name):
    f=load(name)
    # The event menu can dim/cover the map; strict unknown still must not exit.
    if name=='20261104T000528-7cf2ee15':self.assertNotEqual(st.scene(self.detector,f),'field')
    else:self.assertTrue(maps.map_inside(f));self.assertEqual(st.scene(self.detector,f),'dungeon')
 def test_current_map_name_and_character_are_not_part_of_the_asset(self):
  f=load(INSIDE).copy();f[8:23,47:150]=0;f[130:330,300:600]=0
  self.assertTrue(maps.map_inside(f))
 def test_exit_other_green_text_blank_green_and_wrong_frame_do_not_match(self):
  for f in (load(EXITED),np.zeros((479,897,3),np.uint8),np.full((479,897,3),(10,220,10),np.uint8),np.zeros((720,1280,3),np.uint8)):
   self.assertFalse(maps.map_inside(f))
 def test_map_is_primary_even_with_both_portal_icons_missing(self):
  f=load('20261104T014127-15614380').copy();f[84:99,14:29]=0
  self.assertTrue(maps.inside(self.detector,f));self.assertEqual(st.scene(self.detector,f),'dungeon')
 def test_every_title_layout_after_the_patch_is_read(self):
  # A long name shrinks to two lines; 24-hour maps say [상시 비경].
  F=Path(__file__).resolve().parent/'fixtures_image_scope'
  for name in ('dungeon_normal','dungeon_small','dungeon_always'):
   f=np.array(Image.open(F/(name+'.png')).convert('RGB'))
   with self.subTest(name=name):
    self.assertTrue(maps.title_inside(f));self.assertTrue(maps.map_inside(f))
    blank=f.copy();blank[84:99,14:29]=0
    self.assertEqual(st.scene(self.detector,blank),'dungeon')
 def test_plain_field_titles_are_not_a_dungeon(self):
  F=Path(__file__).resolve().parent/'fixtures_image_scope'
  for name in ('plain_new','field_old','map_new','modal_new'):
   self.assertFalse(maps.map_inside(np.array(Image.open(F/(name+'.png')).convert('RGB'))),name)
 def test_no_map_and_no_portal_really_reaches_field(self):self.assertEqual(st.scene(self.detector,load(EXITED)),'field')
 def test_map_name_survives_background_changes_outside_the_label(self):
  f=np.random.default_rng(40).integers(0,255,(479,897,3),dtype=np.uint8)
  f[8:22,23:49]=load(INSIDE)[8:22,23:49]
  self.assertTrue(maps.map_inside(f))

class SharedTimer(unittest.TestCase):
 def test_startup_calls_the_existing_paired_reader_without_new_ocr(self):
  service=object()
  for v in (None,0,601,18000):
   with patch('owner_reward_context.read_remaining',return_value=v) as read:
    self.assertEqual(st.timer_pair(service),v);read.assert_called_once_with(service)
 def test_stop_propagates(self):
  with patch('owner_reward_context.read_remaining',side_effect=Cancelled()),self.assertRaises(Cancelled):st.timer_pair(object())

class Loop(replay.Resume):
 # The old icon-dip tests now have independent map proof. Hide only the map
 # prefix to test an actually unrecognized frame, never weaken old icon rules.
 def dip(self):
  f=load('20261104T014127-15614380').copy();f[8:22,23:49]=0;return f
 def test_dip_frames_do_not_end_the_dungeon_and_send_nothing(self):
  outcome,inputs,published,_=self.run_frames([self.dip()]*6)
  self.assertEqual(outcome[0],'replay_end');self.assertEqual(inputs,[]);self.assertNotIn('field',published)
 def test_dip_resets_the_field_count(self):
  out=load(EXITED);outcome,_,published,_=self.run_frames([out,out,self.dip(),out,out,self.dip()])
  self.assertEqual(outcome[0],'replay_end');self.assertNotIn('field',published)
 def test_unknown_stays_bounded_with_no_input(self):
  outcome,inputs,_,elapsed=self.run_frames([self.dip()]*60)
  self.assertEqual(outcome[0],'error');self.assertIn('20초',outcome[1]);self.assertEqual(inputs,[])
 def test_zero_timer_does_not_click_exit_while_the_map_is_still_present(self):
  # The real loop observes >30 seconds of stable map after paired zero reads.
  # Mock only the old helper's fixture override so the loop sees zero too.
  original=st.timer_pair
  with patch.object(st,'timer_pair',return_value=0):
   # run_frames itself stubs timer_pair(None), so drive the loop directly.
   f=load(INSIDE);ticks=[0.];calls=[];count=[0]
   def capture():
    count[0]+=1
    if count[0]>75:raise StopIteration
    return f
   ctx=S(checkpoint=lambda:None,wait=lambda s:ticks.__setitem__(0,ticks[0]+s))
   service=S(context=ctx,check=lambda:None,capture=capture,detector=self.detector,button=lambda *a,**k:calls.append(a))
   adapter=S(project=S(root=bootstrap.A,code='DKB'),mode='sub_quest')
   with patch.object(st.time,'monotonic',lambda:ticks[0]),patch.object(st,'publish'),patch('project_adapter.secret_exploration.ensure_auto_active'),self.assertRaises(StopIteration):
    st._resume_dungeon(S(),adapter,ctx,S(),service)
   self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
