"""The clan battle screen by its words. Stubbed logic always; real saved 1366x768 frames when they are on this PC. No input."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import os,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
import owner_hd as hd
import owner_image_scope as scope
import owner_text as text

PROFILE=bootstrap.A/'profiles/DKB'
FRAMES=Path(os.environ.get('DKB_HD_FRAMES',r'C:\Users\user\dkb-macro\image_scope_20261104\hd_frames'))
TABS={'요신토벌령':'yosin','결계지방어':'defense','미혹의정원':'garden','신기쟁탈전':'artifact'}

def real(name):return np.asarray(Image.open(FRAMES/('pc2_clan_%s_hd.png'%name)).convert('RGB'))

class Window(unittest.TestCase):
 def setUp(self):
  scope.LOCAL.frame=None
 def test_the_title_decides_on_a_real_frame(self):
  frame=S(hi=np.zeros((768,1366,3),np.uint8))
  with patch.object(text,'shows_title',return_value=True):self.assertTrue(scope.window_open(PROFILE,'clan',frame))
  frame=S(hi=np.zeros((768,1366,3),np.uint8))
  with patch.object(text,'shows_title',return_value=False):self.assertFalse(scope.window_open(PROFILE,'clan',frame))
 def test_a_frame_without_real_pixels_keeps_the_picture(self):
  with patch.object(scope,'_witnessed',return_value=True) as seen,patch.object(text,'shows_title') as words:
   self.assertTrue(scope.window_open(PROFILE,'clan',np.zeros((479,897,3),np.uint8)))
  seen.assert_called_once();words.assert_not_called()
 def test_a_failed_read_falls_back_to_the_picture(self):
  frame=S(hi=np.zeros((768,1366,3),np.uint8))
  with patch.object(text,'shows_title',side_effect=RuntimeError('x')),patch.object(scope,'_witnessed',return_value=False) as seen:
   self.assertFalse(scope.window_open(PROFILE,'clan',frame))
  seen.assert_called_once()

class Table(unittest.TestCase):
 def test_only_navigation_is_listed(self):
  for name,(_,key,_zone) in scope.WORDS.items():
   if key=='clan':self.assertFalse(scope.committed(name),name)
  for name in ('버튼_문파_참가신청','버튼_문파_참가신청확인','버튼_문파_분신등록','버튼_문파_분신등록확인','버튼_문파_전투입장','버튼_문파_활동보상','체크_문파_분신완료','체크_문파_참가완료'):
   self.assertNotIn(name,scope.WORDS)

def row(text,box,score=.95):return {'text':text,'score':score,'box':box}

class Split(unittest.TestCase):
 def test_a_word_split_at_its_space_is_one_word(self):
  got=scope._joined([row('결계지',(28,110,62,125)),row('방어',(58,111,82,124))],'결계지방어')
  self.assertEqual([g['box'] for g in got],[(28,110,82,125)])
 def test_a_stray_stroke_does_not_stop_it(self):
  self.assertEqual(len(scope._joined([row('결계지',(28,111,63,124)),row('ㅣ방어',(57,111,82,125))],'결계지방어')),1)
 def test_parts_on_other_lines_or_far_apart_do_not_join(self):
  self.assertFalse(scope._joined([row('결계지',(28,110,62,125)),row('방어',(58,150,82,164))],'결계지방어'))
  self.assertFalse(scope._joined([row('결계지',(28,110,62,125)),row('방어',(120,111,144,124))],'결계지방어'))
 def test_a_weak_part_does_not_join(self):
  self.assertFalse(scope._joined([row('결계지',(28,110,62,125),.5),row('방어',(58,111,82,124))],'결계지방어'))

class Menu(unittest.TestCase):
 ENTRIES=[row('성장',(674,103,693,114)),row('도술',(723,105,738,113)),row('가호',(769,103,788,114)),row('문파',(627,217,646,230)),row('파전투',(624,375,654,386),.88)]
 def setUp(self):
  scope.LOCAL.frame=None;scope.LOCAL.words={}
  self.d=RoiDetector(PROFILE,['버튼_전체매뉴_문파'])
  patcher=patch.object(scope,'note');patcher.start();self.addCleanup(patcher.stop)
 def frame(self):
  made=np.zeros((479,897,3),np.uint8).view(hd.HdFrame);made.hi=np.zeros((768,1366,3),np.uint8);return made
 def test_found_by_its_word_in_the_menu(self):
  with patch.object(scope,'_read_words',return_value=self.ENTRIES):
   self.assertEqual(scope.word_hit(self.d,'버튼_전체매뉴_문파',self.frame(),.95,None)[:2],(636,223))
 def test_no_menu_entries_no_answer(self):
  with patch.object(scope,'_read_words',return_value=[row('문파',(627,217,646,230))]):
   self.assertIsNone(scope.word_hit(self.d,'버튼_전체매뉴_문파',self.frame(),.95,None))
 def test_the_battle_entry_does_not_answer_for_it(self):
  rows=[r for r in self.ENTRIES if r['text']!='문파']+[row('문파전투',(620,375,654,386))]
  with patch.object(scope,'_read_words',return_value=rows):
   self.assertIsNone(scope.word_hit(self.d,'버튼_전체매뉴_문파',self.frame(),.95,None))

@unittest.skipUnless((FRAMES/'pc2_clan_battle_yosin_hd.png').exists(),'saved real frames are not on this PC')
class SavedFrames(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  text.set_root(PROFILE.parents[1]);hd.install_reading()
  cls.d=RoiDetector(PROFILE,[n for n,s in scope.WORDS.items() if s[1]=='clan'])
  cls.frames={k:hd.make_frame(real('battle_'+k)) for k in TABS.values()}
 def setUp(self):
  scope.LOCAL.words={};scope.LOCAL.frame=None
  for patcher in (patch.object(scope,'note'),patch.object(scope,'WORD_EVERY',0)):
   patcher.start();self.addCleanup(patcher.stop)
 def hit(self,name,frame):
  scope.LOCAL.words={}
  return scope.word_hit(self.d,name,frame,.9,None)
 def test_every_tab_is_found_on_every_battle_screen(self):
  for frame in self.frames.values():
   for word in TABS:self.assertIsNotNone(self.hit('버튼_문파_'+word,frame),word)
 def test_the_chosen_tab_alone_shows_as_chosen(self):
  for word,key in TABS.items():
   for other,frame in self.frames.items():
    self.assertEqual(self.hit('체크_문파_'+word,frame) is not None,other==key,(word,other))
 def test_a_tab_press_lands_on_its_words(self):
  got=self.hit('버튼_문파_미혹의정원',self.frames['yosin'])
  rx,ry=hd.to_real_point(got[0],got[1],self.frames['yosin'].layout)
  self.assertLess(abs(rx-88),14);self.assertLess(abs(ry-241),10)
 def test_the_battle_tab_lands_on_its_words(self):
  frame=hd.make_frame(np.asarray(Image.open(FRAMES/'pc2_clan_hd.png').convert('RGB')))
  got=self.hit('버튼_문파_전투2',frame)
  self.assertIsNotNone(got)
  rx,ry=hd.to_real_point(got[0],got[1],frame.layout)
  self.assertLess(abs(rx-1174),25);self.assertLess(abs(ry-82),10)
 def test_the_menu_entry_on_the_saved_menu(self):
  path=os.environ.get('DKB_HD_MENU')
  if not path:self.skipTest('no saved menu frame named')
  frame=hd.make_frame(np.asarray(Image.open(path).convert('RGB')))
  got=RoiDetector(PROFILE,['버튼_전체매뉴_문파']);hit=scope.word_hit(got,'버튼_전체매뉴_문파',frame,.95,None)
  self.assertIsNotNone(hit)
  rx,ry=hd.to_real_point(hit[0],hit[1],frame.layout)
  self.assertLess(abs(rx-984),29);self.assertLess(abs(ry-340),32)
 def test_not_on_the_training_screen(self):
  frame=hd.make_frame(np.asarray(Image.open(FRAMES/'pc2_clan_training_hd.png').convert('RGB')))
  for name in ('버튼_문파_전투2','버튼_문파_미혹의정원','체크_문파_미혹의정원'):self.assertIsNone(self.hit(name,frame),name)

if __name__=='__main__':unittest.main()
