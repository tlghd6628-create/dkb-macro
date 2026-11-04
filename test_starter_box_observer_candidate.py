exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf8'))
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import owner_starter_box_observer_candidate as subject

class ReadOnlyBoxObserver(unittest.TestCase):
 def test_native_icon_detected_only_as_candidate_not_claim(self):
  profile=A/'profiles/DKB';d=subject.detector(str(profile));needle=d.templates[subject.ICON][:,:,::-1]
  frame=np.asarray(Image.open(C/'live_fixtures/inventory_worn_native_1.png').convert('RGB')).copy()
  self.assertEqual(frame.shape,(479,897,3))
  h,w=needle.shape[:2];frame[120:120+h,750:750+w]=needle
  out=subject.observe(profile,frame.copy(),frame.copy())
  self.assertIsNotNone(out);self.assertIs(out['action_authorized'],False)
  self.assertEqual(out['status'],'possible_material_box')
  changed=frame.copy();changed[120:120+h,750:750+w]=0
  self.assertIsNone(subject.observe(profile,frame,changed))
  self.assertIsNone(subject.observe(profile,frame,frame))
  unknown=frame.copy();unknown[10:25,30:60]=0
  self.assertIsNone(subject.observe(profile,frame,unknown))
 def test_real_inventory_never_counts_as_unproved_action(self):
  frames=[np.asarray(Image.open(C/'live_fixtures'/f'inventory_worn_native_{n}.png').convert('RGB')) for n in (1,2)]
  value=subject.observe(A/'profiles/DKB',*frames)
  self.assertTrue(value is None or value['action_authorized'] is False)

if __name__=='__main__':unittest.main(verbosity=2)
