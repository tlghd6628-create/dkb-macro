"""Actual12:29 stored boot selection pair; no game input/resources."""
import unittest
from pathlib import Path
from PIL import Image
import numpy as np
import bootstrap
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native
from owner_gear_identity_candidate import IconIdentity

class ActualAlignment(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  folder=bootstrap.A/'logs/gear-holds/20261103T122947-f3c44718'
  cls.a,cls.b=[np.asarray(Image.open(folder/(str(i)+'.png')).convert('RGB')).copy() for i in (1,2)]
  cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_EQUIPMENT_NAMES))
 def test_actual_equipped_boots_can_be_identified_without_threshold_reduction(self):
  r=IconIdentity(native,self.detector);token=r(self.a,1,False)
  self.assertIsNotNone(token);self.assertEqual(r(self.b,1,True),token)
 def test_other_selected_item_and_reordered_grid_still_fail(self):
  r=IconIdentity(native,self.detector);self.assertIsNotNone(r(self.a,2,False));self.assertIsNone(r(self.b,2,True))
  r=IconIdentity(native,self.detector);r(self.a,1,False);changed=self.b.copy();changed[120:135,755:770]=0
  self.assertIsNone(r(changed,1,True))
 def test_duplicate_icon_rejects_both_spatial_variants(self):
  a,b=self.a.copy(),self.b.copy();rows=native.inspect_growth_equipment(self.detector,a)
  own=next(r['slot'] for r in rows if r['index']==1);other=next(r['slot'] for r in rows if r['index']==2)
  x,y=own['cell_x']+8,own['cell_y']+8;u,v=other['cell_x']+8,other['cell_y']+8
  a[v:v+18,u:u+18]=a[y:y+18,x:x+18];b[v:v+18,u:u+18]=a[v:v+18,u:u+18]
  r=IconIdentity(native,self.detector);r(a,1,False);self.assertIsNone(r(b,1,True))

if __name__=='__main__':unittest.main()
