"""The four real failures of 11-05 22:19 to 22:29 and the one shop visit, with fake input and fake word reads. Never a game test."""
from pathlib import Path
import json,sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import owner_hd as hd
import owner_shop_runtime_candidate as shop
import owner_skill_growth_candidate as growth
import owner_growth_words as words
import owner_blessing_native_candidate as blessing
import owner_membership,owner_progression,owner_quest_preflight,owner_skill_ui
from owner_gear_step_guard_candidate import Guard
from owner_gear_decision_candidate import Observation
from owner_shop_settings_candidate import ShopSettingsStore
from owner_shop_transaction_candidate import Hold
from owner_skill_goal import Pending

ITEM='파멸 도술 강화 요령서';OTHER='영웅 장비 강화 비법서'


def real_frame(fill=0):
 frame=np.full((479,897,3),fill,np.uint8).view(hd.HdFrame);frame.hi=np.full((768,1366,3),fill,np.uint8);frame.layout=hd._PLAIN
 return frame


def row(text,ry=300,rx=130,score=.98,x=60):
 return dict(text=text,score=score,rx=rx,ry=ry,x=round(rx/1.6),y=round(ry/1.6),bounds=(x,ry-9,x+150,ry+9))


class Cart(unittest.TestCase):
 """'SkillUI' object has no attribute 'last_text_frame', after 상점 구매 · 파멸 1개 · 합계 50000."""
 def test_total_leaves_the_frame_it_read(self):
  ui=NS(frame=real_frame,context=NS(wait=lambda *a:None),adapter=NS(project=NS(root='r')))
  with patch.object(shop,'_total_values',return_value=[50000]):self.assertEqual(shop._total(ui),50000)
  self.assertIsNotNone(ui.last_text_frame.hi);self.assertLessEqual(time.monotonic()-ui.last_text_tick,3)
 def test_frames_that_disagree_give_no_total(self):
  ui=NS(frame=real_frame,context=NS(wait=lambda *a:None),adapter=NS(project=NS(root='r')))
  with patch.object(shop,'_total_values',side_effect=[[50000],[5000]]*6),self.assertRaises(Hold):shop._total(ui)
 def test_real_cart_proof_is_its_label_and_this_total(self):
  frame=real_frame()
  with patch.object(shop,'_cart_bar',return_value=True),patch.object(shop,'_total_values',return_value=[50000]):
   self.assertTrue(shop._same_cart(frame,frame,50000));self.assertFalse(shop._same_cart(frame,frame,100000));self.assertFalse(shop._same_cart(frame,frame))
  with patch.object(shop,'_cart_bar',return_value=False),patch.object(shop,'_total_values',return_value=[50000]):self.assertFalse(shop._same_cart(frame,frame,50000))
  with patch.object(shop,'_cart_bar',return_value=True),patch.object(shop,'_total_values',return_value=[]):self.assertFalse(shop._same_cart(frame,frame,50000))


class RowProof(unittest.TestCase):
 """상점 판독 확인 필요 · 도술 입력 직전 화면 변경: a see-through row's picture never holds still."""
 def check(self,rows,title=True,popup=False,ry=300):
  with patch.object(owner_membership,'shop_title',return_value=title),patch.object(shop,'_quantity_shown',return_value=popup),patch('owner_text.read',return_value=rows):
   return shop.row_on_screen(real_frame(),ITEM,ry)
 def test_the_name_where_it_was_read(self):self.assertTrue(self.check([row(ITEM,303)]))
 def test_a_row_that_glided_away_is_not_it(self):self.assertFalse(self.check([row(ITEM,330)]))
 def test_another_item_is_not_it(self):self.assertFalse(self.check([row(OTHER,300)]))
 def test_nothing_read_is_no_proof(self):self.assertFalse(self.check([]))
 def test_not_the_shop_or_a_popup_over_it(self):
  self.assertFalse(self.check([row(ITEM)],title=False));self.assertFalse(self.check([row(ITEM)],popup=True))


class WordButton(unittest.TestCase):
 def ui(self):
  ui=owner_skill_ui.SkillUI.__new__(owner_skill_ui.SkillUI);ui.adapter=NS(project=NS(root='r'));ui.context=NS(checkpoint=lambda:None,wait=lambda *a:None)
  ui.service=NS(check=lambda:None,capture=real_frame,click_hit=lambda hit:self.clicks.append(hit));self.clicks=[]
  return ui
 def press(self,second):
  reads=iter(([row('구매',440,760)],[row('구매',440,760)],second))
  with patch('owner_text.read',side_effect=lambda *a,**k:next(reads)):return self.ui().click_word('구매',(730,430,65,40),lambda f:True)
 def test_the_word_still_there_is_pressed(self):
  self.press([row('구매',441,761)]);self.assertEqual(len(self.clicks),1)
 def test_a_word_gone_or_moved_is_not_pressed(self):
  for second in ([],[row('구매',470,760)],[row('구매',440,760),row('구매',440,860)]):
   self.clicks=[]
   with self.assertRaises(Pending):self.press(second)
   self.assertEqual(self.clicks,[])


class SkillWords(unittest.TestCase):
 """도술 원본 글자·대상 변경: an unchanged name's mask never matched exactly on the real screen."""
 BOX=(710,100,60,16)
 def reader(self,texts):
  texts=iter(texts)
  return patch('owner_text.read_area',side_effect=lambda *a,**k:[dict(row(next(texts)),rx=1000,ry=170)])
 def source(self):
  frame=real_frame(120);frame[100:116,710:770]=np.random.default_rng(1).integers(0,255,(16,60,3),dtype=np.uint8)
  x,y,w,h=self.BOX;return frame[y:y+h,x:x+w].copy()
 def frame(self):
  frame=real_frame(60);frame[100:116,710:770]=np.random.default_rng(2).integers(0,255,(16,60,3),dtype=np.uint8);return frame
 def test_same_words_over_another_world(self):
  with self.reader(['파멸+23','파멸+23']):self.assertTrue(growth._same_pixels(self.frame(),self.BOX,self.source(),'text'))
 def test_a_changed_digit_is_a_change(self):
  for mode in ('text','gold'):
   with self.reader(['파멸+24','파멸+23']):self.assertFalse(growth._same_pixels(self.frame(),self.BOX,self.source(),mode))
 def test_words_elsewhere_are_a_change(self):
  answers=iter(([row('파멸+23',rx=1000,ry=170)],[row('파멸+23',rx=1000,ry=190)]))
  with patch('owner_text.read_area',side_effect=lambda *a,**k:next(answers)):self.assertFalse(growth._same_pixels(self.frame(),self.BOX,self.source(),'text'))
 def test_nothing_read_is_no_proof(self):
  with patch('owner_text.read_area',return_value=[]):self.assertFalse(growth._same_pixels(self.frame(),self.BOX,self.source(),'text'))
 def test_a_frame_with_no_real_pixels_keeps_the_mask(self):
  plain=np.zeros((479,897,3),np.uint8);plain[100:116,710:770]=np.random.default_rng(2).integers(0,255,(16,60,3),dtype=np.uint8)
  with patch('owner_text.read_area',side_effect=AssertionError('no reading')):
   self.assertTrue(growth._same_pixels(plain,self.BOX,plain[100:116,710:770].copy(),'text'))
 def test_proof_lives_longer_only_on_the_real_screen(self):
  source=self.source();old=time.monotonic()-5
  with self.reader(['파멸+23','파멸+23']):self.assertTrue(growth._same(self.frame(),(self.BOX,source,old,'text')))
  self.assertFalse(growth._same(self.frame(),(self.BOX,source,time.monotonic()-13,'text')))
  plain=np.zeros((479,897,3),np.uint8);self.assertFalse(growth._same(plain,(self.BOX,plain[100:116,710:770].copy(),old,'exact')))
 def test_refresh_passes_a_list_that_did_not_change(self):
  frames=[self.frame(),self.frame()];now=time.monotonic()-5
  ui=NS(context=NS(checkpoint=lambda:None,wait=lambda *a:None),frame=self.frame)
  proof=(self.BOX,self.source(),now,'text')
  with patch('owner_text.read_area',side_effect=lambda *a,**k:[dict(row('파멸+23'),rx=1000,ry=170)]):
   fresh=growth.refresh_evidence(ui,lambda:True,frames,[now,now+.12],[proof],lambda f:True)
  self.assertEqual(fresh[0][3],'text')
  # The next pair says another number than the words they are compared with.
  changed=real_frame(200);changed[100:116,710:770]=np.random.default_rng(3).integers(0,255,(16,60,3),dtype=np.uint8);ui.frame=lambda:changed
  def said(frame,box):return ('파멸+99' if int(np.asarray(frame.hi)[0,0,0])==200 else '파멸+23',1000,170)
  with patch.object(growth,'_real_words',side_effect=said),self.assertRaises(Pending):
   growth.refresh_evidence(ui,lambda:True,frames,[now,now+.12],[proof],lambda f:True)


class FakeStore:
 def __init__(self):self.record=None;self.sent=False
 def pending(self):return self.record
 def begin(self,record):self.record=dict(record,phase='prepared')
 def mark_sent(self):self.sent=True
 def abort_prepared(self,why):
  if not self.sent:self.record=None


class Blessing(unittest.TestCase):
 """나비3 · 39→40 · 입력 가능=True, then 가호 새 화면 재검증 시간 초과: one frame takes up to 2.8 s to read."""
 STATE={'slot':3,'level':39,'active':True,'button':'b','opening':True,'materials':'x','identity':'blessing-words:나비3','cost':40000}
 def observer(self,seconds_per_read,states=None):
  self.now=100.
  context=NS(checkpoint=lambda:None,wait=lambda s:setattr(self,'now',self.now+s))
  service=NS(check=lambda:None,capture=real_frame)
  o=blessing.BlessingObserver.__new__(blessing.BlessingObserver)
  o.service=service;o.context=context;o.identity='me';o.clock=lambda:self.now;o.sequence=0;o.last_state=None;o._fresh_read_view=None
  o.item='icon';o.root='r';o.row={'index':1};o.rows=[];o.last_reason=''
  states=iter(states) if states else None
  def word_state(frame):
   self.now+=seconds_per_read
   return dict(next(states)) if states else dict(self.STATE)
  o._word_state=word_state
  return o
 def guard(self,o):
  return Guard(o.context,FakeStore(),o.read_pair,clock=lambda:self.now,fresh_seconds=blessing.proof_seconds(real_frame()))
 def test_a_slow_read_reaches_the_press_through_all_its_checks(self):
  o=self.observer(2.8);pressed=[]
  def press(latest,mark):
   self.assertTrue(o.verify_final(real_frame(),latest,'enhance'));mark();pressed.append(latest)
  with patch('owner_growth_current.observe_value'):status=self.guard(o).run_one('enhance',{'3번':{'enabled':True,'enhance':50}},press)
  self.assertEqual(status,'pending_confirmation');self.assertEqual(len(pressed),1)
 def test_two_frames_that_differ_press_nothing(self):
  o=self.observer(.5,[self.STATE,dict(self.STATE,level=40)]*8)
  status=self.guard(o).run_one('enhance',{'3번':{'enabled':True,'enhance':50}},lambda *a:self.fail('pressed'))
  self.assertEqual(status,'hold_screen_unverified')
 def test_a_change_at_the_last_read_presses_nothing(self):
  o=self.observer(.5,[self.STATE,self.STATE,dict(self.STATE,level=40),dict(self.STATE,level=40)])
  with patch('owner_growth_current.observe_value'):status=self.guard(o).run_one('enhance',{'3번':{'enabled':True,'enhance':50}},lambda *a:self.fail('pressed'))
  self.assertEqual(status,'hold_boundary_preinput')
 def test_a_last_look_on_a_new_frame_that_differs_stops_the_press(self):
  o=self.observer(.5);latest=None
  with patch('owner_growth_current.observe_value'):latest=o.read_pair()
  latest=dict(latest,button_name='b',opening=True)
  o._word_state=lambda frame:dict(self.STATE,cost=99)
  self.assertFalse(o.verify_final(real_frame(),latest,'enhance'))
 def test_older_than_the_real_limit_still_holds(self):
  o=self.observer(7.)
  self.assertFalse(o.read_pair()['screen_proof']);self.assertEqual(o.last_reason,'가호 새 화면 재검증 시간 초과')
 def test_a_frame_with_no_real_pixels_keeps_1_5_seconds(self):
  self.assertEqual(blessing.proof_seconds(np.zeros((479,897,3),np.uint8)),1.5)
  self.assertEqual(Guard(NS(checkpoint=lambda:None),None,None).fresh_seconds,1.5)


class BlessingTitle(unittest.TestCase):
 def read(self,answers):
  frame=real_frame();seen=[]
  def fake(root,f,box,scale=None,**k):
   seen.append(scale);return answers.pop(0)
  with patch('owner_text.read',side_effect=fake):return words._any_size('r',frame,words.BLESSING_TITLE,words.blessing_title,'제목'),seen
 def test_the_other_size_reads_what_this_one_spoiled(self):
  found,seen=self.read([[row('토끼가호장식1',score=.6)],[row('토끼가호장식1')]])
  self.assertEqual((found['slot'],seen),(1,[3,2]))
 def test_the_digit_is_not_guessed_at_either_size(self):
  self.assertIsNone(self.read([[row('토끼가호장식]')],[row('토끼가호장식7')]])[0])
 def test_the_floor_holds_at_either_size(self):
  self.assertIsNone(self.read([[row('토끼가호장식1',score=.6)],[row('토끼가호장식1',score=.7)]])[0])


class QuoteReads(unittest.TestCase):
 LIST=[row(OTHER,266,x=76),row('15,000',287,x=97),row('도사 주간 한정:(3/50)',308,x=76)]
 def ui(self):
  frame=real_frame();return NS(frame=lambda:frame,context=NS(wait=lambda *a:None),adapter=NS(project=NS(root='r')))
 def test_a_name_not_there_takes_one_read(self):
  ui=self.ui()
  with patch('owner_text.read',return_value=self.LIST) as read:self.assertIsNone(shop._real_quote(ui,ITEM))
  self.assertEqual(read.call_count,1)
 def test_a_row_there_gets_its_second_frame_from_its_band(self):
  ui=self.ui()
  with patch('owner_text.read',return_value=self.LIST) as read:quote=shop._real_quote(ui,OTHER)
  self.assertEqual((quote['unit_price'],quote['used'],quote['remaining'],read.call_count),(15000,3,47,2))
  self.assertLess(read.call_args_list[1][0][2][3],200)
 def test_a_second_frame_that_differs_is_read_again(self):
  ui=self.ui();other=[row(OTHER,266,x=76),row('15,000',287,x=97),row('도사 주간 한정:(4/50)',308,x=76)]
  with patch('owner_text.read',side_effect=[self.LIST,other]),self.assertRaises(Pending):shop._real_quote(ui,OTHER)
 def test_no_real_pixels_holds(self):
  ui=self.ui();ui.frame=lambda:np.zeros((479,897,3),np.uint8)
  with self.assertRaises(Hold):shop._real_quote(ui,OTHER)


class ListWalk(unittest.TestCase):
 """Pages of names; a drag moves one page down, or to the top when it pulls down twice."""
 PAGES=[['1단 체력 회복 물약',OTHER],['전설 장비 강화 비법서','강타 도술 강화 요령서'],[ITEM,'천요석']]
 def go(self,item,start=0,ui=None):
  self.reads=0;self.page=start
  def read(ui,want):
   self.reads+=1;ui._owner_shop_last_page=list(self.PAGES[self.page])
   return {'name':want} if want in self.PAGES[self.page] else None
  def drag(start_at,end,proof,hold=0):
   self.page=max(0,self.page-1) if end[1]>start_at[1] else min(len(self.PAGES)-1,self.page+1)
  ui=ui or NS(context=NS(checkpoint=lambda:None,wait=lambda *a:None))
  ui.drag=drag
  with patch.object(shop,'_paired',return_value=True),patch.object(shop,'_total',return_value=0),patch.object(shop,'_read_quote',side_effect=read):
   return shop._find_quote(ui,item),ui
 def test_goes_on_down_from_the_top(self):
  found,_=self.go(ITEM);self.assertEqual(found['name'],ITEM);self.assertEqual(self.reads,3)
 def test_an_item_already_passed_goes_back_to_the_top(self):
  _,ui=self.go(ITEM)
  found,_=self.go(OTHER,start=2,ui=ui);self.assertEqual(found['name'],OTHER);self.assertLessEqual(self.reads,2+1)
 def test_a_list_opened_lower_finds_what_was_above(self):
  self.assertEqual(self.go(OTHER,start=1)[0]['name'],OTHER)
 def test_an_item_not_sold_ends_at_the_bottom_once(self):
  with self.assertRaises(Hold):self.go('헌신 도술 강화 요령서')
  self.assertLessEqual(self.reads,5)


class Visit(unittest.TestCase):
 """Six items took five minutes: the bag read and the shop trip came again for each."""
 ITEMS=('강타 도술 강화 요령서','파멸 도술 강화 요령서','영웅 장비 강화 비법서')
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'s','character_name':'c'}),encoding='utf8')
  profile=shop.configured_identity(self.root);store=ShopSettingsStore(self.root,profile);doc=store.read_document()
  for r in doc['items']:
   if r['shop']=='remote' and r['name'] in self.ITEMS:r.update(enabled=True,quantity=1)
  store.write(doc['items'],100000)
  self.adapter=NS(project=NS(root=self.root));self.context=NS(checkpoint=lambda:None,wait=lambda *a:None,stop=NS(is_set=lambda:False))
  self.progress=NS(character='hash',observed=0.);self.events=[];self.adapter._owner_shop_entered=False
 def run_it(self,quote,ui=None):
  ui=ui or NS(normal=lambda:True,context=self.context)
  def power(*a):
   self.events.append('power');self.progress.observed=time.monotonic()
   self.adapter._owner_progression_observation=(self.context,self.progress.observed,'hash');return True
  def opened(*a):self.events.append('open');return ui
  def closed(*a):
   if self.adapter._owner_shop_entered:self.events.append('close')
   self.adapter._owner_shop_entered=False
  import owner_schedule_priority
  with patch.object(owner_membership,'paid',return_value=True),patch.object(owner_membership,'open_remote',side_effect=opened),patch.object(owner_skill_ui,'SkillUI',return_value=ui),\
    patch.object(owner_quest_preflight,'read_power',side_effect=power),patch.object(owner_progression,'state',return_value=self.progress),\
    patch.object(shop,'_find_quote',side_effect=quote),patch.object(shop,'_close_known_shop',side_effect=closed),patch.object(owner_schedule_priority,'hold_reason',return_value=None):
   return shop.dispatch_configured(self.adapter,self.context,None)
 def empty(self,ui,item):return {'name':item,'click_y':111,'row_proof':lambda f:True,'unit_price':15000,'remaining':0,'used':10,'limit':10,'kind':'observed_weekly_quote'}
 def test_all_items_in_one_trip(self):
  self.assertEqual(self.run_it(self.empty)['status'],'processed')
  self.assertEqual(self.events,['power','open','close'])
 def test_a_hold_leaves_the_shop_and_the_next_comes_back_without_a_new_bag_read(self):
  calls=[]
  def quote(ui,item):
   calls.append(item)
   if len(calls)==1:raise Hold('x')
   return self.empty(ui,item)
  outcome=self.run_it(quote)
  self.assertEqual(outcome['status'],'partial');self.assertEqual(self.events,['power','open','close','open','close'])
 def test_a_stale_character_read_leaves_reads_and_returns(self):
  calls=[]
  def quote(ui,item):
   calls.append(item)
   if len(calls)==1:self.progress.observed=time.monotonic()-shop.CHARACTER_READ_SECONDS-1;self.adapter._owner_progression_observation=(self.context,self.progress.observed,'hash')
   return self.empty(ui,item)
  self.run_it(quote)
  self.assertEqual(self.events,['power','open','close','power','open','close'])
 def test_a_read_from_another_run_counts_for_nothing(self):
  self.progress.observed=time.monotonic();self.adapter._owner_progression_observation=(object(),self.progress.observed,'hash')
  self.assertFalse(shop.character_read_recently(self.adapter,self.context))
 def test_stop_before_the_next_item_sends_nothing_more(self):
  class Stop(BaseException):pass
  calls=[]
  def checkpoint():
   calls.append(1)
   if len(calls)>1:raise Stop()
  self.context.checkpoint=checkpoint
  with self.assertRaises(Stop):self.run_it(self.empty)
  self.assertEqual(self.events[-1],'close');self.assertIsNone(self.adapter._owner_shop_visit)


class WornSlots(unittest.TestCase):
 def test_only_stale_slots_are_opened_and_none_opens_nothing(self):
  import owner_worn_stats as w
  with patch('owner_progression.state',side_effect=AssertionError('opened')):
   self.assertIsNone(w.inspect_equipped(NS(),NS(),None,only=[]))
 def test_numbers_use_the_places_given(self):
  import owner_worn_stats as w
  places={'enhance':(690,300,45,26),'awaken':(690,350,45,26)}
  with patch('owner_text.read_area',return_value=[dict(row('50'),text='50')]) as reader,patch.object(w,'real_table',side_effect=AssertionError('table read again')):
   self.assertEqual(w.real_read(np.zeros((768,1366,3),np.uint8),places),{'enhance':50,'awaken':50})
  self.assertEqual(reader.call_count,2)


class Potions(unittest.TestCase):
 def test_over_the_limit_with_the_label_is_full_at_any_tier(self):
  import owner_remote_potion_limit_candidate as limits
  frame=real_frame();ui=NS(frame=lambda:frame,context=NS(wait=lambda *a:None))
  rows=[row('2단 체력 회복 물약',193),row('구매불가',212),row('구매 가능 796/651',234)]
  with patch('owner_text.read',return_value=rows),patch('owner_text.shows_title',return_value=True):
   self.assertEqual(limits.observed_full(ui,'2단물약'),796)
  rows=[row('2단 체력 회복 물약',193),row('구매 가능 100/651',234)]
  with patch('owner_text.read',return_value=rows),patch('owner_text.shows_title',return_value=True):
   self.assertIsNone(limits.observed_full(ui,'2단물약'))


class SceneSamples(unittest.TestCase):
 def test_the_saved_sample_has_no_real_screen(self):
  import owner_scene_archive as a,threading
  gui=NS(project=NS(root=Path(tempfile.mkdtemp(dir=str(Path(__file__).resolve().parent/'test_scratch')))),session=NS(snapshot=lambda:{'status':'running'}))
  archive=a.SceneArchive.__new__(a.SceneArchive)
  import queue,collections
  archive.ending=threading.Event();archive.stats_lock=threading.Lock();archive.next_sample=0.;archive.last_forced=-1e30;archive.clock=time.monotonic
  archive.pending=queue.Queue(maxsize=8);archive.recent=collections.deque();archive.activity_epoch=0;archive.gui=gui
  archive.stats={'storage_full':False,'dropped_busy':0,'offered':0,'errors':0,'last_error':None}
  context=NS(stop=threading.Event(),pause=threading.Event())
  self.assertTrue(archive.offer(real_frame(),NS(mode='m'),context))
  self.assertIsNone(getattr(archive.pending.get_nowait()[0],'hi',None))


if __name__=='__main__':unittest.main()
