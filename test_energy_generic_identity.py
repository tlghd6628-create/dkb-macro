"""Existing receipt HUD pixels with fake captures; no live input."""
from pathlib import Path
from types import SimpleNamespace as S
import unittest
import bootstrap
import numpy as np
from PIL import Image
from owner_energy_generic_port_candidate import GenericPort
from owner_energy_box_runtime_candidate import Hold

class Tests(unittest.TestCase):
 def port(self):
  path=bootstrap.A/'logs/energy-claim-evidence/d55113d063ef46cb80813f0e575cc7ca/after-18.png'
  self.frame=np.asarray(Image.open(path).convert('RGB')).copy();self.actions=[]
  p=GenericPort.__new__(GenericPort);p.context=S(checkpoint=lambda:None,wait=lambda n:None)
  p.service=S(check=lambda:None,capture=lambda:self.frame.copy(),click_hit=lambda hit:self.actions.append(hit))
  p.evidence_identity={'character':'256b0f6111f96bcaaf78501c'}
  return p
 def test_current_pair_requires_same_observed_character(self):
  p=self.port();self.assertEqual(p.pair(lambda a,b:'known')[0],'known')
  self.frame[9:25,68:101]=0
  self.assertIsNone(p.pair(lambda a,b:self.fail('reader called after character change')))
 def test_commit_click_is_blocked_when_captured_character_changes(self):
  p=self.port();self.frame[9:25,68:101]=0
  with self.assertRaises(Hold):p.click(449,356,lambda:True,lambda frame:True)
  self.assertEqual(self.actions,[])

if __name__=='__main__':unittest.main()
