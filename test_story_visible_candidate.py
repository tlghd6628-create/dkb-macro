"""Saved mission frame and fake state; no game input."""
import sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,numpy as np
from PIL import Image
from owner_story_visible_candidate import visible_active
from owner_story_groups import glyph,Groups

class Tests(unittest.TestCase):
 def setUp(self):
  self.frame=np.asarray(Image.open(bootstrap.O/'current_checks/live/mission-story-groups.png').convert('RGB')).copy()
  self.count=0;self.mutate=None
  def capture():
   self.count+=1;f=self.frame.copy()
   if self.mutate:self.mutate(self.count,f)
   return f
  self.ui=SimpleNamespace(frame=capture,context=SimpleNamespace(checkpoint=lambda:None,wait=lambda _:None))
  self.book=SimpleNamespace(item={'active':'mission','quests':{'mission':{'group_glyph':glyph(self.frame,185)}}},eligible=lambda key,power:True)
  self.groups=SimpleNamespace(ui=self.ui,book=self.book,power=100000,locate=lambda key,frame:{'y':185,'open':False})
 def test_two_then_latest_frame_of_actual_accepted_row(self):
  self.assertTrue(visible_active(self.groups,['mission']));self.assertEqual(self.count,3)
 def test_changed_dots_or_character_active_rejects(self):
  def clear(n,frame):
   if n==2:frame[168:202,620:655]=0
  self.mutate=clear
  self.assertFalse(visible_active(self.groups,['mission']))
  self.count=0
  def change(n,frame):
   if n==3:self.book.item['active']='other'
  self.mutate=change
  self.assertFalse(visible_active(self.groups,['mission']))
 def test_not_in_batch_ineligible_and_open_other_group_reject(self):
  self.assertFalse(visible_active(self.groups,[]));self.assertEqual(self.count,0)
  self.book.eligible=lambda key,power:False
  self.assertFalse(visible_active(self.groups,['mission']));self.assertEqual(self.count,0)
  self.book.eligible=lambda key,power:True
  with patch('owner_story_groups.group_rows',return_value=[{'y':185,'open':False},{'y':250,'open':True}]):
   self.assertFalse(visible_active(self.groups,['mission']))
  self.ui.execution_dialogue=lambda frame:True
  self.assertFalse(visible_active(self.groups,['mission']))
 def test_unrelated_y_and_old_frame_reject(self):
  self.book.item['quests']['mission']['group_glyph']=glyph(self.frame,147)
  self.assertFalse(visible_active(self.groups,['mission'])) # No accepted dots.
  self.book.item['quests']['mission']['group_glyph']=glyph(self.frame,185)
  with patch('owner_story_visible_candidate.time.monotonic',side_effect=[1,5]):
   self.assertFalse(visible_active(self.groups,['mission']))
 def test_integrated_fast_route_reuses_existing_select_and_activate(self):
  groups=Groups(self.ui,self.book,100000);actions=[]
  groups.select=lambda key:actions.append(('select',key)) or True
  groups.activate=lambda key:actions.append(('activate',key))
  groups.top=lambda:(_ for _ in ()).throw(AssertionError('unexpected rewind'))
  groups.compact=lambda:(_ for _ in ()).throw(AssertionError('unexpected compact'))
  self.assertEqual(groups.choose(['mission'],prefer_saved=True),'mission')
  self.assertEqual(actions,[('select','mission'),('activate','mission')])
 def test_inconclusive_probe_uses_original_rewind(self):
  groups=Groups(self.ui,self.book,100000);actions=[]
  groups.compact=lambda:actions.append('compact')
  def old_top():actions.append('top');raise RuntimeError('old path reached')
  groups.top=old_top
  with patch('owner_story_visible_candidate.visible_active',return_value=False):
   with self.assertRaisesRegex(RuntimeError,'old path reached'):groups.choose(['mission'],prefer_saved=True)
  self.assertEqual(actions,['compact','top'])
 def test_failed_fast_select_keeps_original_defer(self):
  groups=Groups(self.ui,self.book,100000);actions=[]
  groups.select=lambda key:actions.append(('select',key)) or False
  def defer(key,reason,**kwargs):
   actions.append(('defer',key,reason));self.book.item['active']=None
  self.book.defer=defer
  def fallback():actions.append('fallback');raise RuntimeError('normal rescan')
  groups.compact=fallback
  with self.assertRaisesRegex(RuntimeError,'normal rescan'):groups.choose(['mission'],prefer_saved=True)
  self.assertEqual(actions,[('select','mission'),('defer','mission','condition'),'fallback'])
if __name__=='__main__':unittest.main(verbosity=2)
