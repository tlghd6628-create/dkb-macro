exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import tempfile,unittest
from types import SimpleNamespace as NS
from owner_mission_policy import QuestBook
from owner_mission_ui import side_story_gate
from owner_story_groups import known_root,row_title,same_root


def word(text,y,rx=200,score=.95):return {'text':text,'y':y,'rx':rx,'score':score}


class Return(unittest.TestCase):
 def book(self,directory):
  book=QuestBook(directory,'a')
  main=book.observe('main_quest','[4장] 쉬어가는 길',objective='외전가모리의방랑도사완료하기',suitable=True,actionable=False)
  book.defer(main,'prerequisite',prerequisite='가모리의방랑도사')
  return book,main
 def test_step_under_a_new_objective_counts_as_reopened(self):
  with tempfile.TemporaryDirectory() as directory:
   book,main=self.book(directory)
   story=book.observe('sub_quest','[외전] 다른 이야기',suitable=True,actionable=True);book.activate(story)
   new=book.observe('main_quest','[4장]쉬어가는 길',objective='산신과대화하기',suitable=True,actionable=True)
   self.assertNotEqual(new,main)
   book.prerequisite_proved(new)
   self.assertTrue(book.item['quests'][new]['condition_recovered'])
   self.assertNotIn('block',book.item['quests'][main])
   self.assertEqual(book.choose([new],'main_quest',100),new)
 def test_held_while_the_side_story_runs(self):
  with tempfile.TemporaryDirectory() as directory:
   book,main=self.book(directory)
   self.assertFalse(book.story_finished('가모리의방랑도사'))
   self.assertFalse(book.eligible(main,100))
 def test_finished_story_is_found_under_a_misread_title(self):
  with tempfile.TemporaryDirectory() as directory:
   book,_=self.book(directory)
   key=book.observe('sub_quest','[외전] 가모리의 방랑!  도사',completed=True)
   self.assertTrue(book.item['quests'][key]['completed'])
   self.assertTrue(book.story_finished(side_story_gate("임무 목표 외전‘가모리의 방랑 도사’완료하기")))
 def test_another_chapter_or_step_is_not_cleared(self):
  with tempfile.TemporaryDirectory() as directory:
   book,main=self.book(directory)
   other=book.observe('main_quest','[5장] 쉬어가는 길',objective='다른일',suitable=True,actionable=True)
   book.prerequisite_proved(other)
   self.assertIn('block',book.item['quests'][main])
   self.assertNotIn('condition_recovered',book.item['quests'][other])


class Names(unittest.TestCase):
 def entries(self):
  return NS(item={'quests':{
   'a':{'group':True,'title':'[외전] 가모리의 방랑 도사','last_seen':5},
   'b':{'group':True,'title':'[외전] 가모리의 ㅣ방랑 도사','last_seen':9},
   'c':{'group':True,'title':'[외전]가모리의 방랑 도사','last_seen':1,'block':{'reason':'death'}},
   'd':{'group':True,'title':'[외전] 헤어진 두 도사 1','last_seen':1},
   'e':{'group':True,'title':'[외전] 헤어진 두 도사 2','last_seen':1},
   'f':{'group':True,'title':'서사 임무 (이름 확인 중)','last_seen':99}}})
 def test_hold_on_any_reading_of_the_name_stays(self):
  self.assertEqual(known_root(self.entries(),'[외전] 가모리의 방랑 도사'),'c')
 def test_digits_keep_steps_apart(self):
  self.assertEqual(known_root(self.entries(),'[외전] 헤어진 두 도사 2'),'e')
  self.assertFalse(same_root('[외전] 헤어진 두 도사 1','[외전] 헤어진 두 도사 2'))
 def test_placeholder_and_unknown_are_not_matched(self):
  self.assertIsNone(known_root(self.entries(),'[외전] 전혀 다른 이름입니다'))
 def test_row_title_keeps_the_row_and_drops_the_column_beside_it(self):
  words=[word('[외전]',150,120),word('남편의 안부',151,180),word('12,300',150,700),word('적합',150,760),word('[첫걸음] 도술 구매',188)]
  self.assertEqual(row_title(words,150),'[외전] 남편의 안부')
  self.assertIsNone(row_title(words,300))


if __name__=='__main__':unittest.main()
