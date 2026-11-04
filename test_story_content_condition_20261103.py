"""Selected mission detail classification and durable defer; no gameplay."""
import copy,tempfile,unittest
from pathlib import Path
import bootstrap
from owner_story_groups import external_content_goal,defer_external_content,content_hold_probe,reviewable_block
from owner_mission_policy import QuestBook

class Content(unittest.TestCase):
 def rows(self):return [{'text':'※임무 목표','score':.94638276},{'text':'승천의 탑 1층 클리어하기','score':.87896156}]
 def case(self):
  tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(tmp.cleanup)
  book=QuestBook(tmp.name,'char')
  book.item['quests']['tower']={'title':'[첫걸음] 승천의 탐','mode':'sub_quest','group':True,'suitable':True,'actionable':True,'accepted':True,'completed':False,'deaths':1}
  book.item['active']='tower';return book
 def test_actual_saved_detail_ocr_classifies_a_tower_condition(self):
  self.assertEqual(external_content_goal(self.rows())['floor'],1)
 def test_low_confidence_and_talk_only_do_not_prove_a_content_requirement(self):
  self.assertIsNone(external_content_goal([{'text':'승천의 탑 1층 클리어하기','score':.849}]))
  self.assertIsNone(external_content_goal([{'text':'승천의 탑 담당자와 대화하기','score':.99}]))
 def test_waiting_survives_restart_without_a_death_or_completion(self):
  b=self.case();self.assertTrue(defer_external_content(b,'tower',self.rows()))
  saved=QuestBook(b.path.parent.parent,'char');entry=saved.item['quests']['tower']
  self.assertFalse(entry['completed']);self.assertTrue(entry['accepted']);self.assertEqual(entry['deaths'],1)
  self.assertIsNone(saved.item['active']);self.assertTrue(saved.blocked('tower',134980))
  self.assertEqual(entry['block']['external_content']['content'],'tower')
 def test_existing_false_recovery_hold_is_preserved_in_history(self):
  b=self.case();old={'reason':'condition','functional_hold':True,'detail':'자리 정체 복구 확인 필요 · old','at':1}
  b.item['quests']['tower']['block']=copy.deepcopy(old)
  self.assertTrue(content_hold_probe(b.item['quests']['tower']))
  self.assertTrue(defer_external_content(b,'tower',self.rows()))
  row=b.item['quests']['tower'];self.assertEqual(row['content_condition_history'],[old])
  self.assertTrue(reviewable_block(row['block']));self.assertFalse(content_hold_probe(row))
 def test_other_quest_or_death_hold_is_not_a_tower_probe(self):
  self.assertFalse(content_hold_probe({'title':'다른 임무','block':{'reason':'condition','functional_hold':True,'detail':'자리 정체 복구 확인 필요'}}))
  self.assertFalse(content_hold_probe({'title':'승천의 탑','block':{'reason':'death','baseline':100000}}))
 def test_fresh_changed_objective_can_release_waiting_via_existing_policy(self):
  b=self.case();defer_external_content(b,'tower',self.rows())
  self.assertFalse(defer_external_content(b,'tower',[{'text':'도사와 대화하기','score':.99}]))
  self.assertTrue(b.blocked('tower',134980))
  b.prerequisite_proved('tower');self.assertFalse(b.blocked('tower',134980))
  self.assertFalse(b.item['quests']['tower']['completed'])

if __name__=='__main__':unittest.main()
