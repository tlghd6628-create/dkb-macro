"""Dipped dungeon markers must not read as field. Saved frames and fake services only; never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_startup_stage as st
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES

F=Path(__file__).resolve().parent/'fixtures_dungeon_exit'
DIPS=('20261101T075913-c214458c','20261104T000528-7cf2ee15','20261104T014127-15614380')
INSIDE='20261104T014125-7df40d8d'
EXITED='20261101T080944-7d26accc'

def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))

class Clock:
 def __init__(self):self.now=0.
 def monotonic(self):return self.now
 def __getattr__(self,name):return getattr(__import__('time'),name)

class Scene(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))

 def test_real_dipped_frames_are_not_field(self):
  for name in DIPS:
   # The map-prefix check added later may read these as dungeon; either is safe.
   with self.subTest(name):self.assertIn(st.scene(self.detector,load(name)),('unknown','dungeon'))

 def test_real_exit_frame_is_field(self):self.assertEqual(st.scene(self.detector,load(EXITED)),'field')
 def test_real_dungeon_frame_is_dungeon(self):self.assertEqual(st.scene(self.detector,load(INSIDE)),'dungeon')
 def test_black_transition_is_unknown(self):self.assertEqual(st.scene(self.detector,np.zeros((479,897,3),np.uint8)),'unknown')
 def test_scene_detector_names_carry_both_markers(self):
  self.assertIn(st.DUNGEON,NAMES);self.assertIn(st.EXIT,NAMES)

class Resume(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))

 def run_frames(self,frames):
  """Replay frames through the real loop; every input path is a recording fake."""
  clock=Clock();inputs=[];feed=iter(frames)
  def capture():
   try:return next(feed)
   except StopIteration:raise AssertionError('loop kept running after the replay ended') from None
  def wait(seconds):clock.now+=seconds
  service=S(capture=capture,detector=self.detector,context=S(wait=wait),check=lambda:None,
            button=lambda *a,**k:inputs.append(('button',a)),click_hit=lambda *a,**k:inputs.append(('click',a)))
  context=S(checkpoint=lambda:None,wait=wait)
  adapter=S(project=S(root=bootstrap.A,code='DKB'),mode='sub_quest')
  published=[]
  with patch.object(st,'time',clock),patch.object(st,'timer_pair',return_value=None),\
       patch.object(st,'publish',lambda g,a,kind,*r,**k:published.append(kind)),\
       patch('owner_dungeon_reentry.after_exit',return_value=None),\
       patch('owner_scene_archive.unknown_observed',lambda *a,**k:None),\
       patch('owner_camera.zoom_once',lambda *a,**k:None),patch('project_adapter.secret_exploration.ensure_auto_active',lambda *a,**k:inputs.append(('auto',))):
   try:outcome=('returned',st._resume_dungeon(S(),adapter,context,S(),service))
   except RuntimeError as exc:outcome=('error',str(exc))
   except AssertionError as exc:outcome=('replay_end',str(exc))
  return outcome,inputs,published,clock.now

 def test_dip_frames_do_not_end_the_dungeon_and_send_nothing(self):
  dip=load('20261104T014127-15614380')
  outcome,inputs,published,_=self.run_frames([dip]*6)
  self.assertEqual(outcome[0],'replay_end');self.assertEqual(inputs,[]);self.assertNotIn('field',published)

 def test_three_real_field_frames_end_the_dungeon(self):
  outcome,inputs,published,_=self.run_frames([load(EXITED)]*3)
  self.assertEqual(outcome,('returned',None));self.assertEqual(inputs,[]);self.assertEqual(published[-1],'field')

 def test_dip_resets_the_field_count(self):
  dip,out=load('20261104T014127-15614380'),load(EXITED)
  outcome,_,published,_=self.run_frames([out,out,dip,out,out,dip])
  self.assertEqual(outcome[0],'replay_end');self.assertNotIn('field',published)

 def test_black_screen_longer_than_45s_stops_with_error_today(self):
  # Records current behaviour for a long black exit transition, not a wanted result.
  outcome,inputs,_,_=self.run_frames([np.zeros((479,897,3),np.uint8)]*200)
  self.assertEqual(outcome[0],'error');self.assertIn('45초',outcome[1]);self.assertEqual(inputs,[])

if __name__=='__main__':unittest.main()
