import bootstrap
import unittest,threading,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image

class Observations(unittest.TestCase):
 def probe(self):
  from owner_feature_check_live_candidate import MenuProbe
  p=MenuProbe(None,NS(project=NS(root=bootstrap.A)),threading.Event())
  p.known='energy';p.context=NS(checkpoint=lambda:None)
  p.service=NS(detector=NS(find=lambda *a,**kw:True));p.pair=lambda f:True
  p.menu_visible=lambda *a:True
  return p
 def test_one_verified_back_retry_then_confirms_the_field(self):
  p=self.probe();keys=[];p.button=keys.append
  result=iter((False,True));p.wait_pair=lambda *args:next(result)
  self.assertTrue(p.close_menu());self.assertIsNone(p.known)
  self.assertEqual(keys,['버튼_나가기','버튼_나가기'])
 def test_failed_close_keeps_original_menu_ownership(self):
  p=self.probe();keys=[];p.button=keys.append;p.wait_pair=lambda *a:False
  self.assertFalse(p.close_menu());self.assertEqual(p.known,'energy')
  self.assertEqual(len(keys),2)
 def test_unknown_menu_does_not_receive_a_second_back(self):
  p=self.probe();keys=[];p.button=keys.append;p.wait_pair=lambda *a:False
  answers=iter((True,True,False));p.pair=lambda f:next(answers)
  self.assertFalse(p.close_menu());self.assertEqual(keys,['버튼_나가기'])
 def test_evidence_uses_a_fresh_frame_after_the_reader(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=self.probe();p.adapter=NS(project=NS(root=Path(tmp)));old=np.zeros((479,897,3),dtype=np.uint8)
   fresh=np.full_like(old,80);p.last_frame=old
   def capture():p.last_frame=fresh.copy();return p.last_frame
   p.frame=capture
   file=p.evidence({'id':'gear'},failure=True)
   self.assertTrue(np.array_equal(np.asarray(Image.open(file)),fresh))
 def test_read_only_style_agreement_keeps_only_paired_known_rows(self):
  from owner_feature_check_growth_candidate import read_styles
  frame=np.zeros((479,897,3),dtype=np.uint8);seen=[]
  ui=NS(frame=lambda:frame,_owner_last_rows_raw=None,_owner_last_rows_pair=None)
  ui.rows_batch=lambda specs:seen.extend(specs)
  with patch('owner_skill_ui.SkillUI',return_value=ui),patch('owner_skill_growth_candidate.tab',return_value=True):
   self.assertFalse(read_styles(NS(adapter=None),None,None)['verified'])
  agrees=seen[0][5]
  a={'text':'파멸+19','score':.99,'y':82};b={'text':'강타+9','score':.99,'y':120}
  self.assertTrue(agrees([a,b],[a,dict(b,text='강타+8')]))
  self.assertFalse(agrees([a],[dict(a,text='파멸+18')]))
  self.assertFalse(agrees([a],[dict(a,y=99)]))

if __name__=='__main__':unittest.main()
