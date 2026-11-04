exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf8'))
import unittest,numpy as np
from PIL import Image
import owner_energy_counter_glyph_candidate as g

# Artificial characters exercise parsing mechanics only. They are not game
# screenshots and must never become a production numeric reference atlas.
FONT='0123456789/'
def image(key):
 # Distinct random test symbols deliberately avoid relying on game glyphs.
 mask=np.random.default_rng(ord(key)).integers(0,2,size=(7,5),dtype=np.uint8)
 mask[0,0]=mask[0,4]=mask[6,0]=mask[6,4]=1
 return np.repeat((mask*255)[:,:,None],3,axis=2)
def atlas():return g.Atlas([g.sample(k,image(k),'synthetic-only') for k in FONT])
def frame(text):
 a=np.zeros((479,897,3),dtype=np.uint8);x=436
 for char in text:
  px=image(char);a[322:329,x:x+5]=px;x+=6
 return a

class CounterTests(unittest.TestCase):
 def test_complete_atlas_parses_two_independent_frames(self):
  self.assertEqual(g.read_pair(frame('1/50'),frame('1/50'),atlas()),(1,50))
  self.assertEqual(g.read_pair(frame('2/49'),frame('2/49'),atlas()),(2,49))
  self.assertEqual(g.read_pair(frame('1/60'),frame('1/60'),atlas()),(1,60))
 def test_missing_six_never_guesses_five(self):
  partial=g.Atlas([g.sample(k,image(k),'synthetic-only') for k in FONT if k!='6'])
  self.assertIsNone(g.read_pair(frame('1/50'),frame('1/50'),partial))
  self.assertIsNone(g.read_pair(frame('1/60'),frame('1/60'),partial))
 def test_ambiguous_competitors_and_disagreeing_frames_hold(self):
  references=[g.sample(k,image(k),'synthetic-only') for k in FONT if k!='6']
  references.append(g.sample('6',image('5'),'synthetic-only'))
  self.assertIsNone(g.read_pair(frame('1/50'),frame('1/50'),g.Atlas(references)))
  self.assertIsNone(g.read_pair(frame('1/50'),frame('1/60'),atlas()))
 def test_real_1_50_incomplete_atlas_still_unknown(self):
  f=[np.asarray(Image.open(C/'live_fixtures'/f'energy_box_select_native_{i}.png').convert('RGB')) for i in (1,2)]
  # Exactly observed actual glyph crops. No speculative 6 or other digits.
  boxes={'1':(439,323,442,331),'/':(443,323,447,331),'5':(447,323,453,331),'0':(453,323,458,331)}
  samples=[g.sample(k,f[0][y1:y2,x1:x2].copy(),'actual 1/50') for k,(x1,y1,x2,y2) in boxes.items()]
  self.assertIsNone(g.read_pair(*f,g.Atlas(samples)))

if __name__=='__main__':unittest.main(verbosity=2)
