"""Isolated journal/fake UI contracts; not real quest acceptance or progress."""
import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import bootstrap
import owner_story_groups as g
from owner_mission_policy import QuestBook

class Tests(unittest.TestCase):
 def case(self):
  temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(temp.cleanup)
  book=QuestBook(temp.name,'test-character')
  book.item['quests']['q']={'title':'[외전] 동굴에 갇힌 도사','group':True,'mode':'sub_quest','accepted':True,
   'completed':False,'suitable':True,'actionable':True,'deaths':1,
   'block':{'reason':'condition','functional_hold':True,'detail':'자리 정체 복구 확인 필요 · 홈 복귀 후 같은 임무의 현재 단계 실행 조건 확인 필요','at':1},
   'position_recovery':{'phase':'at_town','at':1}}
  return book
 def test_only_prior_position_error_is_recheckable(self):
  b=self.case();r=b.item['quests']['q'];self.assertTrue(g.position_hold_probe(r,1000))
  for mutate in ({'reason':'death'},{'reason':'power'},{'reason':'prerequisite'},{'functional_hold':False},{'detail':'다른 소비 결과 확인 필요'}):
   other=copy.deepcopy(r);other['block'].update(mutate);self.assertFalse(g.position_hold_probe(other,1000))
  for mutate in ({'completed':True},{'accepted':False}):
   other=copy.deepcopy(r);other.update(mutate);self.assertFalse(g.position_hold_probe(other,1000))
 def test_bounded_persistent_probe_does_not_clear_hold(self):
  b=self.case();old=copy.deepcopy(b.item['quests']['q']['block'])
  self.assertTrue(g.begin_position_probe(b,'q',1000));self.assertFalse(g.begin_position_probe(b,'q',1100))
  self.assertTrue(g.begin_position_probe(b,'q',1300));self.assertFalse(g.begin_position_probe(b,'q',1600))
  self.assertTrue(g.position_hold_probe(b.item['quests']['q'],1901))
  self.assertEqual(b.item['quests']['q']['block'],old);self.assertFalse(b.item['quests']['q']['completed'])
 def test_release_preserves_history_and_never_claims_quest_complete(self):
  b=self.case();r=b.item['quests']['q'];old=copy.deepcopy(r['block']);g.begin_position_probe(b,'q',1000)
  self.assertFalse(g.release_position_hold(b,'q',dict(old,at=2)))
  self.assertTrue(g.release_position_hold(b,'q',old));self.assertEqual(r['position_condition_history'],[old])
  self.assertEqual(r['deaths'],1);self.assertFalse(r['completed']);self.assertTrue(r['accepted'])
  self.assertEqual(r['position_recovery']['phase'],'selected_recheck')
  self.assertTrue(g.group_eligible(b,'q',135577))
 def test_button_proof_requires_two_matching_selected_suitable_views(self):
  a,b=object(),object();frames=iter((a,b));ui=NS(frame=lambda:next(frames),context=NS(wait=lambda _:None),service=NS(detector=object()))
  with patch.object(g,'quest_screen',return_value=True),patch.object(g,'selected_quest_box',return_value=(0,110,1,20)),patch.object(g,'suitable',return_value=True),patch('owner_mission_ui.auto_button_hit',side_effect=[(800,450,(750,430,850,470)),None]):
   self.assertFalse(g.position_step_button_pair(ui,120))
 def test_visible_top_rechecks_old_hold_before_next_row(self):
  b=self.case();actions=[];ui=NS(frame=lambda:object());groups=g.Groups(ui,b,135577)
  groups.compact=lambda:None;groups.identify=lambda *a:'q'
  def selected(key):
   actions.append('select');groups._position_recheck_ready=(key,copy.deepcopy(b.item['quests'][key]['block']));return True
  groups.select=selected
  with patch.object(g,'group_rows',return_value=[{'y':120,'open':False}]),patch.object(g,'completed_root',return_value=False),patch.object(g,'suitable',return_value=True),patch.object(g,'dots',return_value=True):
   self.assertEqual(groups.choose(['q']),'q')
  self.assertEqual(actions,['select']);self.assertEqual(b.item['active'],'q');self.assertFalse(b.item['quests']['q']['completed'])
 def test_selection_failure_keeps_hold(self):
  b=self.case();groups=g.Groups(NS(frame=lambda:object()),b,135577);groups.compact=lambda:None;groups.identify=lambda *a:'q'
  def selected(key):raise g.Pending('current button unverified')
  groups.select=selected
  with patch.object(g,'group_rows',return_value=[{'y':120,'open':False}]),patch.object(g,'completed_root',return_value=False),patch.object(g,'suitable',return_value=True),patch.object(g,'dots',return_value=True):
   with self.assertRaises(g.StorySelectionPending):groups.choose(['q'])
  self.assertTrue(g.position_hold(b.item['quests']['q']));self.assertIsNone(b.item['active'])

if __name__=='__main__':unittest.main()
