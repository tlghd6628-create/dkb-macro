"""Treasure by its words at 1366x768: saved real frames and the native checks. Never a game test."""
import os,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap
import numpy as np
from PIL import Image
import owner_hd as hd
import owner_text as text
import owner_treasure as t
from roi_runtime import RoiDetector
from project_adapter import treasure_entry as te
FRAMES=Path(os.environ.get('DKB_FRAMES',r'C:\Users\user\dkb-macro\image_scope_20261104\hd_frames'))
MENU_SHOT=os.environ.get('DKB_MENU_SHOT','')
T1,T2,T3,T4='체크_보물찾기_타바로1','체크_보물찾기_타바로2','체크_보물찾기_타바로3','체크_보물찾기_타바로4'
OPENED,CLOSED='버튼_보물찾기_타바로지방열림','버튼_보물찾기_타바로지방'

def shot(name):
 return hd.make_frame(np.asarray(Image.open(FRAMES/('pc2_treasure_%s_hd.png'%name)).convert('RGB')))


@unittest.skipUnless((FRAMES/'pc2_treasure_open_hd.png').exists(),'saved frames not on this PC')
class SavedFrames(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  hd.install_reading();text.set_root(bootstrap.A);t.install_words();t._running[0]=1
  cls.d=RoiDetector(bootstrap.A/'profiles/DKB',list(te.NAMES))
  cls.open,cls.gamori,cls.done=shot('open'),shot('gamori'),shot('done')
 @classmethod
 def tearDownClass(cls):t._running[0]=0
 def found(self,name,frame):return self.d.find(name,frame,threshold=.85)
 def real_of(self,hit,frame):return hd.to_real_point(hit[0],hit[1],frame.layout)
 def test_title(self):
  for frame in (self.open,self.gamori,self.done):self.assertIsNotNone(self.found('체크_보물찾기',frame))
 def test_the_open_tab_is_told_from_the_closed_ones(self):
  self.assertIsNotNone(self.found(OPENED,self.open));self.assertIsNone(self.found(CLOSED,self.open))
  self.assertIsNotNone(self.found(CLOSED,self.gamori));self.assertIsNone(self.found(OPENED,self.gamori))
  self.assertIsNotNone(self.found('버튼_보물찾기_가모리지방열림',self.gamori));self.assertIsNone(self.found('버튼_보물찾기_가모리지방',self.gamori))
 def test_a_closed_tab_is_pressed_on_its_word_wherever_it_moved(self):
  x,y=self.real_of(self.found('버튼_보물찾기_수아리지방',self.open),self.open)
  self.assertLess(abs(x-77),12);self.assertLess(abs(y-358),6)
  x,y=self.real_of(self.found('버튼_보물찾기_수아리지방',self.gamori),self.gamori)
  self.assertLess(abs(x-77),12);self.assertLess(abs(y-316),6)
 def test_rows_are_found_under_the_badge_too(self):
  for name,y in ((T1,128),(T2,171),(T3,214),(T4,256)):
   with self.subTest(name=name):
    hit=self.found(name,self.open);self.assertIsNotNone(hit)
    self.assertLess(abs(self.real_of(hit,self.open)[1]-y),6)
 def test_the_castle_done_badge(self):
  for frame in (self.open,self.done):self.assertIsNotNone(te.completion_marker_hit(self.d,frame,t.CASTLE_DONE))
  self.assertIsNone(te.completion_marker_hit(self.d,self.gamori,t.CASTLE_DONE))
 def test_only_the_lit_row_counts_as_selected(self):
  hit=(0,0,(0,0,1,1))
  self.assertTrue(te.selected_point_active(self.d,self.open,T2,hit));self.assertTrue(te.selected_point_confirmed(self.d,self.open,T2,hit))
  for name in (T1,T3,T4):
   with self.subTest(name=name):self.assertFalse(te.selected_point_active(self.d,self.open,name,hit))
  self.assertTrue(te.selected_point_active(self.d,self.done,T1,hit))
  for name in (T2,T3,T4):
   with self.subTest(name=name):self.assertFalse(te.selected_point_active(self.d,self.done,name,hit))
 def test_first_card_shows_a_shortcut_or_the_current_place(self):
  short,here='버튼_보물찾기_타바로_바로가기','체크_보물찾기_타바로_현위치'
  self.assertIsNotNone(self.found(short,self.open));self.assertIsNone(self.found(here,self.open))
  self.assertIsNotNone(self.found(here,self.done));self.assertIsNone(self.found(short,self.done))
 def test_claim_button(self):
  x,y=self.real_of(self.found('버튼_보물찾기_보상모두받기',self.done),self.done)
  self.assertLess(abs(x-1244),12);self.assertLess(abs(y-729),6)
 @unittest.skipUnless(MENU_SHOT,'no menu shot given')
 def test_menu_entry_presses_the_icon_above_its_label(self):
  frame=hd.make_frame(np.asarray(Image.open(MENU_SHOT).convert('RGB')))
  x,y=self.real_of(self.found('버튼_보물찾기',frame),frame)
  self.assertLess(abs(x-1190),8);self.assertLess(abs(y-400),8)
 def test_other_names_and_other_screens_stay_with_the_pictures(self):
  self.assertEqual(t.word_answer('버튼_나가기',self.open),(False,None))
  t._running[0]=0
  try:self.assertIsNone(self.d.find(OPENED,self.open,threshold=.85))  # the picture still misses it, nothing read
  finally:t._running[0]=1


class Rules(unittest.TestCase):
 def row(self,word,y):return dict(text=word,rx=70,ry=y,bounds=(50,y-5,90,y+5))
 def test_no_winner_means_no_answer(self):
  real=np.full((400,200,3),120,np.uint8)
  self.assertIsNone(t.lit_tab(real,{'타바로지방':self.row('타바로지방',80),'가모리지방':self.row('가모리지방',200)}))
  self.assertIsNone(t.lit_tab(real,{'타바로지방':self.row('타바로지방',80)}))
 def test_frames_without_real_pixels_keep_the_native_check(self):
  frame=np.zeros((479,897,3),np.uint8);called=[]
  check=t._on_real(lambda d,f,n,*r:called.append(n) or 'native',lambda f,n:'words')
  self.assertEqual(check(None,frame,T1),'native');self.assertEqual(called,[T1])
 def test_power_policy_is_unchanged(self):
  self.assertEqual(t.allowed_points(None),['포인트_보물찾기_타바로1'])
  self.assertEqual(t.allowed_points(150236,recent_death=True),['포인트_보물찾기_타바로1'])
  self.assertEqual(len(t.allowed_points(127575)),4)


class CurrentCard(unittest.TestCase):
 """Stand-in rows, not a game test: only the card that says 현위치 loses its green power."""
 def test_only_the_current_card(self):
  from unittest.mock import patch
  rows=[{'text':'현위치','x':171,'y':85},{'text':'바로가기','x':334,'y':85}]
  with patch.object(t.text,'read',lambda *a,**k:rows):
   self.assertTrue(t.on_current_card(None,(180,99)))
   self.assertFalse(t.on_current_card(None,(334,99)))


if __name__=='__main__':unittest.main(verbosity=1)
