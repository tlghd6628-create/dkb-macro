from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import unittest
import bootstrap
import numpy as np
from PIL import Image
from owner_visual_state import same_label
from owner_membership import remote_shop_screen
from owner_remote_potion_limit_candidate import _asset
from owner_energy_box_port_candidate import Port

class Visual(unittest.TestCase):
 def frame(self,relative):return np.asarray(Image.open(bootstrap.A/'logs'/relative).convert('RGB')).copy()
 def test_actual_active_and_exhausted_labels_identify_same_shop(self):
  for relative in ['quest-incidents/20261102T055949Z-119ee4a1/screen.png','scene-corpus/20261102/20261102T030220-b0ce4cbf/screen.png','scene-corpus/20261102/20261102T150055-33551b82/screen.png']:
   self.assertTrue(remote_shop_screen(self.frame(relative)),relative)
 def test_label_identity_does_not_prove_underlying_modal_actionable(self):
  f=self.frame('quest-incidents/20261102T055949Z-119ee4a1/screen.png')
  self.assertFalse(remote_shop_screen((f.astype(float)*.55).astype('uint8')))
  f[9:28,40:117]=0;self.assertFalse(remote_shop_screen(f))
 def test_shape_rejects_flat_changed_or_inverted_text(self):
  ref=_asset('tier1');frame=np.zeros((100,150,3),dtype='uint8');frame[69:80,49:133]=ref
  self.assertTrue(same_label(frame,ref,(49,69,84,11)))
  for value in [np.full_like(ref,100),np.roll(ref,4,axis=1),255-ref]:
   frame[69:80,49:133]=value;self.assertFalse(same_label(frame,ref,(49,69,84,11)))
 def test_normal_inventory_is_not_toggled_again(self):
  f=self.frame('scene-corpus/20261102/20261102T150049-3477ab5e/screen.png')
  p=Port.__new__(Port);p.context=S(checkpoint=lambda:None,wait=lambda n:None)
  p.service=S(check=lambda:None,capture=lambda:f.copy())
  with patch('owner_progression.open_inventory_by_key',side_effect=AssertionError('must not toggle existing inventory')):
   self.assertTrue(p.ensure_inventory())
 def test_new_navigation_requires_postcondition(self):
  p=Port.__new__(Port);p.service=object();p.pair=lambda read:None;p.wait_pair=lambda read:None
  with patch('owner_progression.open_inventory_by_key',return_value=True):self.assertFalse(p.ensure_inventory())
if __name__=='__main__':unittest.main()
