"""Actual archived rasters and fake controller state, no game input."""
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
import owner_story_groups as g

class Tests(unittest.TestCase):
 def frame(self,name):
  return np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261102'/name/'screen.png').convert('RGB'))
 def test_all_observed_completed_suitable_rows_rejected_without_threshold_change(self):
  expected={'20261102T101628-d5be92e0':[420], '20261102T101635-0b326d9e':[295,334,372,410],
    '20261102T101641-65f1b6b9':[189,227,266,304,342,381,419],
    '20261102T101647-c198b23a':[172,210,248,287,325]}
  for name,ys in expected.items():
   f=self.frame(name)
   for y in ys:
    with self.subTest(name=name,y=y):self.assertTrue(g.completed_root(f,y));self.assertFalse(g.dots(f,y))
 def test_real_accepted_and_new_suitable_roots_are_not_completed(self):
  f=self.frame('20261102T101602-79f2420c')
  for y in (113,151,190,228,266):self.assertFalse(g.completed_root(f,y))
  self.assertTrue(g.dots(f,151));self.assertTrue(g.suitable(f,266))
 def test_missing_stamp_never_resets_durable_completion(self):
  f=self.frame('20261102T101602-79f2420c');glyph=g.glyph(f,151)
  book=S(item={'quests':{'q':{'mode':'sub_quest','title':'known','group':True,'group_glyph':glyph,'completed':True,'legacy_history_checked':True}}},commit=lambda:None)
  ui=S(rows=lambda *a,**k:[]);groups=g.Groups(ui,book,104055)
  self.assertEqual(groups.identify(f,{'y':151,'open':False}),'q')
  self.assertTrue(book.item['quests']['q']['completed']);self.assertFalse(book.item['quests']['q']['actionable'])
 def test_fresh_visible_glyph_used_after_fractional_scroll_not_stale_persisted_raster(self):
  f=self.frame('20261102T101602-79f2420c');actual=g.glyph(f,151)
  book=S(item={'quests':{'q':{'group_glyph':{'bits':'00'*480,'width':100},'title':'known'}}})
  groups=g.Groups(S(frame=lambda:f),book,104055);groups.visible_glyphs['q']=actual
  self.assertEqual(groups.locate('q')['y'],151)

if __name__=='__main__':unittest.main()
