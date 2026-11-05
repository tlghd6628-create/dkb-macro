"""1366x768 mapping and matching, on arrays and frames saved from the game. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,unittest
import numpy as np,cv2
from PIL import Image
import owner_hd as hd
hd.install_reading()

LIVE=HERE/'image_scope_20261104/live'
FRAMES=HERE/'image_scope_20261104/hd_frames'


def layout_of(*rules):
 """Columns of anchors across the screen."""
 grid=np.zeros(hd.GRID,np.uint8)
 for start,rule in rules:grid[:,start//hd.CELL:]=hd.RULES.index(rule)
 return hd.Layout('test',grid)


GROWTH=layout_of((0,'left'),(100,'center'),(700,'right'))
INVENTORY=layout_of((0,'left'),(200,'center'),(600,'right'))


class Places(unittest.TestCase):
 """Real places measured from the game on 11-05."""
 def setUp(self):hd._hits.clear()
 def close(self,a,b):self.assertLessEqual(abs(a-b),2,(a,b))
 def test_anchors(self):
  self.close(hd.to_real_x(884,'right'),1344);self.close(hd.to_real_x(84,'left'),134);self.close(hd.to_real_x(450,'center'),685)
 def test_same_place_differs_by_screen(self):
  self.assertEqual(hd.to_real_point(150,100,INVENTORY),(240,160));self.assertEqual(hd.to_real_point(150,100,GROWTH),(205,160))
 def test_stays_on_the_real_screen(self):
  x,y=hd.to_real_point(896,478,GROWTH);self.assertLess(x,1366);self.assertLess(y,768)
 def test_found_picture_keeps_its_own_anchor(self):
  # The map says centre here, but the picture was found under the left anchor.
  import time
  hd._hits.append((time.monotonic(),140,90,160,110,0.0))
  self.assertEqual(hd.to_real_point(150,100,GROWTH),(240,160))
  self.assertEqual(hd.to_real_point(400,100,GROWTH),(605,160))
 def test_old_hit_expires(self):
  import time
  hd._hits.append((time.monotonic()-hd.HIT_LIFE-1,140,90,160,110,0.0))
  self.assertEqual(hd.to_real_point(150,100,GROWTH),(205,160))
 def test_box_uses_anchor_at_its_middle(self):
  self.assertEqual(hd.real_box((10,20,30,40),GROWTH),(16,32,48,64))
  self.assertEqual(hd.real_box((800,20,30,40),GROWTH)[0],round(800*1.6-69.2))


class Layouts(unittest.TestCase):
 def setUp(self):
  self.addCleanup(lambda:(setattr(hd,'_layouts',None)))
 def test_measures_anchors_from_a_pair(self):
  rng=np.random.default_rng(1)
  real=cv2.GaussianBlur(rng.integers(0,255,(768,1366,3),dtype=np.uint8),(5,5),0)
  frame=hd.make_frame(real,GROWTH)
  built=hd.build_layout(np.asarray(frame),real,'x')
  self.assertEqual(built.rule(50,200),'left');self.assertEqual(built.rule(400,200),'center');self.assertEqual(built.rule(800,200),'right')
 def test_a_lone_cell_is_noise(self):
  grid=np.ones(hd.GRID,np.uint8);grid[5,5]=0
  self.assertEqual(int(hd._tidy(grid)[5,5]),1)
 def test_empty_cells_take_the_nearest_along_the_row(self):
  grid=np.full(hd.GRID,255,np.uint8);grid[3,2]=0;grid[3,50]=2
  out=hd._tidy(grid);self.assertEqual(int(out[3,10]),0);self.assertEqual(int(out[3,45]),2)
 def test_round_trip_through_storage(self):
  source=hd.Layout('a',GROWTH.grid,hd.signature_of(np.random.default_rng(2).integers(0,255,(768,1366,3),dtype=np.uint8)))
  back=hd.load_layout(hd.dump_layout(source))
  self.assertTrue((back.grid==source.grid).all());self.assertGreater(float(np.dot(back.signature,source.signature)),.99)
 def test_unknown_frame_gets_the_field_map(self):
  rng=np.random.default_rng(5);a=rng.integers(0,255,(768,1366,3),dtype=np.uint8)
  known=hd.Layout('panel',INVENTORY.grid,hd.signature_of(a));field=hd.Layout('field',GROWTH.grid,hd.signature_of(a))
  hd._layouts=[known,field]
  self.assertEqual(hd.classify(a).name,'panel')
  self.assertEqual(hd.classify(rng.integers(0,255,(768,1366,3),dtype=np.uint8)).name,'field')
 def test_every_saved_screen_gets_a_map_that_fits_it(self):
  # Two screens can look alike (a tab with little on it). What matters is that their maps agree where it counts.
  if not FRAMES.exists():self.skipTest('saved frames not on this PC')
  hd._layouts=None
  known={l.name:l for l in hd.layouts()};worst=[]
  for path in FRAMES.glob('*_hd.png'):
   name=path.stem[:-3]
   if name==hd.DEFAULT_SCREEN or name not in known:continue
   got=hd.classify(np.asarray(Image.open(path).convert('RGB')))
   agree=float((got.grid==known[name].grid).mean())
   if agree<.9:worst.append((name,got.name,round(agree,2)))
  self.assertEqual(worst,[])


class Frames(unittest.TestCase):
 def frame(self):return hd.make_frame(np.zeros((768,1366,3),np.uint8),GROWTH)
 def test_shape_and_real_copy(self):
  r=np.zeros((768,1366,3),np.uint8);f=hd.make_frame(r,GROWTH)
  self.assertEqual(f.shape,(479,897,3));self.assertIs(f.hi,r);self.assertIs(f.copy().hi,r)
 def test_slice_remembers_its_box_and_flip(self):
  part=self.frame()[20:60,700:800]
  self.assertEqual(part.source,(700,20,100,40));self.assertFalse(part.flip)
  flipped=part[:,:,::-1];self.assertEqual(flipped.source,(700,20,100,40));self.assertTrue(flipped.flip)
 def test_a_slice_of_a_slice_is_where_it_really_is(self):
  self.assertEqual(self.frame()[20:60,700:800][1:3,2:6].source,(702,21,4,2))
 def test_flipping_twice_is_the_original_order(self):
  self.assertFalse(self.frame()[0:9,0:9][:,:,::-1][:,:,::-1].flip)
 def test_arithmetic_is_no_longer_the_screen(self):
  self.assertNotIsInstance(self.frame()[0:9,0:9]*2,hd.HdFrame);self.assertNotIsInstance(self.frame()[0:9,0:9].astype(np.int16)-1,hd.HdFrame)
 def test_a_pixel_is_not_a_box(self):
  self.assertIsNone(self.frame()[5].source if isinstance(self.frame()[5],hd.HdFrame) else None)
 def test_the_map_decides_what_old_code_sees(self):
  r=np.zeros((768,1366,3),np.uint8);x=round(800*1.6-69.2);r[160:176,x:x+16]=255
  self.assertGreater(int(np.asarray(hd.make_frame(r,GROWTH))[105,805].min()),200)
  x=round(150*1.6);r=np.zeros((768,1366,3),np.uint8);r[160:176,x:x+16]=255
  self.assertGreater(int(np.asarray(hd.make_frame(r,INVENTORY))[105,155].min()),200)
  self.assertLess(int(np.asarray(hd.make_frame(r,GROWTH))[105,155].min()),50)
 def test_reader_crop_is_the_same_size_as_before(self):
  self.assertEqual(hd.real_crop(self.frame(),(100,50,40,20)).shape,(80,160,3))
 def test_plain_frames_are_left_alone(self):
  self.assertIsNone(hd.real_crop(np.zeros((479,897,3),np.uint8),(1,1,5,5)))
 def test_enlarging_a_slice_uses_real_pixels(self):
  r=np.zeros((768,1366,3),np.uint8);r[::2,:,:]=255  # lines that scaling down would blur away
  f=hd.make_frame(r,GROWTH);out=cv2.resize(f[20:40,300:340],None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
  self.assertEqual(out.shape,(80,160,3));self.assertGreater(float(out.std()),100)
  self.assertLess(float(cv2.resize(np.asarray(f)[20:40,300:340],None,fx=4,fy=4).std()),60)
 def test_shrinking_stays_on_the_frame(self):
  self.assertEqual(cv2.resize(self.frame()[0:100,0:100],(50,50)).shape,(50,50,3))
 def test_channel_swap_keeps_the_box(self):
  part=cv2.cvtColor(self.frame()[0:9,0:9],cv2.COLOR_RGB2BGR);self.assertTrue(part.flip);self.assertEqual(part.source,(0,0,9,9))
 def test_gray_is_plain(self):
  self.assertEqual(cv2.cvtColor(self.frame()[0:9,0:9],cv2.COLOR_RGB2GRAY).ndim,2)


class Matching(unittest.TestCase):
 def setUp(self):
  hd._hits.clear()
  self.real=np.random.default_rng(3).integers(0,255,(768,1366,3),dtype=np.uint8)
  self.needle=np.random.default_rng(4).integers(0,255,(10,20,3),dtype=np.uint8)
  self.x=round(800*1.6-69.2);self.y=160;self.cut=self.real[self.y:self.y+16,self.x:self.x+32].copy()
  key=hd.key_of(self.needle);hd._index={key:dict(file='x.png',x=self.x,y=self.y,w=32,h=16,rule='right')};hd._images[(key,False)]=self.cut
  self.addCleanup(hd.reload_index);self.addCleanup(hd._hits.clear)
  self.frame=hd.make_frame(self.real,GROWTH)
 def test_exact_box_answers_from_the_real_frame(self):
  answer=cv2.matchTemplate(self.frame[100:110,800:820],self.needle,cv2.TM_CCOEFF_NORMED)
  self.assertEqual(answer.shape,(1,1));self.assertGreater(float(answer[0,0]),.99)
 def test_search_box_gives_best_near_the_logical_place(self):
  answer=cv2.matchTemplate(self.frame[90:130,780:860],self.needle,cv2.TM_CCOEFF_NORMED)
  y,x=np.unravel_index(int(answer.argmax()),answer.shape)
  self.assertGreater(float(answer.max()),.99);self.assertLessEqual(abs(x-20),1);self.assertLessEqual(abs(y-10),1)
 def test_whole_frame_search_finds_it_and_the_click_lands_on_it(self):
  answer=cv2.matchTemplate(self.frame,self.needle,cv2.TM_CCOEFF_NORMED)
  y,x=np.unravel_index(int(answer.argmax()),answer.shape)
  self.assertGreater(float(answer.max()),.99)
  rx,ry=hd.to_real_point(x+10,y+5,INVENTORY)
  self.assertLessEqual(abs(rx-(self.x+16)),2);self.assertLessEqual(abs(ry-(self.y+8)),2)
 def test_several_copies_each_get_a_place(self):
  self.real[self.y+64:self.y+80,self.x:self.x+32]=self.cut
  answer=cv2.matchTemplate(self.frame[90:180,790:840],self.needle,cv2.TM_CCOEFF_NORMED)
  self.assertEqual(len(np.where(answer>=.95)[0]),2)
 def test_not_on_screen_scores_low(self):
  answer=cv2.matchTemplate(self.frame[300:320,800:840],self.needle,cv2.TM_CCOEFF_NORMED)
  self.assertLess(float(answer.max()),.5)
 def test_a_picture_with_no_cut_is_listed(self):
  other=np.ones((8,8,3),np.uint8)
  other[0,0]=9
  self.assertEqual(cv2.matchTemplate(self.frame[0:20,0:20],other,cv2.TM_CCOEFF_NORMED).shape,(13,13));self.assertIn(hd.key_of(other),hd.missing())
 def test_picture_read_the_other_way_round_finds_its_cut(self):
  hd._images[(hd.key_of(self.needle),True)]=self.cut[:,:,::-1].copy()
  answer=cv2.matchTemplate(self.frame[100:110,800:820][:,:,::-1],self.needle[:,:,::-1],cv2.TM_CCOEFF_NORMED)
  self.assertGreater(float(answer.max()),.99)
 def test_other_methods_fall_through(self):
  self.assertEqual(cv2.matchTemplate(self.frame[100:110,800:820].astype(np.float32),self.needle.astype(np.float32),cv2.TM_CCORR).shape,(1,1))


class RealScreen(unittest.TestCase):
 def test_text_reads_right_from_the_real_frame(self):
  path=LIVE/'r_shop.png'
  if not path.exists():self.skipTest('saved frame not on this PC')
  from tools.ocr_support import get_paddle_engine
  engine=get_paddle_engine(bootstrap.A,language='korean')
  f=hd.make_frame(np.asarray(Image.open(path).convert('RGB')),layout_of((0,'left')))
  crop=cv2.copyMakeBorder(hd.real_crop(f,(44,61,153,370)),32,32,32,32,cv2.BORDER_CONSTANT)
  text=' '.join(t for page in engine.predict(crop) for t in page['rec_texts'])
  self.assertIn('절명 도술 강화 요령서',text);self.assertIn('(0/50)',text);self.assertIn('영웅',text)


if __name__=='__main__':unittest.main()
