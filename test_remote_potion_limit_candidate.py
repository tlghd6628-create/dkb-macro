"""Two real saved images plus fake OCR/game input; no game operations."""
import sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,numpy as np
from PIL import Image
import owner_remote_potion_limit_candidate as mod
import owner_membership

P=bootstrap.A/'logs/scene-corpus/20261102'
FRAMES=[np.asarray(Image.open(P/n/'screen.png').convert('RGB')).copy() for n in
        ('20261102T030220-b0ce4cbf','20261102T030223-41e178cb')]
class UI:
 def __init__(self,frames=FRAMES,texts=('650/650','650/650'),scores=(.9986,.9958),age=0):
  self.frames=frames;self.i=0;self.texts=texts;self.scores=scores;self.age=age
  self.context=SimpleNamespace(wait=lambda _:None,checkpoint=lambda:None)
 def frame(self):
  frame=self.frames[self.i%len(self.frames)].copy();self.i+=1;return frame
 def rows(self,box,**kwargs):
  assert box==(70,89,50,17) and kwargs.get('pair_minimum')==.99
  frames=[self.frame(),self.frame()];now=time.monotonic()-self.age
  answers=[[{'text':text,'score':score}] for text,score in zip(self.texts,self.scores)]
  self._owner_last_rows_pair=(frames,[now,now],answers);return answers[-1]

class Tests(unittest.TestCase):
 def setUp(self):mod._CACHE.clear()
 def test_two_actual_screen_markers_and_equal_counter(self):
  self.assertTrue(all(mod._screen(frame,'1단물약') for frame in FRAMES))
  self.assertEqual(mod.observed_full(UI(),'1단물약'),650)
  self.assertEqual(mod._parse([{'text':'700/700','score':.999}]),700)
 def test_unavailable_tier_and_screens_or_numbers_never_claim_full(self):
  self.assertIsNone(mod.observed_full(UI(),'2단물약'))
  for texts,scores in [(('650/649','650/649'),(.999,.999)),(('650/650','650/650'),(.98,.999)),
                       (('650/650','649/649'),(.999,.999)),(('0/0','0/0'),(.999,.999))]:
   self.assertIsNone(mod.observed_full(UI(texts=texts,scores=scores),'1단물약'))
  self.assertIsNone(mod.observed_full(UI(age=4),'1단물약'))
  for box in ((9,81,44,94),(49,69,133,80),(70,89,120,106),(35,4,145,34)):
   altered=FRAMES[1].copy();l,t,r,b=box;altered[t:b,l:r]=0
   self.assertIsNone(mod.observed_full(UI(frames=(FRAMES[0],altered)),'1단물약'))
 def test_limit_cache_is_character_profile_and_tier_scoped_and_expiring(self):
  adapter=object();key=('profile','scope','character','1단물약')
  with patch.object(mod,'_identity',return_value=key),patch.object(mod.time,'monotonic',return_value=100):
   self.assertTrue(mod.remember_full(adapter,'1단물약'));self.assertTrue(mod.cached_full(adapter,'1단물약'))
  with patch.object(mod,'_identity',return_value=('profile','scope','other','1단물약')):
   self.assertFalse(mod.cached_full(adapter,'1단물약'))
  with patch.object(mod,'_identity',return_value=key),patch.object(mod.time,'monotonic',return_value=131):
   self.assertFalse(mod.cached_full(adapter,'1단물약'))
  with patch.object(mod,'_identity',return_value=None):self.assertFalse(mod.cached_full(adapter,'1단물약'))
  with patch.object(mod,'_identity',side_effect=lambda adapter,tier:('profile','scope','character',tier)),\
       patch.object(mod.time,'monotonic',return_value=150):
   self.assertTrue(mod.remember_full(adapter,'1단물약'))
   self.assertFalse(mod.cached_full(adapter,'2단물약'))
 def test_cache_requires_recent_identified_character_and_same_scope(self):
  adapter=SimpleNamespace(project=SimpleNamespace(root='test-profile'))
  record=SimpleNamespace(character='A',observed=90.)
  with patch('owner_progression.state',return_value=record),\
       patch('owner_hunt_rules_candidate.configured_identity',return_value='scope1'),\
       patch.object(mod.time,'monotonic',return_value=100.):
   self.assertTrue(mod.remember_full(adapter,'1단물약'));self.assertTrue(mod.cached_full(adapter,'1단물약'))
   record.character='B';self.assertFalse(mod.cached_full(adapter,'1단물약'))
   record.character='A';record.observed=69.;self.assertFalse(mod.cached_full(adapter,'1단물약'))
 def test_remote_full_skips_max_and_closes_original_screen(self):
  import project_adapter.town_services as town
  actions=[]
  class Service:
   def __init__(self,*args):pass
   def capture(self):return FRAMES[0].copy()
   def button(self,name,**kwargs):actions.append(name);return True
  adapter=SimpleNamespace(values={'common.potion_and_favorite.potion_tier':'1단물약'})
  ctx=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None)
  with patch.object(town,'TownServices',Service),patch.object(town,'_close_potion_screen',side_effect=lambda service:actions.append('close')),\
       patch.object(owner_membership,'open_remote',return_value=UI()),patch.object(mod,'cached_full',return_value=False),\
       patch.object(mod,'observed_full',return_value=650),patch.object(mod,'remember_full',return_value=True):
   self.assertTrue(owner_membership.remote_purchase(adapter,ctx,object()))
  self.assertEqual(actions,['close'])
 def test_recent_full_returns_before_any_open_or_input(self):
  adapter=SimpleNamespace(values={'common.potion_and_favorite.potion_tier':'1단물약'})
  ctx=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None)
  with patch.object(mod,'cached_full',return_value=True),patch.object(owner_membership,'open_remote') as opening:
   self.assertTrue(owner_membership.remote_purchase(adapter,ctx,object()));opening.assert_not_called()
 def test_no_full_evidence_preserves_original_unavailable_path(self):
  import project_adapter.town_services as town
  actions=[]
  class Service:
   def __init__(self,*args):pass
   def capture(self):return FRAMES[0].copy()
   def button(self,name,**kwargs):actions.append(name);return False
  adapter=SimpleNamespace(values={'common.potion_and_favorite.potion_tier':'1단물약'})
  ctx=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None)
  with patch.object(town,'TownServices',Service),patch.object(town,'_close_potion_screen',side_effect=lambda service:actions.append('close')),\
       patch.object(owner_membership,'open_remote',return_value=UI()),patch.object(mod,'cached_full',return_value=False),\
       patch.object(mod,'observed_full',return_value=None):
   self.assertFalse(owner_membership.remote_purchase(adapter,ctx,object()))
  self.assertEqual(actions,['버튼_물약상인_1단물약','close'])
if __name__=='__main__':unittest.main(verbosity=2)
