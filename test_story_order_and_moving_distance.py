import unittest
from unittest.mock import patch
from types import SimpleNamespace as S
from pathlib import Path
import numpy as np
from PIL import Image
import bootstrap
import owner_movement as movement
from owner_story_groups import Groups

class Tests(unittest.TestCase):
 def test_first_visible_accepted_root_beats_saved_middle_without_full_search(self):
  book=S(item={'active':'old_middle','quests':{'old_middle':{'title':'old'},'top':{'title':'top'}}},commit=lambda:None)
  ui=S(frame=lambda:'frame');g=Groups(ui,book,100000);actions=[]
  g.compact=lambda:actions.append('compact');g.top=lambda:actions.append('top')
  g.identify=lambda f,r:'top';g.select=lambda key:actions.append(('select',key)) or True;g.activate=lambda key:actions.append(('activate',key))
  g.locate=lambda *a:(_ for _ in ()).throw(AssertionError('must not search for saved middle'))
  with patch('owner_story_groups.group_rows',return_value=[{'y':120,'open':False}]),patch('owner_story_groups.dots',return_value=True),patch('owner_story_groups.suitable',return_value=True),patch('owner_story_groups.completed_root',return_value=False),patch('owner_story_groups.group_eligible',return_value=True):
   self.assertEqual(g.choose(['old_middle','top']),'top')
  self.assertEqual(actions,['compact',('select','top'),('activate','top')])
 def moving_ui(self,values):
  field=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/moving_415_native.png').convert('RGB'))
  modal=np.asarray(Image.open(bootstrap.O/'current_checks/live/b-move-dialog.png').convert('RGB'));samples=iter(values)
  class UI:
   def __init__(self):self.current=field;self.keys=[];self.pairs=[];self.context=S(wait=lambda n:None)
   def frame(self):return self.current.copy()
   def rows(self,*a,**kw):self.pairs.append(kw.get('pair'));return [{'text':str(next(samples))+'m','score':.999}]
   def key(self,key):self.keys.append(key);self.current=modal if len(self.keys)==1 else field
   def wait(self,predicate,seconds):
    if not predicate(self.current):raise AssertionError('unknown screen')
  return UI()
 def test_walking_distance_changes_are_valid_without_exact_text_pair(self):
  ui=self.moving_ui([1210,1207]);self.assertTrue(movement.travel(ui));self.assertEqual(ui.keys,[0x42,0x42]);self.assertEqual(ui.pairs,[False,False])
 def test_boundary_crossing_or_large_scene_change_sends_no_key(self):
  for values in ([201,199],[1210,700]):
   ui=self.moving_ui(values);self.assertFalse(movement.travel(ui));self.assertEqual(ui.keys,[])

if __name__=='__main__':unittest.main()
