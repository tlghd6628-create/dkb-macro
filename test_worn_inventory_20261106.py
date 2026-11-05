"""Worn items and blessings read from the bag's fixed tiles at 1366x768. Words from real reads and fake input; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import os,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_worn_stats as w
import owner_growth_current as current


def word(text,y):return dict(text=text,score=.9,rx=620,ry=y,bounds=(600,y-9,640,y+9))
REAL=np.zeros((768,1366,3),np.uint8)
import owner_hd
CLOSE=owner_hd.real_hit(*w.REAL_CLOSE)[:2]
FILTER2=owner_hd.real_hit(w.REAL_FILTER_X,w.REAL_FILTER_Y[2])[:2]
TILE=owner_hd.real_hit(*w.REAL_FIRST_TILE)[:2]


class Table(unittest.TestCase):
 def table(self,rows):
  with patch('owner_text.read_area',return_value=rows):return w.real_table(REAL)
 def test_an_item_has_four_rows(self):
  hits=self.table([word('강화',415),word('개방',443),word('돌파',471),word('각성',499)])
  self.assertEqual(list(hits),['enhance','opening','breakthrough','awaken'])
 def test_a_blessing_has_three(self):
  hits=self.table([word('강화',483),word('개방',511),word('각성',539)])
  self.assertEqual(list(hits),['enhance','opening','awaken'])
 def test_a_word_read_badly_keeps_its_row_by_spacing(self):
  hits=self.table([word('강화',415),word('개방',443),word('들파',471),word('각성',499)])
  self.assertEqual(hits['breakthrough'][1],471-13)
 def test_without_both_ends_there_is_no_table(self):
  self.assertIsNone(self.table([word('강화',415),word('개방',443)]))
  self.assertIsNone(self.table([word('개방',443),word('각성',499)]))
 def test_rows_at_another_spacing_are_no_table(self):
  self.assertIsNone(self.table([word('강화',415),word('각성',433)]))
 def test_the_lower_rows_of_a_blessing_are_inside_the_area(self):
  x,y,width,height=w.REAL_ROWS
  self.assertGreater(y+height,560)


class Open(unittest.TestCase):
 def test_the_info_tab_says_open(self):
  with patch('owner_text.read_area',return_value=[word('정보',314)]):self.assertTrue(w.real_popup(REAL))
  with patch('owner_text.read_area',return_value=[word('장비',314)]):self.assertFalse(w.real_popup(REAL))
 def test_a_real_frame_never_reaches_the_e_picture(self):
  frame=np.zeros((479,897,3),np.uint8).view(type('F',(np.ndarray,),{}));frame.hi=REAL
  with patch('owner_text.read_area',return_value=[word('정보',314)]),patch('owner_equipment_tooltip_candidate._badge',side_effect=AssertionError('E read')):
   self.assertTrue(w.popup(frame))


class Heading(unittest.TestCase):
 def test_title_and_grade(self):
  with patch('owner_text.read_area',side_effect=[[word('토끼 가호 장식2(귀속)',170)],[word('일반',217),word('세트가호',240)]]):
   self.assertEqual(w.real_heading(REAL),('토끼가호장식2(귀속)','일반'))
 def test_two_grades_are_none(self):
  with patch('owner_text.read_area',side_effect=[[word('x',170)],[word('일반',217),word('희귀',240)]]):
   self.assertIsNone(w.real_heading(REAL)[1])
 def test_kind_comes_from_the_title(self):
  self.assertEqual(w.blessing_kind('도깨비가호장식](귀속)'),'도깨비')
  self.assertEqual(w.blessing_kind('토까가호장식4(귀속)'),'토끼')
  self.assertEqual(w.blessing_kind('나비갓호장식3'),'나비')
  self.assertIsNone(w.blessing_kind('호랑이가호장식1'))


class Corrected(unittest.TestCase):
 def test_the_font_s_1_on_an_item(self):
  self.assertEqual(w.corrected({'enhance':50,'awaken':7},False)['awaken'],1)
  self.assertEqual(w.corrected({'enhance':50,'awaken':0},False)['awaken'],0)
 def test_over_the_top_is_no_reading(self):
  self.assertIsNone(w.corrected({'enhance':50,'awaken':3},False))
 def test_a_blessing_is_left_alone(self):
  self.assertEqual(w.corrected({'enhance':39,'awaken':7},True)['awaken'],7)


class Belongs(unittest.TestCase):
 def check(self,slot,words,title=''):
  with patch('owner_text.read_area',return_value=[word(text,217) for text in words]):return w.real_matches(REAL,slot,title)
 def test_an_item_by_its_part(self):
  self.assertTrue(self.check('다리',['각반']));self.assertTrue(self.check('반지',['반지']))
  self.assertFalse(self.check('팔찌',['부채']));self.assertFalse(self.check('목걸이',['갑옷']))
 def test_a_weapon_is_none_of_the_others(self):
  self.assertTrue(self.check('무기',['부채']));self.assertFalse(self.check('무기',['반지']));self.assertFalse(self.check('무기',[]))
  self.assertFalse(self.check('무기',['가호']))
 def test_a_blessing_by_its_digit(self):
  self.assertTrue(self.check('가호2',['가호'],'토끼가호장식2(귀속)'));self.assertFalse(self.check('가호2',['가호'],'도깨비가호장식1(귀속)'))
  self.assertTrue(self.check('가호1',['가호'],'도깨비가호장식](귀속)'))
  # pc2 11-06: 토끼 가호 장식1 read 장식7. There is no 장식7, so it is 1, never 2 to 5.
  self.assertTrue(self.check('가호1',['가호'],'토끼가호장식7(귀속)'));self.assertFalse(self.check('가호2',['가호'],'토끼가호장식7(귀속)'))
  self.assertFalse(self.check('가호2',['반지'],'수정세공 반지'))


class Numbers(unittest.TestCase):
 def test_a_row_unread_in_the_tight_crop_gets_a_roomier_look(self):
  places={'awaken':(690,499,45,26)}
  with patch('owner_text.read_area',side_effect=[[],[dict(word('1',512))]]) as reader:
   self.assertEqual(w.real_read(REAL,places),{'awaken':1})
  self.assertEqual(reader.call_count,2)
 def test_still_nothing_stays_unread(self):
  with patch('owner_text.read_area',return_value=[]):self.assertEqual(w.real_read(REAL,{'awaken':(690,499,45,26)}),{})


class Settled(unittest.TestCase):
 def run_reads(self,reads):
  values=iter(reads)
  service=NS(capture=lambda:NS(hi=REAL),check=lambda:None);context=NS(checkpoint=lambda:None,wait=lambda s:None)
  with patch.object(w,'real_table',return_value={'enhance':0,'awaken':0}),patch.object(w,'real_read',side_effect=lambda r,h:next(values,None)):
   return w.settled_read(service,context)
 def test_two_looks_in_a_row_must_agree(self):
  self.assertEqual(self.run_reads([{'enhance':50,'awaken':7},{'enhance':50,'awaken':1},{'enhance':50,'awaken':1}]),{'enhance':50,'awaken':1})
 def test_never_agreeing_is_nothing(self):
  self.assertIsNone(self.run_reads([{'enhance':50,'awaken':n} for n in range(9)]))
 def test_a_row_unread_on_some_looks_takes_what_most_gave(self):
  reads=[{'enhance':50},{'enhance':50,'awaken':1},{'enhance':50},{'enhance':50,'awaken':1},{'enhance':50,'awaken':7},{'enhance':50}]
  self.assertEqual(self.run_reads(reads),{'enhance':50,'awaken':1})
 def test_a_row_seen_once_never_answers(self):
  self.assertIsNone(self.run_reads([{'enhance':50}]*9))
 def test_a_tie_never_answers(self):
  self.assertIsNone(self.run_reads([{'enhance':50,'awaken':1},{'enhance':50,'awaken':7}]*3))


class Inspect(unittest.TestCase):
 """Each tile is clicked once, then the details close. A second click on a tile would take the item off."""
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
  self.root=Path(self.dir.name);self.clicks=[];self.open=False;self.opens=True
  def click_hit(hit):
   self.clicks.append(hit[:2]);self.open=self.opens and hit[:2]!=CLOSE
  self.service=NS(adapter=NS(project=NS(root=self.root)),check=lambda:None,capture=lambda:NS(hi=REAL),click_hit=click_hit)
  self.context=NS(checkpoint=lambda:None,wait=lambda s:None)
  from contextlib import contextmanager
  @contextmanager
  def transaction():yield
  self.inputs=NS(transaction=transaction,_guard_target=lambda:None,move=lambda x,y:None)
 def run_slot(self,slot,*,left=True,values=None,heading=('토끼가호장식2(귀속)','일반')):
  values={'enhance':20,'opening':2,'awaken':0} if values is None else values
  with patch.object(w,'popup',side_effect=lambda f:self.open),patch('owner_progression.inventory_parts',return_value=(left,False)),\
       patch.object(w,'settled_read',return_value=values),patch.object(w,'real_heading',return_value=heading),patch.object(w,'real_matches',return_value=self.matches),patch.object(w,'open_blessing_screen',return_value=True),patch.object(w,'offers_unequip',return_value=self.worn_one),\
       patch('owner_mission_ui.MissionUI.wheel'),patch('owner_skill_ui.SkillUI',lambda *a:NS()):
   return w.inspect_real(self.service,self.context,self.inputs,'profile','c',slot)
 def test_a_blessing_is_saved_by_its_place(self):
  self.assertIs(self.run_slot('가호2'),True)
  self.assertEqual(current.blessing_rows(self.root,'profile')[1],('2번','토끼','일반','20','2','0'))
  self.assertEqual(self.clicks[0],FILTER2);self.assertEqual(self.clicks[1],TILE);self.assertEqual(self.clicks[-1],CLOSE);self.assertEqual(len(self.clicks),3)
 def test_an_item_is_saved_by_its_slot(self):
  self.assertIs(self.run_slot('무기',values={'enhance':50,'opening':5,'breakthrough':3,'awaken':1},heading=('바람물결은선','희귀')),True)
  self.assertEqual(current.equipped_rows(self.root,'profile')[0],('무기','희귀','50','5','3','1'))
 def test_the_same_tile_is_not_read_again_soon(self):
  self.run_slot('가호2');self.clicks.clear()
  self.assertIs(self.run_slot('가호2'),False);self.assertEqual(self.clicks,[])
 def test_a_closed_bag_clicks_nothing(self):
  self.assertIs(self.run_slot('반지',left=False),False);self.assertEqual(self.clicks,[])
 def test_a_tile_that_opens_nothing_is_skipped_once(self):
  self.opens=False
  self.assertIs(self.run_slot('반지'),False);self.assertEqual(len(self.clicks),1)
 def test_unread_numbers_save_nothing_and_still_close(self):
  self.service.adapter._owner_worn_stats_cache={}
  with patch.object(w,'settled_read',return_value=None):pass
  self.assertIs(self.run_slot('가호2',values={}),False)
  self.assertEqual(current.blessing_rows(self.root,'profile')[1][1],'미확인');self.assertEqual(self.clicks[-1],CLOSE)
 matches=True;worn_one=True
 def test_a_first_tile_not_worn_saves_nothing_and_closes(self):
  self.worn_one=False
  self.assertIs(self.run_slot('가호2'),False)
  self.assertEqual(current.blessing_rows(self.root,'profile')[1][1],'미확인');self.assertEqual(self.clicks[-1],CLOSE)
 def test_leaving_by_the_growth_button_keeps_the_answer_and_presses_no_x(self):
  self.assertIs(self.run_decide(lambda values,grade,title:True),True)
  self.assertEqual(len(self.clicks),2)
 def test_not_leaving_closes_with_x(self):
  self.assertIs(self.run_decide(lambda values,grade,title:False),True)
  self.assertEqual(self.clicks[-1],CLOSE)
 def run_decide(self,decide):
  with patch.object(w,'popup',side_effect=lambda f:self.open),patch('owner_progression.inventory_parts',return_value=(True,False)),\
       patch.object(w,'settled_read',return_value={'enhance':20,'opening':2,'awaken':0}),patch.object(w,'real_heading',return_value=('토끼가호장식2(귀속)','일반')),patch.object(w,'real_matches',return_value=True),patch.object(w,'open_blessing_screen',return_value=True),patch.object(w,'offers_unequip',return_value=True),\
       patch('owner_mission_ui.MissionUI.wheel'),patch('owner_skill_ui.SkillUI',lambda *a:NS()):
   return w.inspect_real(self.service,self.context,self.inputs,'profile','c','가호2',decide=decide)
 def test_a_window_of_another_tile_saves_nothing_and_closes(self):
  self.matches=False
  self.assertIs(self.run_slot('가호2'),False)
  self.assertEqual(current.blessing_rows(self.root,'profile')[1][1],'미확인');self.assertEqual(self.clicks[-1],CLOSE)
 def test_an_unknown_kind_saves_nothing(self):
  self.assertIs(self.run_slot('가호1',heading=('호랑이가호장식1','희귀')),False)
  self.assertEqual(current.blessing_rows(self.root,'profile')[0][1],'미확인')


class Rows(unittest.TestCase):
 def setUp(self):
  self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup);self.root=Path(self.dir.name)
 def test_empty_rows_say_unread(self):
  self.assertEqual(current.blessing_rows(self.root,'p')[4],('5번','미확인','미확인','미확인','미확인','미확인'))
 def test_growth_keeps_the_kind_of_the_same_item(self):
  current.observe_blessing(self.root,'p','3번','도깨비','희귀',{'enhance':23,'opening':2,'awaken':0})
  current.observe_value(self.root,'p','blessings','3번',{'enhance':24},verified=True,item_identity='blessing-words:도깨비3')
  self.assertEqual(current.blessing_rows(self.root,'p')[2],('3번','도깨비','희귀','24','2','0'))
 def test_stale_slots_name_blessings_until_read(self):
  self.assertIn('가호1',w.stale_slots(self.root,'p'))
  current.observe_blessing(self.root,'p','1번','도깨비','희귀',{'enhance':39,'opening':3,'awaken':0})
  self.assertNotIn('가호1',w.stale_slots(self.root,'p'))
 def test_saved_values_come_back(self):
  current.observe_blessing(self.root,'p','1번','도깨비','희귀',{'enhance':39,'opening':3,'awaken':0})
  current._LOADED.clear();current._VALUES.clear()
  self.assertEqual(current.blessing_rows(self.root,'p')[0],('1번','도깨비','희귀','39','3','0'))


class TestButton(unittest.TestCase):
 def test_it_reads_everything_and_names_what_it_missed(self):
  import owner_challenge_test as t
  adapter=NS(_owner_worn_stats_cache={'old':1})
  with patch('owner_quest_preflight.read_power'),patch('owner_worn_stats.inspect_equipped',return_value=list(w.ALL_SLOTS[:15])) as read:
   self.assertEqual(t.worn(adapter,None,None),'15칸 확인 · 미확인 가호5')
  self.assertEqual(adapter._owner_worn_stats_cache,{});self.assertIsNone(read.call_args.kwargs.get('only'))
 def test_all_read_is_plain(self):
  import owner_challenge_test as t
  with patch('owner_quest_preflight.read_power'),patch('owner_worn_stats.inspect_equipped',return_value=list(w.ALL_SLOTS)):
   self.assertEqual(t.worn(NS(),None,None),'16칸 확인')
 def test_all_slots_are_the_real_ones(self):
  from owner_equipment_boxes import SLOTS
  self.assertEqual(set(w.ALL_SLOTS),set(SLOTS)|set(w.BLESSING_SLOTS));self.assertEqual(len(w.ALL_SLOTS),16)


if __name__=='__main__':unittest.main()
