"""Durable quest-stall recovery without live game input."""
import logging,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from owner_mission_policy import QuestBook
from owner_mission_controller import StallLog,LOCAL,defer_stalled,release_functional_hold
from owner_story_groups import reviewable_block,same_verified_root_blocked,group_eligible

class Tests(unittest.TestCase):
 def test_only_exact_stall_on_active_worker_is_tagged(self):
  handler=StallLog();LOCAL.active=('adapter','context','quest1',0);LOCAL.stalled=None
  def emit(msg):handler.emit(logging.LogRecord('x',logging.INFO,'',0,msg,(),None))
  emit('퀘스트 상태판정: selected=quest_active');self.assertIsNone(LOCAL.stalled)
  emit('서브퀘 움직임 정체 3분 · 진행중2로 전환');self.assertEqual(LOCAL.stalled,'quest1')
  LOCAL.active=None;LOCAL.stalled=None;emit('서브퀘 움직임 정체 3분 · 진행중2로 전환');self.assertIsNone(LOCAL.stalled)
 def test_stalled_quest_persists_and_other_eligible_quest_can_run(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'settings').mkdir()
   b=QuestBook(root,'test-char')
   proof=dict(objective='대화',completed=False,suitable=True,actionable=True,accepted=True)
   a=b.observe('sub_quest','[외전] 테스트1',**proof);other=b.observe('sub_quest','[외전] 테스트2',**proof)
   b.activate(a);b.item['quests'][a]['deaths']=1;b.commit();defer_stalled(b,a)
   restarted=QuestBook(root,'test-char')
   self.assertEqual(restarted.item['quests'][a]['deaths'],1)
   self.assertTrue(restarted.item['quests'][a]['block']['functional_hold'])
   self.assertFalse(reviewable_block(restarted.item['quests'][a]['block']))
   self.assertTrue(reviewable_block({'reason':'condition'}))
   self.assertFalse(restarted.eligible(a,100000));self.assertTrue(restarted.eligible(other,100000))
   self.assertFalse(restarted.item['quests'][a]['completed'])
   self.assertEqual(restarted.choose([a,other],'sub_quest',100000),other)
   self.assertTrue(release_functional_hold(restarted,a))
   self.assertTrue(restarted.eligible(a,100000));self.assertFalse(release_functional_hold(restarted,a))
 def test_only_evidenced_mountain_root_aliases_inherit_active_hold(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'settings').mkdir();book=QuestBook(root,'one')
   def add(key,title,mode='sub_quest'):
    book.item['quests'][key]={'title':title,'mode':mode,'group':True,'deaths':0,'completed':False,'suitable':True,'actionable':True,'accepted':True}
   add('original','[외전] 1산길의 호환');add('alias','[외전] 산길의 호환')
   add('different','[외전] 산길의 호환2');add('main','[외전] 산길의 호환','main_quest')
   defer_stalled(book,'original')
   self.assertTrue(same_verified_root_blocked(book,'alias',100000));self.assertFalse(group_eligible(book,'alias',100000))
   self.assertFalse(same_verified_root_blocked(book,'different',100000));self.assertTrue(group_eligible(book,'different',100000))
   self.assertFalse(same_verified_root_blocked(book,'main',100000))
   reopened=QuestBook(root,'one');self.assertTrue(same_verified_root_blocked(reopened,'alias',100000))
   self.assertEqual(reopened.item['quests']['alias']['deaths'],0)
   self.assertTrue(release_functional_hold(reopened,'original'));self.assertFalse(same_verified_root_blocked(reopened,'alias',100000))
 def test_alias_preserves_death_hold_until_power_threshold(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'settings').mkdir();book=QuestBook(root,'one')
   for key,title in [('a','[외전] 산길의 호환'),('b','[외전] ㅣ산길의 호환')]:
    book.item['quests'][key]={'title':title,'mode':'sub_quest','group':True,'deaths':0,'completed':False,'suitable':True,'actionable':True,'accepted':True}
   book.defer('a','death',baseline=100000)
   self.assertTrue(same_verified_root_blocked(book,'b',114999));self.assertFalse(same_verified_root_blocked(book,'b',115000))

if __name__=='__main__':unittest.main(verbosity=2)
