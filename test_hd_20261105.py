"""1366x768 mapping and matching, on arrays and frames saved from the game. Never a game test."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import bootstrap,json,unittest
from unittest.mock import patch
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


class Pins(unittest.TestCase):
 def setUp(self):hd._pins.clear();hd._hits.clear()
 def tearDown(self):hd._pins.clear()
 def test_a_word_found_elsewhere_is_where_the_click_goes(self):
  import time
  hd._pins.append((time.monotonic(),495,310,522,326,778,528))
  self.assertEqual(hd.to_real_point(508,318,GROWTH),(778,528))
  self.assertNotEqual(hd.to_real_point(100,100,GROWTH),(778,528))
 def test_an_old_one_expires(self):
  import time
  hd._pins.append((time.monotonic()-hd.HIT_LIFE-1,495,310,522,326,778,528))
  self.assertNotEqual(hd.to_real_point(508,318,GROWTH),(778,528))


class Auto(unittest.TestCase):
 def frame(self,colour):
  r=np.zeros((768,1366,3),np.uint8);r[705:725,1198:1222]=colour
  return r
 def test_gold_is_on(self):self.assertEqual(hd.auto_state(self.frame((230,170,40))),'gold')
 def test_white_is_off(self):self.assertEqual(hd.auto_state(self.frame((240,240,240))),'white')
 def test_nothing_there(self):self.assertIsNone(hd.auto_state(np.zeros((768,1366,3),np.uint8)))
 def test_thin_white_is_paused(self):
  r=np.zeros((768,1366,3),np.uint8);r[705:725,1205:1207]=240;r[705:725,1212:1214]=240
  self.assertEqual(hd.auto_state(r),'paused')
 def test_answers_only_for_its_own_state_and_place(self):
  f=hd.make_frame(self.frame((230,170,40)),GROWTH);needle=np.zeros((13,12,3),np.uint8)
  yes=hd.match_state(f[442:455,794:806],needle,(794,442,12,13),f.hi,'gold')
  self.assertGreater(float(yes.max()),.9)
  self.assertLess(float(hd.match_state(f[442:455,794:806],needle,(794,442,12,13),f.hi,'white').max()),0)
  self.assertLess(float(hd.match_state(f[441:457,770:786],needle,(770,441,16,16),f.hi,'gold').max()),0)


class SameAnswersFaster(unittest.TestCase):
 def small(self):return np.random.default_rng(7).integers(0,255,(479,854,3),dtype=np.uint8)
 def test_composing_gives_the_same_pixels_as_indexing(self):
  small=self.small();rows=np.arange(hd.LOGICAL[1])[:,None]
  grids=[GROWTH,INVENTORY,hd._PLAIN,*hd.layouts()]
  for layout in grids:self.assertTrue(np.array_equal(layout.compose(small),small[rows,layout.picks()]),layout.name)
 def test_a_match_hashes_its_picture_once(self):
  rng=np.random.default_rng(3);real=cv2.GaussianBlur(rng.integers(0,255,(768,1366,3),dtype=np.uint8),(3,3),0)
  needle=rng.integers(0,255,(10,20,3),dtype=np.uint8);key=hd.key_of(needle)
  hd._index={key:dict(file='x.png',x=100,y=100,w=32,h=16,rule='left')};hd._images[(key,False)]=real[160:176,160:192].copy()
  self.addCleanup(hd.reload_index);self.addCleanup(hd._hits.clear)
  frame=hd.make_frame(real,GROWTH)[90:130,80:140]
  with patch.object(hd,'key_of',wraps=hd.key_of) as hashed,patch.object(hd,'word_table',lambda:{}):
   self.assertGreater(float(cv2.matchTemplate(frame,needle,cv2.TM_CCOEFF_NORMED).max()),.9)
  self.assertEqual(hashed.call_count,1)
 def test_tables_are_whole_before_anyone_sees_them(self):
  self.addCleanup(hd.reload_index)
  seen=[];plain=json.loads
  def watch(line):
   seen.append((hd._index,hd._words));return plain(line)
  hd._index=None;hd._words=None
  with patch.object(json,'loads',watch):hd.index();hd.word_table()
  self.assertEqual(seen[0],(None,None));self.assertTrue(all(i is None or len(i)==len(hd._index) for i,_ in seen));self.assertTrue(all(w is None for _,w in seen))
 def test_reloading_forgets_the_words_too(self):
  hd._words={'x':{}};hd.reload_index();self.assertNotIn('x',hd.word_table())


class CaptureBytes(unittest.TestCase):
 """Fake window calls. Says nothing about the game's real capture."""
 TARGET={'client_size':list(hd.REAL),'capture':{'layers':[]}}
 def run_grab(self,*,layers=(),rect=(0,0,1366,768),after=None,image=None):
  import win32gui,mdt_owned_capture as owned
  image=np.zeros((768,1366,3),np.uint8) if image is None else image
  calls=[];states=[rect,after or rect]
  layer_calls=iter([list(layers),list(layers)])
  original=lambda hwnd,target,printwindow=None:calls.append('original') or 'original'
  with patch.dict(hd._state,{'capture':original}),patch.object(win32gui,'ClientToScreen',lambda h,p:(5,5)),\
       patch.object(win32gui,'GetClientRect',lambda h:states.pop(0)),patch.object(owned,'_layers',lambda h,p:next(layer_calls)):
   return hd._grab(1,self.TARGET,lambda h:image),calls
 def test_nothing_over_it_comes_back_as_is(self):
  image=np.full((768,1366,3),7,np.uint8);got,calls=self.run_grab(image=image)
  self.assertIs(got,image);self.assertEqual(calls,[])
 def test_a_layer_goes_the_original_way(self):
  got,calls=self.run_grab(layers=[(9,0)]);self.assertEqual((got,calls),('original',['original']))
 def test_a_wrong_size_goes_the_original_way(self):
  got,calls=self.run_grab(rect=(0,0,800,600));self.assertEqual((got,calls),('original',['original']))
 def test_a_window_that_moved_during_the_capture_is_refused(self):
  with self.assertRaises(RuntimeError):self.run_grab(after=(0,0,1366,700))
 def test_a_short_picture_is_refused(self):
  with self.assertRaises(RuntimeError):self.run_grab(image=np.zeros((700,1366,3),np.uint8))
 def test_a_minimized_game_is_left_alone(self):
  import types,win32gui
  gui=types.SimpleNamespace(session=types.SimpleNamespace(snapshot=lambda:{'status':'stopped'}),game_window=types.SimpleNamespace(hwnd=5))
  with patch.object(hd,'_is_game',lambda h:True),patch.object(hd,'ensure_size') as size,patch.object(hd,'place_program'),patch.object(win32gui,'IsIconic',lambda h:True):
   hd.keep_size(gui)
  size.assert_not_called()
  with patch.object(hd,'_is_game',lambda h:True),patch.object(hd,'ensure_size') as size,patch.object(hd,'place_program'),patch.object(win32gui,'IsIconic',lambda h:False):
   hd.keep_size(gui)
  size.assert_called_once()


class Reading(unittest.TestCase):
 """A stand-in for the engine. Says nothing about what it really reads."""
 def setUp(self):
  import owner_text
  self.text=owner_text;self.calls=0;owner_text._areas.clear();self.addCleanup(owner_text._areas.clear)
  test=self
  class Engine:
   def predict(self,source):
    test.calls+=1
    return [dict(rec_texts=['하나','둘'],rec_scores=[.9,.6],rec_polys=[[[16,16],[36,16],[36,26],[16,26]],[[16,36],[56,36],[56,46],[16,46]]])]
  engine=patch.object(owner_text,'_engine',lambda r,l:Engine());engine.start();self.addCleanup(engine.stop)
 def area(self,fill=1):return np.full((30,30,3),fill,np.uint8)
 def test_the_same_pixels_are_read_once_whatever_was_asked(self):
  a=self.text.read_area(None,self.area(),minimum=.5);b=self.text.read_area(None,self.area(),minimum=.8);c=self.text.read_area(None,self.area(),left=100,top=10)
  self.assertEqual(self.calls,1);self.assertEqual([r['text'] for r in a],['하나','둘']);self.assertEqual([r['text'] for r in b],['하나'])
  self.assertEqual((a[0]['rx'],a[0]['ry']),(5,2));self.assertEqual((c[0]['rx'],c[0]['ry']),(105,12));self.assertEqual(c[0]['bounds'],(100,10,110,15))
 def test_what_comes_back_can_be_changed_freely(self):
  self.text.read_area(None,self.area())[0]['x']=1;self.assertNotIn('x',self.text.read_area(None,self.area())[0])
 def test_other_pixels_or_scale_are_read_again(self):
  self.text.read_area(None,self.area());self.text.read_area(None,self.area(2));self.text.read_area(None,self.area(),scale=3);self.text.read_area(None,self.area(),bright=True)
  self.assertEqual(self.calls,4)
 def test_a_reading_in_use_outlives_a_moving_world(self):
  self.text.read_area(None,self.area())
  for fill in range(2,2+self.text.AREAS_KEPT*2):
   self.text.read_area(None,self.area(fill));self.text.read_area(None,self.area())
  self.assertEqual(self.calls,1+self.text.AREAS_KEPT*2);self.assertLessEqual(len(self.text._areas),self.text.AREAS_KEPT)
 def test_a_menu_named_by_its_title_needs_no_more_reading(self):
  import owner_start_menu as menu
  frame=hd.make_frame(np.zeros((768,1366,3),np.uint8),GROWTH)
  with patch.object(menu,'title_menu',lambda f:'성장'),patch.object(menu,'word_window',side_effect=AssertionError),patch.object(menu,'idle_training',side_effect=AssertionError):
   self.assertEqual(menu.kind(frame),'성장')
  with patch.object(menu,'title_menu',lambda f:None),patch.object(menu,'word_window',lambda f:('이벤트',(1,1))),patch.object(menu,'idle_training',side_effect=AssertionError):
   self.assertEqual(menu.kind(frame),'이벤트')
  with patch.object(menu,'title_menu',lambda f:None),patch.object(menu,'word_window',lambda f:None),patch.object(menu,'idle_training',lambda f:True):
   self.assertEqual(menu.kind(frame),'영기 수련')
  with patch.object(menu,'title_menu',lambda f:None),patch.object(menu,'word_window',lambda f:None),patch.object(menu,'idle_training',lambda f:False):
   self.assertIsNone(menu.kind(frame))


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
