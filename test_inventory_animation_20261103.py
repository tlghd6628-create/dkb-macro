import bootstrap,unittest
import numpy as np
from PIL import Image
from unittest.mock import patch
from roi_runtime import RoiDetector
from project_adapter import market_inventory as n
import owner_equipment_tooltip_candidate as t
class Animation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261103/20261103T141953-4dc67e35/screen.png').convert('RGB'))
  cls.d=RoiDetector(bootstrap.A/'profiles/DKB',list(n.INVENTORY_USE_NAMES)+[n.EMPTY])
  cls.box=t.inventory_slots(cls.d,cls.f)[0][1][2]
 def test_arrow_corner_animation_is_inspection_only(self):
  f=self.f.copy();x,y,r,b=self.box;f[y:y+6,r-6:r]=(0,255,0)
  self.assertTrue(t.same_equipment_inventory(self.d,self.f,f))
 def test_changed_item_core_is_rejected(self):
  f=self.f.copy();x,y,r,b=self.box;f[y+8:y+24,x+8:x+24]=0
  self.assertFalse(t.same_equipment_inventory(self.d,self.f,f))
 def test_changed_rarity_border_is_rejected(self):
  f=self.f.copy();x,y,r,b=self.box;f[y:b,x:x+3]=(255,0,255)
  self.assertFalse(t.same_equipment_inventory(self.d,self.f,f))
 def test_actual_rejected_pair_has_exact_icons_and_only_subthreshold_border_noise(self):
  folder=bootstrap.A/'logs/gear-holds/20261103T142711-6b2ab7ae'
  a,b=[np.asarray(Image.open(folder/f'{i}.png').convert('RGB')) for i in (1,2)]
  self.assertTrue(t.same_equipment_inventory(self.d,a,b))
 def test_actual_longer_visit_preserves_icon_shape_with_single_channel_drift(self):
  folder=bootstrap.A/'logs/scene-corpus/20261103'
  a,b=[np.asarray(Image.open(folder/p/'screen.png').convert('RGB')) for p in ('20261103T144237-bd679249','20261103T144244-f36b82e8')]
  self.assertTrue(t.same_equipment_inventory(self.d,a,b))
 def test_unseen_cell_change_does_not_forget_rejected_candidate(self):
  rows=t.inventory_slots(self.d,self.f);hits=[h for state,h in rows[:2]]
  f=self.f.copy();x,y,r,b=hits[1][2];f[y+8:y+24,x+8:x+24]=0
  with patch.object(t,'inventory_slots',return_value=[('occupied',h) for h in hits]):
   self.assertEqual(t.retain_rejected_cells(self.d,self.f,f,[hits[0][2]]),[hits[0][2]])
   x,y,r,b=hits[0][2];f[y+8:y+24,x+8:x+24]=0
   self.assertEqual(t.retain_rejected_cells(self.d,self.f,f,[hits[0][2]]),[])
if __name__=='__main__':unittest.main()
