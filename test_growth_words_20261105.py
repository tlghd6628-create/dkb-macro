"""Growth screens by words on the 1366x768 frame (11-05), from rows the reader really gave. Fake input; never a game test."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os,sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_hd as hd
import owner_growth_words as w
from project_adapter import market_inventory as native


def row(text,x=0,y=0,score=.98,wide=40):return dict(text=text,score=score,rx=x,ry=y,x=round(x/1.6),y=round(y/1.6),bounds=(x-wide//2,y-9,x+wide//2,y+9))


def real_frame(gold=True):
 big=np.zeros((768,1366,3),np.uint8)
 if gold:big[700:742,560:795]=(253,230,148)
 else:big[700:742,560:795]=(125,114,71)
 frame=np.zeros((479,897,3),np.uint8).view(hd.HdFrame);frame.hi=big;frame.layout=hd._PLAIN
 return frame


# These tests are about reading the panel. The coin floor has its own, and one case below.
import owner_coin_reserve
owner_coin_reserve.can_spend=lambda *a,**k:True

class Title(unittest.TestCase):
 def test_title_gives_name_and_slot(self):
  self.assertEqual(w.blessing_title([row('나비가호장식3')])['identity'],'blessing-words:나비3')
 def test_split_title_and_digit_read_twice(self):
  found=w.blessing_title([row('토끼가호',500),row('장식1',600),row('1(귀속)',650)])
  self.assertEqual((found['name'],found['slot']),('토끼',1))
 def test_a_letter_off_in_the_name_still_names_one(self):
  self.assertEqual(w.blessing_title([row('토까 가호 장식1')])['name'],'토끼')
  self.assertEqual(w.blessing_title([row('나비가혹 장식3')])['name'],'나비')
 def test_slot_digit_is_never_guessed(self):
  self.assertIsNone(w.blessing_title([row('토끼가호장식]')]))
  self.assertIsNone(w.blessing_title([row('토끼가호장식7')]))
 def test_a_name_that_is_none_of_them(self):
  self.assertIsNone(w.blessing_title([row('호랑이가호장식1')]))
 def test_low_score_is_no_title(self):
  self.assertIsNone(w.blessing_title([row('토끼가호장식1',score=.6)]))


class Level(unittest.TestCase):
 def test_both_sides(self):self.assertEqual(w.level_pair([row('-35')],[row('36+')]),(35,36))
 def test_opening_row_has_no_signs(self):self.assertEqual(w.level_pair([row('39')],[row('40')]),(39,40))
 def test_redrawing_number_is_no_level(self):self.assertIsNone(w.level_pair([row('3')],[row('38+')]))
 def test_single_digit_alone_is_no_level(self):self.assertIsNone(w.level_pair([row('3')],[]))
 def test_top_level_has_no_next(self):self.assertEqual(w.level_pair([row('50')],[]),(50,None))
 def test_low_score(self):self.assertIsNone(w.level_pair([row('35',score=.5)],[row('36')]))


class Counts(unittest.TestCase):
 def test_owned_and_needed(self):self.assertEqual(w.counts([row('85,179/2,100'),row('976/3')]),[(85179,2100),(976,3)])
 def test_short_or_unread(self):
  self.assertFalse(w.enough([(2,5)]));self.assertIsNone(w.enough([]));self.assertTrue(w.enough([(5,5)]))
 def test_price_keeps_its_comma(self):
  self.assertEqual(w.pill_price([row('강화'),row('40,000')]),40000)
  self.assertIsNone(w.pill_price([row('강화'),row('5,00')]))
 def test_close_spelling_is_no_button(self):
  self.assertIsNone(w.only_word([row('강회')],('강화','개방')))
  self.assertIsNone(w.only_word([row('강화'),row('개방')],('강화','개방')))


class Zones:
 """What the reader gives for each zone of the blessing panel."""
 def __init__(self,title='나비가호장식3',level=37,count='90/5',word='강화',cost='5,000'):
  self.title=title;self.level=level;self.count=count;self.word=word;self.cost=cost
 def read(self,root,frame,box,**options):
  if box==w.BLESSING_TITLE:return [row(self.title,560,118)]
  if box==w.BLESSING_LEVEL:return [row('-%d'%self.level,570,218)]
  if box==w.BLESSING_NEXT:return [row('%d+'%(self.level+1),625,218)]
  if box==w.BLESSING_COUNT:return [row(self.count,594,645)] if self.count else []
  if box==w.BLESSING_PILL:return [row(self.word,730,720),row(self.cost,626,720)]
  raise AssertionError(box)


ROW={'index':1,'slot':{'x':700,'y':80,'w':34,'h':34,'cell_x':700,'cell_y':80,'cell_w':34,'cell_h':34}}


def observer(root,selected=1,zones=None,frame=None):
 import owner_blessing_native_candidate as blessing
 service=SimpleNamespace(adapter=SimpleNamespace(project=SimpleNamespace(root=root)),check=lambda:None,capture=lambda:frame,detector=None)
 context=SimpleNamespace(checkpoint=lambda:None,wait=lambda n:None)
 fake=SimpleNamespace(GROWTH_BLESSING_EXEC_BUTTONS=native.GROWTH_BLESSING_EXEC_BUTTONS,_growth_selected_slot=lambda f,rows:selected)
 return blessing.BlessingObserver(service,context,'나',fake,np.zeros((479,897,3),np.uint8),[ROW],ROW)


class WithRoot(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.getcwd(),ignore_cleanup_errors=True);self.root=Path(self.temp.name)
  config=self.root/'profiles/DKB/ocr_regions.json';config.parent.mkdir(parents=True)
  config.write_bytes((bootstrap.A/'profiles/DKB/ocr_regions.json').read_bytes())
 def tearDown(self):self.temp.cleanup()


class BlessingState(WithRoot):
 def state(self,zones,selected=1,gold=True):
  with patch('owner_text.read',zones.read):
   seen=observer(self.root,selected);return seen._state(real_frame(gold)),seen
 def test_ready_step(self):
  state,seen=self.state(Zones())
  self.assertEqual((state['slot'],state['level'],state['identity'],state['cost'],state['active']),(3,37,'blessing-words:나비3',5000,True))
  self.assertEqual(state['button'],native.GROWTH_BLESSING_EXEC_BUTTONS[0])
  self.assertEqual(seen.word_hit[:2],(456,450))
 def test_opening_at_a_nine(self):
  state,_=self.state(Zones(level=39,count='976/20',word='개방',cost='40,000'))
  self.assertTrue(state['active']);self.assertTrue(state['opening']);self.assertEqual(state['button'],native.GROWTH_BLESSING_EXEC_BUTTONS[1])
 def test_opening_can_show_no_counter(self):
  state,_=self.state(Zones(level=19,count='',word='개방',cost='20,000'));self.assertTrue(state['active'])
 def test_opening_with_a_short_count_stays(self):
  state,_=self.state(Zones(level=39,count='3/20',word='개방',cost='40,000'));self.assertFalse(state['active'])
 def test_opening_word_at_another_level_stays(self):
  state,_=self.state(Zones(level=37,word='개방'));self.assertFalse(state['active'])
 def test_short_material_stays(self):self.assertFalse(self.state(Zones(count='2/5'))[0]['active'])
 def test_unread_material_stays(self):self.assertFalse(self.state(Zones(count=''))[0]['active'])
 def test_dimmed_button_stays(self):self.assertFalse(self.state(Zones(),gold=False)[0]['active'])
 def test_unread_price_stays(self):self.assertFalse(self.state(Zones(cost='5,00'))[0]['active'])
 def test_close_spelling_on_the_button_stays(self):self.assertFalse(self.state(Zones(word='강회'))[0]['active'])
 def test_another_tile_selected_is_no_state(self):
  state,seen=self.state(Zones(),selected=2);self.assertIsNone(state);self.assertIn('선택',seen.last_reason)
 def test_no_title_is_no_state(self):
  state,seen=self.state(Zones(title='나비가호장식'));self.assertIsNone(state);self.assertIn('제목',seen.last_reason)


class BlessingRun(WithRoot):
 """The 18:27 failure: a level read mid-redraw on the last look must cost a retry, not the whole growth entry."""
 def run_with(self,verify=None,start=37,target=38,identity=None,title='나비가호장식3'):
  import owner_blessing_native_candidate as blessing
  zones=Zones(level=start,title=title);state=SimpleNamespace(selected=None);clicks=[]
  frame=real_frame()
  def click_hit(hit):
   clicks.append(hit)
   if hit[0]>=600:state.selected=1
   else:zones.level+=1
  service=SimpleNamespace(adapter=SimpleNamespace(project=SimpleNamespace(root=self.root)),check=lambda:None,capture=lambda:frame,click_hit=click_hit,
                          detector=SimpleNamespace(find=lambda *a,**k:None))
  context=SimpleNamespace(checkpoint=lambda:None,wait=lambda n:time.sleep(.02))
  real_verify=blessing.BlessingObserver.verify_final
  calls=[]
  def verify_final(me,frame,latest,kind):
   calls.append(1)
   return verify(len(calls)) if verify and verify(len(calls)) is not None else real_verify(me,frame,latest,kind)
  with patch('owner_text.read',zones.read),patch.object(native,'inspect_growth_equipment',lambda *a,**k:[ROW]),\
       patch.object(native,'_growth_selected_slot',lambda f,rows:state.selected),patch.object(native,'_click_xy',lambda s:(717,97)),\
       patch.object(blessing,'worn_candidates',lambda *a,**k:[ROW]),patch('owner_native_contracts.pool_for',lambda s:SimpleNamespace(get=lambda k:service.detector)),\
       patch.object(blessing.BlessingObserver,'verify_final',verify_final),patch.dict(sys.modules,{'owner_growth_current':SimpleNamespace(observe_value=lambda *a,**k:None)}):
   identity=identity or 'fake-words-%d'%time.monotonic_ns()
   result=blessing.run_blessing(service,context,identity,{'3번':{'enabled':True,'enhance':target,'breakthrough':0}})
  return result,clicks,service.adapter._owner_blessing_growth_outcome
 def test_one_step_is_pressed_and_confirmed(self):
  result,clicks,outcome=self.run_with()
  self.assertFalse(result);self.assertEqual(outcome['actions'],1);self.assertEqual(outcome['confirmed'],1)
  self.assertEqual(clicks[-1][:2],(456,450));self.assertEqual(outcome['state'],'processed_unverified')
 def test_a_failed_last_look_is_retried_and_does_not_raise(self):
  result,clicks,outcome=self.run_with(lambda n:False if n==1 else None)
  self.assertEqual(outcome['actions'],1);self.assertEqual(outcome['confirmed'],1);self.assertEqual(outcome['state'],'processed_unverified')
 def test_last_look_never_clear_presses_nothing_and_does_not_raise(self):
  result,clicks,outcome=self.run_with(lambda n:False)
  self.assertEqual(outcome['actions'],0);self.assertEqual(outcome['state'],'processed_unverified')
  self.assertEqual([c for c in clicks if c[0]<600],[])
  self.assertIn('입력 직전',outcome['slots']['1']['reason'])
 def sent_record(self,identity):
  from owner_gear_decision_candidate import Observation
  from owner_gear_intent_store_candidate import IntentStore
  from owner_gear_settings_candidate import Store
  path=Store(self.root,identity).path;store=IntentStore(path.with_name(path.stem+'-intent.json'))
  now=time.monotonic()
  def seen(n):return Observation(n,now+n/100,identity,'blessing-words:나비3','blessing:3','3번',37,None,None,True,None,None)
  store.begin({'kind':'enhance','before':seen(1),'second':seen(2),'cost':None,'balance':None,'item_icon':None});store.mark_sent()
  return store
 def test_a_step_sent_before_a_restart_settles_by_its_name(self):
  identity='fake-words-sent-%d'%time.monotonic_ns();store=self.sent_record(identity)
  result,clicks,outcome=self.run_with(start=38,target=38,identity=identity)
  self.assertEqual(outcome['actions'],0);self.assertEqual(outcome['confirmed'],1);self.assertIsNone(store.pending())
 def test_a_tile_with_another_name_settles_nothing_and_presses_nothing(self):
  identity='fake-words-other-%d'%time.monotonic_ns();store=self.sent_record(identity)
  result,clicks,outcome=self.run_with(start=38,target=50,identity=identity,title='토끼가호장식1')
  self.assertEqual(outcome['actions'],0);self.assertEqual(outcome['state'],'hold_pending_item');self.assertIsNotNone(store.pending())


class EnergyState(unittest.TestCase):
 PANEL=[row('생명의 기운 발현 2단계'),row('레벨9')]
 def test_title_and_level(self):self.assertEqual(w.parse_energy(self.PANEL),{'name':'생명','stage':2,'level':9})
 def test_close_name_is_no_name(self):self.assertIsNone(w.parse_energy([row('생멍의 기운 발현 2단계'),row('레벨9')]))
 def test_two_titles(self):self.assertIsNone(w.parse_energy(self.PANEL+[row('여명의 기운 발현 1단계')]))
 def test_selected_stage_must_be_the_highest_lit(self):
  rows=[row('1',1329,92),row('2',1328,149)]
  self.assertEqual(w.selected_stage(rows,lambda r:r['text']=='2'),2)
  self.assertIsNone(w.selected_stage(rows,lambda r:r['text']=='1'))
  self.assertIsNone(w.selected_stage(rows,lambda r:True))
  self.assertIsNone(w.selected_stage([],lambda r:True))
 def action(self,word='기운 발현',count='8/4',gold=True,target=3,info=None):
  import owner_energy_native_candidate as energy
  from project_adapter import achievement_rewards as reward
  frame=real_frame();frame.hi[700:750,1020:1270]=(249,222,126) if gold else (125,114,71)
  def read(root,f,box,**o):
   if box==w.ENERGY_PILL:return [row(word,1144,726,wide=77)]
   if box==w.ENERGY_COUNT:return [row(count,1144,676)] if count else []
   raise AssertionError(box)
  service=SimpleNamespace(adapter=SimpleNamespace(project=SimpleNamespace(root=Path('.'))))
  seen=energy.EnergyObserver(service,None,'나','생명',target,text_reader=lambda root,f:info or {'name':'생명','stage':2,'level':9})
  with patch('owner_text.read',read):return seen.state(frame),seen,reward
 def test_ready(self):
  state,seen,reward=self.action()
  self.assertTrue(state['active']);self.assertEqual(state['button'],reward.ENERGY_ACTIVE);self.assertEqual(seen.word_hit[:2],(715,454))
 def test_breakthrough_word(self):
  state,seen,reward=self.action(word='기운 돌파');self.assertEqual(state['button'],reward.ENERGY_BREAKTHROUGH);self.assertTrue(state['active'])
 def test_short_count_stays(self):self.assertFalse(self.action(count='3/4')[0]['active'])
 def test_unread_count_stays(self):self.assertFalse(self.action(count='')[0]['active'])
 def test_dimmed_stays(self):self.assertFalse(self.action(gold=False)[0]['active'])
 def test_at_target_stays(self):self.assertFalse(self.action(target=2)[0]['active'])
 def test_another_word_is_no_button(self):
  state,_,_=self.action(word='기운 발헌');self.assertIsNone(state['button']);self.assertFalse(state['active'])
 def test_tab_is_exact(self):
  rows=[row('생명의 기운',90,87),row('여명의 기운',90,148)]
  with patch('owner_text.read',lambda *a,**k:rows):
   self.assertEqual(w.energy_tab(None,real_frame(),'여명')[:2],(56,92))
   self.assertIsNone(w.energy_tab(None,real_frame(),'몽환'))
  with patch('owner_text.read',lambda *a,**k:[row('어명의 기운',90,148)]):
   self.assertIsNone(w.energy_tab(None,real_frame(),'여명'))


class Spirit(unittest.TestCase):
 def zones(self,dialog='영기 수련',train='수련',instant='즉시 완료',money='85,179/2,100',stone='976/3'):
  def read(root,f,box,**o):
   if box==w.SPIRIT_DIALOG:return [row(dialog,682,153)] if dialog else []
   if box==w.SPIRIT_BUTTONS:return [row(train,586,584),row(instant,818,584)] if instant else [row(train,586,584)]
   if box==w.SPIRIT_COUNTS:return [row(money,610,512),row(stone,700,512)]
   raise AssertionError(box)
  return read
 def frame(self,teal=True):
  frame=real_frame();frame.hi[560:610,500:700]=(90,160,170) if teal else (110,110,110)
  return frame
 def train(self,read,frame=None,other=None):
  frame=frame if frame is not None else self.frame()
  with patch('owner_text.read',read):return w.spirit_train(None,'버튼_영기수련_수련',frame,second=lambda f:other if other is not None else frame)
 def test_ready_on_two_frames(self):self.assertEqual(self.train(self.zones())[:2],(366,365))
 def test_needs_the_dialog_title(self):self.assertIsNone(self.train(self.zones(dialog='내기 수련')))
 def test_needs_both_buttons(self):self.assertIsNone(self.train(self.zones(instant='')))
 def test_short_material_stays(self):self.assertIsNone(self.train(self.zones(stone='2/3')))
 def test_short_money_stays(self):self.assertIsNone(self.train(self.zones(money='1,000/2,100')))
 def test_dimmed_stays(self):self.assertIsNone(self.train(self.zones(),frame=self.frame(False)))
 def test_counts_that_change_stay(self):
  frames=[self.frame(),self.frame()]
  def read(root,f,box,**o):return (self.zones() if f is frames[0] else self.zones(stone='975/3'))(root,f,box)
  self.assertIsNone(self.train(read,frame=frames[0],other=frames[1]))
 def test_second_look_missing_stays(self):
  with patch('owner_text.read',self.zones()):
   self.assertIsNone(w.spirit_train(None,'버튼_영기수련_수련',self.frame(),second=lambda f:None))
 def test_screen_check_by_title(self):
  detector=SimpleNamespace(entries={'체크_영기수련':dict(x=59,y=13,w=57,h=13)})
  with patch('owner_text.title',lambda f,root=None:['백영기수련']):
   self.assertEqual(w.spirit_check(detector,'체크_영기수련',real_frame())[:2],(87,19))
  with patch('owner_text.title',lambda f,root=None:['기운발현']):
   self.assertIsNone(w.spirit_check(detector,'체크_영기수련',real_frame()))
 def test_idle_needs_the_sentence(self):
  detector=SimpleNamespace(entries={'체크_영기수련_미진행':dict(x=398,y=433,w=101,h=11)})
  with patch('owner_text.title',lambda f,root=None:['영기수련']):
   with patch('owner_text.read',lambda *a,**k:[row('진행 중인 수련이 없습니다.')]):
    self.assertTrue(w.spirit_idle(detector,'체크_영기수련_미진행',real_frame()))
   with patch('owner_text.read',lambda *a,**k:[row('2시간 33분')]):
    self.assertIsNone(w.spirit_idle(detector,'체크_영기수련_미진행',real_frame()))
 def test_only_real_frames_are_answered(self):
  self.assertTrue(w.answers('버튼_영기수련_수련',real_frame()))
  self.assertFalse(w.answers('버튼_영기수련_수련',np.zeros((479,897,3),np.uint8)))
  self.assertFalse(w.answers('버튼_나가기',real_frame()))
 def test_a_read_that_fails_is_no_hit(self):
  def boom(*a,**k):raise RuntimeError('no reader')
  with patch.dict(w.FINDERS,{'버튼_영기수련_수련':boom}):self.assertIsNone(w.find_word(None,'버튼_영기수련_수련',real_frame()))
 def test_hit_holds_still_for_a_pixel(self):
  w._last.clear()
  self.assertEqual(w.steady('n',(100,100,None))[:2],(100,100))
  self.assertEqual(w.steady('n',(102,99,None))[:2],(100,100))
  self.assertEqual(w.steady('n',(120,99,None))[:2],(120,99))


class Detector(unittest.TestCase):
 def test_words_decide_the_spending_picture_on_a_real_frame(self):
  from roi_runtime import RoiDetector
  import owner_image_scope
  owner_image_scope.install()
  detector=RoiDetector(bootstrap.A/'profiles/DKB',['버튼_영기수련_수련'])
  frame=real_frame()
  with patch.dict(w.FINDERS,{'버튼_영기수련_수련':lambda d,n,f:(5,6,(1,2,9,9))}):
   w._last.clear();self.assertEqual(detector.find('버튼_영기수련_수련',frame,threshold=.9),(5,6,(1,2,9,9)))
   self.assertIsNone(detector.find('버튼_영기수련_수련',frame,threshold=.9,candidate_filter=lambda f,h:False))
  with patch.dict(w.FINDERS,{'버튼_영기수련_수련':lambda d,n,f:None}):
   self.assertIsNone(detector.find('버튼_영기수련_수련',frame,threshold=.1))


class Map(unittest.TestCase):
 def test_title_letters_name_the_screen_even_dimmed(self):
  rows={'k':dict(key='k',label='native:체크_영기수련',x=95,y=21,w=91,h=21,rule='left',file='x',bgr=False)}
  cut=np.zeros((21,91,3),np.uint8);cut[5:16,10:30]=255;cut[5:16,50:60]=255;cut[2:6,70:88]=255
  real=np.full((768,1366,3),40,np.uint8);real[21:42,95:186]=cut
  field=[SimpleNamespace(name='m_spirit',signature=None)]
  with patch.object(hd,'index',lambda:rows),patch.object(hd,'_load',lambda *a:cut),patch.object(hd,'layouts',lambda:field):
   self.assertIs(hd._titled_layout(real),field[0])
   dim=(real*.5).astype(np.uint8);self.assertIs(hd._titled_layout(dim),field[0])
   other=np.full((768,1366,3),40,np.uint8);other[10:60,300:400]=255
   self.assertIsNone(hd._titled_layout(other))
 def test_no_cut_no_answer(self):
  with patch.object(hd,'index',lambda:{}):self.assertIsNone(hd._titled_layout(np.zeros((768,1366,3),np.uint8)))


if __name__=='__main__':unittest.main()
