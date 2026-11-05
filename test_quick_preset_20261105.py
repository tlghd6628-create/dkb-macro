"""H preset menu: frames saved from the game and a fake service. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
from types import SimpleNamespace as S
import numpy as np
from PIL import Image
import owner_quick_preset as quick

LIVE=HERE/'image_scope_20261104/live'


class Frames(unittest.TestCase):
 def read(self,name):
  path=LIVE/(name+'.png')
  if not path.exists():self.skipTest('saved frame not on this PC')
  return quick.lit_letter(np.asarray(Image.open(path).convert('RGB')))
 def test_lit_letter(self):
  self.assertEqual(self.read('h2'),'A');self.assertEqual(self.read('h5'),'B')
 def test_closed_menu_reads_nothing(self):
  for name in ('h0','h3','a0','b1c','u5','look_shop'):self.assertIsNone(self.read(name),name)


def menu(letter):
 frame=np.full((479,897,3),50,dtype=np.uint8)
 if letter:
  y=quick.LETTERS[letter];frame[y-8:y+9,quick.X-8:quick.X+9]=110
 return frame


class FakeGame:
 """The H key toggles the menu; a pick changes the letter and closes it."""
 def __init__(self,current='A',takes=True):
  self.current=current;self.open=False;self.takes=takes;self.keys=0;self.clicks=[];self.context=S(wait=lambda *_:None,checkpoint=lambda:None)
 def check(self):pass
 def capture(self):return menu(self.current if self.open else None)
 def key(self,code):self.keys+=1;self.open=not self.open
 def click_hit(self,hit):
  self.clicks.append(hit[1]);self.open=False
  if self.takes:self.current=next(k for k,y in quick.LETTERS.items() if y==hit[1])


class Select(unittest.TestCase):
 def test_switches_and_leaves_the_menu_closed(self):
  game=FakeGame();self.assertTrue(quick.select(game,'B'))
  self.assertEqual(game.current,'B');self.assertFalse(game.open);self.assertEqual(game.clicks,[quick.LETTERS['B']])
 def test_already_on_it_presses_no_letter(self):
  game=FakeGame('B');self.assertTrue(quick.select(game,'B'));self.assertEqual(game.clicks,[]);self.assertFalse(game.open)
 def test_a_pick_that_did_not_take_is_false(self):
  game=FakeGame(takes=False);self.assertFalse(quick.select(game,'B'));self.assertFalse(game.open)
 def test_unknown_letter_presses_nothing(self):
  game=FakeGame();self.assertFalse(quick.select(game,'Z'));self.assertEqual(game.keys,0)


class RealPixels(unittest.TestCase):
 """Real-size arrays and a stand-in reader. What real letters read as is checked in the game, not here."""
 def real(self,*white):
  image=np.full((768,1366,3),60,dtype=np.uint8)
  for letter in white:
   x,y=round(quick.X*1.6-69.2),round(quick.LETTERS[letter]*1.6)
   image[y-5:y+5,x-5:x+5]=255
  return image
 def lit(self,image,reads):
  from unittest.mock import patch
  import owner_text
  calls=[]
  def read_area(root,area,**options):
   calls.append(options['top'])
   return [{'text':reads.pop(0),'score':.9}]
  with patch.object(owner_text,'read_area',read_area):return quick._real_lit(image),calls
 def test_white_letter_that_reads_as_itself(self):
  self.assertEqual(self.lit(self.real('B'),['B'])[0],'B')
 def test_white_art_that_reads_as_something_else(self):
  self.assertIsNone(self.lit(self.real('A'),['F2'])[0])
 def test_nothing_white_is_not_read_at_all(self):
  found,calls=self.lit(self.real(),[])
  self.assertIsNone(found);self.assertEqual(calls,[])
 def test_two_lit_letters_answer_nothing(self):
  self.assertIsNone(self.lit(self.real('A','B'),['A','B'])[0])
 def test_every_letter_is_clicked_on_the_column(self):
  import owner_hd
  frame=S(hi=self.real())
  for letter,y in quick.LETTERS.items():
   hit=quick._letter_hit(frame,letter)
   self.assertEqual(owner_hd.to_real_point(hit[0],hit[1]),(round(quick.X*1.6-69.2),round(y*1.6)),letter)


class Off(unittest.TestCase):
 def test_switch_off_does_nothing(self):
  adapter=S(values={'common.skill_preset.enabled':False})
  self.assertFalse(quick.run_skill_preset(adapter,S(),None))


if __name__=='__main__':unittest.main()
