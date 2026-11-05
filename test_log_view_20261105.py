"""Main window log filter, on a plain Text widget. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import unittest,tkinter as tk
from owner_log_view import hidden,install


class Lines(unittest.TestCase):
 def test_preparation_lines_are_hidden(self):
  for text in ('09:29:27 현재 적용 버전 · 16','09:29:33 세부설정 창 열림','09:30:07 인식 준비 종료 · 40.1초 · 완료',
               '정보창 열림 · 좌우 패널 확인','퀘스트 상태판정: mode=sub_quest selected=quest_active','09:17:39 완료'):
   self.assertTrue(hidden(text),text)
 def test_what_the_program_did_stays(self):
  for text in ('09:18:40 상점 구매 · 천요석 1개 · 합계 100000','실전 TEST 결과 · 잡화상점 구매 · 구매 2회',
               '상점 품목 미완료 · 천요석 · 판독 확인 필요','장비 분해 완료 · 일반','자동 동작 오류','이전 상점 구매 정리 · 천요석 · 구매됨'):
   self.assertFalse(hidden(text),text)


class Widget(unittest.TestCase):
 def setUp(self):
  self.tk=tk.Tk();self.tk.withdraw();self.addCleanup(self.tk.destroy);self.text=tk.Text(self.tk);install(self.text);install(self.text)
 def test_only_kept_lines_reach_the_widget(self):
  self.text.insert('end','09:29:27 현재 적용 버전 · 16\n')
  self.text.insert('end','09:18:40 상점 구매 · 천요석 1개\n','tag')
  self.assertEqual(self.text.get('1.0','end').strip(),'09:18:40 상점 구매 · 천요석 1개')


if __name__=='__main__':unittest.main()
