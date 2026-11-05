"""Choosing an option by its word from what the reader really gave. On arrays only, never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,unittest
import numpy as np
import owner_game_settings as g


def word(value,x=700):return dict(text=value,rx=x,ry=100,x=x,y=60,bounds=(x-30,92,x+30,108))
def row(*values):return dict(label='x',y=100,row=word('x',300),options=[word(v,700+150*i) for i,v in enumerate(values)])


class Options(unittest.TestCase):
 def pick(self,wanted,*values):
  found=g.option_for(row(*values),wanted)
  return found and found['text']
 def test_misread_does_not_turn_left_into_right(self):
  self.assertEqual(self.pick('좌측','마우스 좌측 버른','마우스 우측 버튼'),'마우스 좌측 버른')
 def test_misread_does_not_turn_on_into_off(self):
  self.assertEqual(self.pick('켜기','그림자 끄기','그렇자 켜기'),'그렇자 켜기')
 def test_zero_read_as_a_letter_is_still_sixty(self):
  self.assertEqual(self.pick('60fps','30fps','45fps','6ofps','제한 없음'),'6ofps')
  self.assertEqual(self.pick('60fps','30fps','45fps','6ofpe','제한 없음'),'6ofpe')
 def test_a_number_nobody_shows_presses_nothing(self):
  self.assertIsNone(self.pick('60fps','30fps','45fps','제한 없음'))
 def test_use_is_not_do_not_use(self):
  self.assertEqual(self.pick('사용','사용안함','사용'),'사용')
  self.assertEqual(self.pick('사용 안 함','사용안함','사용'),'사용안함')
  self.assertEqual(self.pick('사용 안 함','사용안할','사용'),'사용안할')
  self.assertIsNone(self.pick('사용','사용안함'))
 def test_window_mode_is_not_full_screen(self):
  self.assertEqual(self.pick('창 모드','창모드','창 모드(전체 화면)'),'창모드')
 def test_close_spelling_with_a_rival_presses_nothing(self):
  self.assertIsNone(self.pick('가나다라','가나다마','가나다바'))


class Reading(unittest.TestCase):
 def test_icons_and_numbers_are_not_labels_or_options(self):
  rows=[word('88',205),word('카메라 흔들림',300),word('100%',620),word('+',980),word('사용 안함',1080),word('사용',1227)]
  found=g.panel_rows(rows)
  self.assertEqual([r['label'] for r in found],['카메라 흔들림']);self.assertEqual([o['text'] for o in found[0]['options']],['사용 안함','사용'])
 def test_resolution_stays_an_option(self):
  self.assertEqual([o['text'] for o in g.panel_rows([word('해상도',300),word('1366×768',900)])[0]['options']],['1366×768'])
 def test_lighter_pill_is_the_chosen_one(self):
  real=np.full((200,1400,3),30,np.uint8);a=word('사용 안함',700);b=word('사용',1000)
  real[90:110,640:760]=90
  self.assertIs(g.chosen(real,dict(label='x',options=[a,b])),a)
 def test_no_clear_difference_is_no_answer(self):
  real=np.full((200,1400,3),30,np.uint8)
  self.assertIsNone(g.chosen(real,dict(label='x',options=[word('사용 안함',700),word('사용',1000)])))
 def test_only_one_word_is_no_answer(self):
  self.assertIsNone(g.chosen(np.zeros((200,1400,3),np.uint8),row('사용')))
 def test_compare_sorts_rows(self):
  real=np.full((200,1400,3),30,np.uint8);real[90:110,640:760]=90
  shown=[dict(label='이펙트 표시',y=100,row=word('x',300),options=[word('켜기',700),word('끄기',1000)])]
  right,press,unclear,absent=g.compare(shown,real,(('이펙트 표시','끄기'),('구름 효과','끄기')))
  self.assertEqual(right,[]);self.assertEqual(press[0][1],'끄기');self.assertEqual(absent,[('구름 효과','끄기')])


if __name__=='__main__':unittest.main()
