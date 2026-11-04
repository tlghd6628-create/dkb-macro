"""Actual saved native slider frames and simulated navigation; no live inputs."""
import time,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
from PIL import Image
import numpy as np
from roi_runtime import RoiDetector
from owner_energy_generic_port_candidate import GenericPort
from owner_energy_choice_reader_candidate import read_pair
from owner_energy_box_runtime_candidate import Hold
PAIRS={15:('20261102_134713_53dc3709.png','20261102_134737_d7f8e9cb.png'),16:('20261102_134928_b988666e.png','20261102_134953_2279d7e2.png'),46:('20261102_135158_83dab78b.png','20261102_135225_e1535a5e.png')}
def image(name):return np.asarray(Image.open(bootstrap.A/'logs/manual-captures'/name).convert('RGB')).copy()
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.detector=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_인벤_MAX'])
 def test_native15_16_MAX46_pairs_and_all_quantity_controls(self):
  p=GenericPort.__new__(GenericPort);p.service=S(detector=self.detector)
  for quantity,names in PAIRS.items():
   a,b=map(image,names);value=read_pair(a,b)
   self.assertEqual((value['selected'],value['quantity'],value['available_count']),('생명',quantity,46))
   for frame in (a,b):
    for name in ('plus','minus','min','max'):self.assertIsNotNone(p.quantity_control(frame,name),(quantity,name))
 def fake_port(self,current):
  state={'selected':'생명','quantity':current,'available_count':46};actions=[];frame=image(PAIRS[15][0]);p=GenericPort.__new__(GenericPort)
  p.service=S(capture=lambda:frame.copy(),detector=self.detector);p.detail_count_before=46
  p.open_selection=lambda guard:dict(boxes=46)
  def pair(reader):
   a,b=frame.copy(),frame.copy();p._last_pair=(a,b);value=reader(a,b);t=time.monotonic()
   return (value,['fresh-a','fresh-b'],[t-.01,t]) if value is not None else None
  p.pair=pair;p.wait_pair=pair
  def click(x,y,guard,predicate,on_sent=None):
   if guard() is not True or not predicate(frame.copy()):raise Hold('fake preinput changed')
   actions.append((x,y));state['quantity']={367:1,529:46}.get(x,state['quantity']+(1 if x==509 else -1))
  p.click=click
  return p,state,actions
 def test_bounded_plus_MIN_MAX_paths_never_press_commit(self):
  for start,target,expected in ((1,15,[(509,327)]*14),(46,15,[(367,327)]+[(509,327)]*14),(1,46,[(529,327)])):
   p,state,actions=self.fake_port(start)
   with patch('owner_energy_generic_port_candidate.read_pair',side_effect=lambda a,b:dict(state)),patch('owner_energy_generic_port_candidate.read_open_pair',side_effect=lambda a,b:dict(state)):
    proof=p.prepare_batch('생명',target,lambda:True)
   self.assertEqual(actions,expected);self.assertEqual(proof['quantity'],target);self.assertNotIn((449,356),actions)
 def test_changed_step_counter_holds_without_commit(self):
  p,state,actions=self.fake_port(1);p.wait_pair=lambda reader:None
  with patch('owner_energy_generic_port_candidate.read_pair',side_effect=lambda a,b:dict(state)),patch('owner_energy_generic_port_candidate.read_open_pair',side_effect=lambda a,b:dict(state)),self.assertRaises(Hold):
   p.prepare_batch('생명',15,lambda:True)
  self.assertEqual(actions,[(509,327)])
if __name__=='__main__':unittest.main()
