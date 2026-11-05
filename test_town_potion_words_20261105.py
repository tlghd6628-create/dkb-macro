"""The town potion row and the shop's marks, read by words. Fake word rows only; no game."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import bootstrap
import owner_remote_potion_limit_candidate as limits
import owner_shop_runtime_candidate as shop

def word(text,ry,rx=130):return dict(text=text,score=.99,rx=rx,ry=ry,x=rx,y=ry,bounds=(rx-40,ry-8,rx+40,ry+8))
USED_UP=[word('1단 체력 회복 물약',118),word('구매불가',138,44),word('100',139,114),word('구매 가능 320/250',160),
         word('영웅 장비 강화 비법서',193),word('15,000',214),word('도사 주간 한정:(1/50)',234)]
AT_LIMIT=[word('1단 체력 회복 물약',118),word('구매불가',138,44),word('100',139,114),word('구매 가능 250/250',160)]
OPEN=[word('1단 체력 회복 물약',118),word('100',139,114),word('구매 가능 120/250',160)]
class Real(np.ndarray):hi=np.zeros((768,1366,3),np.uint8)
FRAME=np.zeros((479,897,3),np.uint8).view(Real)

def words(rows):
 return patch('owner_text.read',return_value=rows),patch('owner_text.shows_title',return_value=True)

class Tests(unittest.TestCase):
 def under(self,rows,call):
  a,b=words(rows)
  with a,b:return call()
 def test_row_says_used_up(self):
  self.assertEqual(self.under(USED_UP,lambda:limits.tier_words(FRAME,'1단물약')),(320,250,True))
  self.assertTrue(self.under(USED_UP,lambda:limits.sold_out(FRAME,'1단물약')))
 def test_open_row_and_missing_tier_are_not_used_up(self):
  self.assertFalse(self.under(OPEN,lambda:limits.sold_out(FRAME,'1단물약')))
  self.assertFalse(self.under(USED_UP,lambda:limits.sold_out(FRAME,'2단물약')))
 def test_other_screen_says_nothing(self):
  with patch('owner_text.shows_title',return_value=False):self.assertIsNone(limits.tier_words(FRAME,'1단물약'))
 def test_full_needs_the_label_and_the_same_numbers(self):
  ui=NS(frame=lambda:FRAME,context=NS(wait=lambda *a:None))
  self.assertEqual(self.under(AT_LIMIT,lambda:limits.observed_full(ui,'1단물약')),250)
  # 320/250 with 구매 불가: over the limit is as finished as at it (the 11-05 screen showed 796/651).
  self.assertEqual(self.under(USED_UP,lambda:limits.observed_full(ui,'1단물약')),320)
  self.assertIsNone(self.under(OPEN,lambda:limits.observed_full(ui,'1단물약')))
 def test_marks_are_words_on_the_real_screen(self):
  with patch('owner_text.read',return_value=[word('수량 입력',270,688)]):self.assertTrue(shop._quantity_shown(FRAME))
  with patch('owner_text.read',return_value=[]):self.assertFalse(shop._quantity_shown(FRAME))
  with patch('owner_text.read',return_value=[word('합계',641,545)]):self.assertTrue(shop._cart_bar(FRAME))
  with patch('owner_text.read',return_value=[]):self.assertFalse(shop._cart_bar(FRAME))
 def test_over_limit_row_quotes_nothing_left(self):
  ui=NS(frame=lambda:FRAME,context=NS(wait=lambda *a:None),adapter=NS(project=NS(root=None)))
  with patch('owner_text.read',return_value=USED_UP):quote=shop._real_quote(ui,'1단 체력 회복 물약')
  self.assertEqual(quote['remaining'],0)
 def test_over_limit_without_the_label_still_waits(self):
  rows=[word('1단 체력 회복 물약',118),word('100',139,114),word('구매 가능 320/250',160)]
  ui=NS(frame=lambda:FRAME,context=NS(wait=lambda *a:None),adapter=NS(project=NS(root=None)))
  with patch('owner_text.read',return_value=rows),self.assertRaises(shop.Pending):shop._real_quote(ui,'1단 체력 회복 물약')

if __name__=='__main__':unittest.main()
