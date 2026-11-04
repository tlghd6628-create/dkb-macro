from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
from PIL import Image
import numpy as np,unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_start_menu as m
class Tests(unittest.TestCase):
 def test_actual_original_growth_pair_and_dimmed_popup(self):
  for i in (1,2):
   frame=np.asarray(Image.open(T/f'live_fixtures/blessing_list_native_{i}.png').convert('RGB'))
   self.assertEqual(m.kind(frame),'성장')
   self.assertIsNone(m.kind((frame*.45).astype(np.uint8)))
  for i in (1,2):
   frame=np.asarray(Image.open(T/f'live_fixtures/blessing_menu_native_{i}.png').convert('RGB'))
   self.assertEqual(m.kind(frame),'가호')
   self.assertIsNone(m.kind((frame*.45).astype(np.uint8)))
 def test_same_menu_then_native_back_only(self):
  frames=iter(['growth','growth','growth',None,None]);actions=[]
  service=NS(context=NS(checkpoint=lambda:None,wait=lambda n:None),check=lambda:None,
   capture=lambda:next(frames),detector=NS(find=lambda *a,**k:('back',)),click_hit=actions.append)
  with patch.object(m,'kind',lambda f:'성장' if f=='growth' else None):m.normalize(service)
  self.assertEqual(actions,[('back',)])
 def test_changed_or_unknown_menu_sends_no_input(self):
  for values in ((None,None),('growth',None)):
   frames=iter(values);actions=[]
   service=NS(context=NS(checkpoint=lambda:None,wait=lambda n:None),check=lambda:None,capture=lambda:next(frames),click_hit=actions.append)
   with patch.object(m,'kind',lambda f:'성장' if f=='growth' else None):m.normalize(service)
   self.assertEqual(actions,[])
if __name__=='__main__':unittest.main()
