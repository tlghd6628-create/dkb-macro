"""Saved frame/file state and fake UI only; no live game input."""
import ast,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
import owner_story_groups as g
import owner_mission_controller as c
from owner_mission_policy import QuestBook
from owner_skill_goal import Pending

class Tests(unittest.TestCase):
 def frame(self,name='20261102T101602-79f2420c'):
  return np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261102'/name/'screen.png').convert('RGB'))
 def test_recent_unique_glyph_survives_new_book_and_groups_without_overwriting_identity(self):
  f=self.frame();canonical=g.glyph(f,151)
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   book=QuestBook(root,'char')
   book.item['quests']['q']={'mode':'sub_quest','title':'known','group':True,'group_glyph':canonical,'legacy_history_checked':True,'deaths':1,'block':{'reason':'death','baseline':100}}
   ui=S(rows=lambda *a,**k:[],frame=lambda:f.copy())
   groups=g.Groups(ui,book,104055)
   self.assertEqual(groups.identify(f,{'y':151,'open':False}),'q')
   self.assertNotIn('group_recent_glyph',book.item['quests']['q'])
   self.assertEqual(groups.locate('q',f)['y'],151)
   self.assertNotIn('group_recent_glyph',book.item['quests']['q'])
   self.assertEqual(groups.locate('q')['y'],151)
   entry=book.item['quests']['q']
   self.assertEqual(entry['group_glyph'],canonical)
   self.assertEqual(entry['group_recent_proof'],'paired_unique_visible_root')
   self.assertEqual(entry['deaths'],1);self.assertEqual(entry['block']['reason'],'death')
   restored=QuestBook(root,'char')
   restored.item['quests']['q']['group_glyph']={'bits':'00'*480,'width':100}
   again=g.Groups(ui,restored,104055)
   self.assertEqual(again.locate('q')['y'],151)
   self.assertEqual(again.identify(f,{'y':151,'open':False}),'q')
   self.assertEqual(len(restored.item['quests']),1)
 def test_two_identical_glyph_candidates_never_choose_first_without_unique_name(self):
  f=self.frame();actual=g.glyph(f,151)
  book=S(item={'quests':{'q':{'group_glyph':actual,'title':'[외전] 서로다른임무'}}})
  groups=g.Groups(S(frame=lambda:f,rows=lambda *a,**k:[]),book,104055)
  with patch.object(g,'group_rows',return_value=[{'y':151},{'y':190}]),patch.object(g,'glyph',return_value=actual):
   self.assertIsNone(groups.locate('q'))
 def test_unverified_or_malformed_recent_glyph_never_replaces_canonical(self):
  f=self.frame();actual=g.glyph(f,151)
  for proof,recent in [('unverified',{'bits':'00'*480,'width':100}),('paired_unique_visible_root',{'bits':'00','width':100})]:
   entry={'group_glyph':actual,'title':'known','group_recent_glyph':recent,'group_recent_proof':proof}
   groups=g.Groups(S(frame=lambda:f),S(item={'quests':{'q':entry}}),104055)
   self.assertEqual(groups.locate('q')['y'],151)
 def test_confirmed_progress_resets_only_same_quest_stall(self):
  for stalled,expected in [('q',None),('other','other')]:
   adapter=S(_owner_catalog_errors=2);c.LOCAL.stalled=stalled
   c.confirmed_progress(adapter,'q')
   self.assertEqual(adapter._owner_catalog_errors,0);self.assertEqual(c.LOCAL.stalled,expected)
 def test_auto_method_return_alone_has_no_progress_reset(self):
  tree=ast.parse(Path(c.__file__).read_text(encoding='utf8'))
  run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
  calls=[n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='confirmed_progress']
  self.assertEqual(calls,[])
 def test_only_confirmed_completion_resets_errors(self):
  f=self.frame('20261102T101635-0b326d9e');adapter=S(_owner_catalog_errors=2)
  entry={'title':'[외전] 완료임무확인','deaths':1,'block':{'reason':'condition'}}
  book=S(item={'active':'q','quests':{'q':entry}},commit=lambda:None)
  ui=S(frame=lambda:f.copy(),rows=lambda *a,**k:[{'text':entry['title'],'score':.99}],context=S(wait=lambda n:None),adapter=adapter)
  groups=g.Groups(ui,book,104055);c.LOCAL.stalled='q'
  self.assertFalse(groups.completed('q',{'y':113}));self.assertEqual(adapter._owner_catalog_errors,2)
  self.assertTrue(groups.completed('q',{'y':295}));self.assertEqual(adapter._owner_catalog_errors,0)
  self.assertIsNone(c.LOCAL.stalled);self.assertEqual(entry['deaths'],1)
 def tearDown(self):c.LOCAL.stalled=None

if __name__=='__main__':unittest.main()
