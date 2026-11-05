"""Shop rows from the words the reader really gave on the 1366x768 list (11-05). Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,unittest
import owner_shop_runtime_candidate as shop

Hold=shop.Hold


def row(y,x,text,score=.98):return dict(text=text,score=score,ry=y,rx=x+40,x=0,y=round(y/1.6),bounds=(x,y-9,x+80,y+9))


LIST=[row(119,76,'1단 체력 회복 물약'),row(139,16,'구매불가'),row(140,97,'100'),row(160,76,'구매 가능 796/651'),
 row(266,76,'영웅 장비 강화 비법서'),row(287,97,'15,000'),row(308,76,'도사 주간 한정:(3/50)'),
 row(340,75,'영웅 가호의 정수'),row(362,97,'15,000'),row(382,76,'도사 주간 한정:(0/50)'),
 row(636,76,'연타 도술 강화 요령서'),row(658,97,'50,000'),row(677,76,'도사 주간 한정:(0/10)'),
 row(710,75,'강타 도술 강화 요령서'),row(732,97,'50,000')]


class Words(unittest.TestCase):
 def test_row_with_name_price_and_limit(self):
  q=shop.quote_from_words(LIST,'영웅 장비 강화 비법서')
  self.assertEqual((q['price'],q['first'],q['limit'],q['bracketed'],q['sold_out']),(15000,3,50,True,False))
 def test_next_row_is_not_taken_for_this_one(self):
  q=shop.quote_from_words(LIST,'영웅 가호의 정수')
  self.assertEqual((q['price'],q['first'],q['limit']),(15000,0,50))
 def test_row_cut_off_at_the_bottom_is_not_on_screen(self):
  self.assertIsNone(shop.quote_from_words(LIST,'강타 도술 강화 요령서'))
 def test_item_not_shown(self):
  self.assertIsNone(shop.quote_from_words(LIST,'전설 장비 강화 비법서'))
 def test_sold_out_words_are_seen(self):
  q=shop.quote_from_words(LIST,'1단 체력 회복 물약')
  self.assertTrue(q['sold_out']);self.assertFalse(q['bracketed'])
 def test_a_low_score_price_is_not_a_price(self):
  rows=[row(266,76,'영웅 장비 강화 비법서'),row(287,97,'15,000',.5),row(308,76,'도사 주간 한정:(3/50)')]
  self.assertIsNone(shop.quote_from_words(rows,'영웅 장비 강화 비법서'))
 def test_one_misread_letter_is_still_the_name(self):
  rows=[row(266,76,'영웅 장비 강회 비법서'),row(287,97,'15,000'),row(308,76,'도사 주간 한정:(3/50)')]
  self.assertEqual(shop.quote_from_words(rows,'영웅 장비 강화 비법서')['price'],15000)
 def test_same_item_twice_stops(self):
  with self.assertRaises(Hold):shop.quote_from_words(LIST+[row(500,76,'영웅 장비 강화 비법서')],'영웅 장비 강화 비법서')


class Popup(unittest.TestCase):
 ROWS=[row(270,683,'수량 입력'),row(312,688,'영웅 장비 강화 비법서'),row(332,690,'상점 개당 가격:15,000'),row(350,681,'가방보유개수:605')]
 def test_name_price_owned(self):
  self.assertEqual(shop.popup_from_words(self.ROWS,'영웅 장비 강화 비법서'),(True,15000,605))
 def test_another_item_is_not_this_one(self):
  self.assertFalse(shop.popup_from_words(self.ROWS,'절명 도술 강화 요령서')[0])
 def test_missing_number_is_none(self):
  self.assertIsNone(shop.popup_from_words(self.ROWS[:2],'영웅 장비 강화 비법서')[1])


if __name__=='__main__':unittest.main()
