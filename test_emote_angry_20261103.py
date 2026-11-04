"""Actual08:54 frames and fake input for the 화남 requirement; no game input."""
import bootstrap
import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import cv2,numpy as np
from PIL import Image
import owner_emote_dispatch as d
from owner_emote_cooldown import Rate
from owner_emote_requirements import parse_target

P=Path(__file__).parent/'live_fixtures'
def frame(name):return np.asarray(Image.open(P/name).convert('RGB')).copy()
GOAL='emote-angry-goal-0854-24.png';BLANK='emote-angry-blank-0854-39.png'
OTHER='emote-other-quest-0854-20.png';NO_WORD='emote-requested-no-word-0854-21.png'
def real_detector():return d.chat_detector(str(bootstrap.A))

class Requirement(unittest.TestCase):
 def test_actual_0854_requirement_is_angry_not_surprise(self):
  self.assertEqual(d.known_goal(frame(GOAL))[0],'화남')
 def test_frames_without_the_whole_word_prove_nothing(self):
  for name in (OTHER,NO_WORD,BLANK):self.assertIsNone(d.known_goal(frame(name)),name)
 def test_other_saved_requirements_keep_their_own_names(self):
  self.assertEqual(d.known_goal(frame('emote-sleep-goal.png'))[0],'졸기')
  self.assertEqual(d.known_goal(frame('emote-surprise-goal.png'))[0],'황당')
 def test_no_saved_surprise_frame_reads_as_angry(self):
  for name in ('emote-surprise-goal.png','emote-three-cards-1.png','emote-three-cards-2.png','emote-panel-bottom.png','emote-panel-row-324.png','emote-panel-row-356.png','emote-panel-row-388.png','emote-panel-row-420.png'):
   self.assertEqual(d.angry_hits(frame(name)),[],name)
 def test_actual_marquee_positions_all_read_as_angry(self):
  # Real frames over different maps and scroll positions; the reference was
  # cropped from the first one only.
  for name,x in ((GOAL,766),('emote-angry-marquee-0854-59.png',787),('emote-angry-marquee-0855-11.png',790),('emote-angry-marquee-0855-31.png',778),('emote-angry-goal-0855-40.png',804)):
   self.assertEqual(d.angry_hits(frame(name)),[(x,148)],name)
   self.assertEqual(d.known_goal(frame(name))[0],'화남',name)
 def test_word_survives_half_pixel_marquee_positions(self):
  # Synthetic shifts of the one real frame, not additional real phases.
  f=frame(GOAL)
  for shift in (.25,.5,.75,1.5,2.5):
   moved=cv2.warpAffine(f,np.float32([[1,0,shift],[0,1,0]]),(897,479),flags=cv2.INTER_LINEAR)
   self.assertTrue(d.angry_hits(moved),shift)
 def test_word_needs_its_following_use_text(self):
  f=frame(GOAL);f[146:160,785:815]=f[146:160,840:870];self.assertEqual(d.angry_hits(f),[])
 def test_low_score_ocr_alone_never_authorizes_it(self):
  self.assertIsNone(parse_target([{'text':'표현중화남”사용하기','score':.832}]))
  self.assertEqual(parse_target([{'text':'표현 중 ‘화남’ 사용하기','score':.97}]),'화남')
  self.assertEqual(parse_target([{'text':"'화남' 사용하기",'score':.97}]),'화남')

class Card(unittest.TestCase):
 def test_first_scroll_position_uses_the_original_card_image(self):
  for name in (GOAL,BLANK,'emote-panel-top.png'):
   self.assertEqual(d.card_point(real_detector(),frame(name),'화남'),(281,460),name)
 def test_scrolled_positions_use_the_full_card(self):
  for name,y in (('emote-panel-middle.png',404),('emote-panel-row-388.png',340),('emote-panel-row-420.png',372)):
   self.assertEqual(d.card_point(real_detector(),frame(name),'화남'),(279,y),name)
 def test_scrolled_past_or_closed_panel_has_no_card(self):
  for name in ('emote-panel-bottom.png','emote-panel-row-324.png','emote-panel-row-356.png',NO_WORD):
   self.assertIsNone(d.card_point(real_detector(),frame(name),'화남'),name)
 def test_other_cards_do_not_borrow_the_original_angry_image(self):
  for target in ('졸기','황당','뽐내기'):self.assertIsNone(d.card_point(real_detector(),frame(GOAL),target),target)

class Worker(unittest.TestCase):
 def _run(self,name,rows=(),title='[외전] 항아리를 옮긴 자',once=False):
  temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(temp.cleanup)
  root=Path(temp.name);now=[1000.];clicks=[];shown=frame(name)
  book=S(item={'active':'quest','quests':{'quest':{'title':title}}},commit=lambda:None)
  self.seen=S(clicks=clicks,book=book,root=root,now=now)
  # The native chat state already requested it and the panel is open, as08:54.
  adapter=S(project=S(root=root,code='DKB'),_owner_emote_requested='quest')
  case=self
  class UI:
   def __init__(self):self.adapter=adapter;self.context=S(checkpoint=lambda:None,wait=lambda n:None)
   def frame(self):return shown
   def normal(self):return True
   def normal_frame(self,f):return False
   def rows(self,*a,**k):return list(rows)
   def wait(self,pred,seconds):case.assertTrue(pred(shown))
   def click(self,x,y,proof):
    case.assertTrue(proof(shown));clicks.append((x,y))
    if (x,y)==(281,460):case.assertEqual(Rate(root,'scope','char',clock=lambda:now[0]).remaining(),61)
   def wheel(self,*a,**k):raise AssertionError('card is already on screen')
  ui=UI()
  with patch.object(d,'chat_detector',return_value=real_detector()),patch.object(d,'close_chat'),patch.object(d,'save_navigation'),patch('owner_progression.state',return_value=S(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'),patch.object(d,'Rate',side_effect=lambda r,s,c:Rate(r,s,c,clock=lambda:now[0])):
   first=d.run(ui,book,'quest');again=None if once else d.run(ui,book,'quest')
  return first,again,clicks,book,Rate(root,'scope','char',clock=lambda:now[0]).remaining()
 def test_actual_0854_open_panel_selects_angry_once_and_keeps_the_limit(self):
  first,again,clicks,book,remaining=self._run(GOAL)
  self.assertIs(first,True);self.assertIs(again,False);self.assertEqual(clicks,[(281,460)]);self.assertEqual(remaining,61)
  attempt=book.item['quests']['quest']['emote_attempt']
  self.assertEqual((attempt['name'],attempt['phase']),('화남','input_intent_unverified'))
 def test_second_actual_arrival_selects_the_same_card(self):
  first,_,clicks,_,_=self._run('emote-angry-goal-0855-40.png')
  self.assertIs(first,True);self.assertEqual(clicks,[(281,460)])
 def test_unmapped_scrolled_away_word_with_low_confidence_sends_nothing(self):
  ocr=[{'text':'표현중화남”사용하기','score':.832,'y':155,'bounds':(735,147,860,165)}]
  with patch('owner_emote_requirements.Catalog.packaged_for_title',return_value=[]):
   first,again,clicks,book,remaining=self._run(BLANK,ocr)
  self.assertIs(first,False);self.assertIs(again,False);self.assertEqual(clicks,[]);self.assertEqual(remaining,0)
  self.assertNotIn('emote_attempt',book.item['quests']['quest'])

TITLE=[{'text':'[의전항아리를음긴 자8쪽','score':.818}]
class Portable(Worker):
 """Each worker run has an empty local settings folder, as on another PC."""
 def test_shipped_knowledge_needs_no_local_state_when_the_word_has_scrolled_away(self):
  first,again,clicks,book,remaining=self._run(BLANK,TITLE)
  self.assertIs(first,True);self.assertIs(again,False);self.assertEqual(clicks,[(281,460)]);self.assertEqual(remaining,61)
  attempt=book.item['quests']['quest']['emote_attempt']
  self.assertEqual((attempt['name'],attempt['phase']),('화남','input_intent_unverified'))
 def test_exact_stage_pixels_do_not_depend_on_uncertain_title_ocr(self):
  for text in ('[의전항아리를음긴 자7쪽','[의전항아리를음긴 자','[의전항아리를음긴 자18'):
   first,_,clicks,_,remaining=self._run(BLANK,[{'text':text,'score':.8}])
   self.assertIs(first,True,text);self.assertEqual(clicks,[(281,460)]);self.assertEqual(remaining,61)
 def test_other_real_steps_of_the_same_quest_do_not_use_stage_eight(self):
  import owner_emote_requirements as r
  image=r.packaged_knowledge()['quests']['외전|항아리를옮긴자|8']['title_image']
  # NCC alone accepted real step 5 (.913); exact foreground glyph proof must
  # now reject both wrong steps, before any OCR/card/input.
  self.assertIsNone(d.tracked_title_y(frame('emote-hangari-stage7-0854-11.png'),image))
  self.assertIsNone(d.tracked_title_y(frame('emote-hangari-stage5-0853-23.png'),image))
  self.assertEqual(r.stage_of([{'text':'[의전]황아리를옮긴자5','score':.99}]),'5')
 def test_different_book_quest_or_untracked_row_cannot_use_it(self):
  import owner_emote_requirements as r
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   c=r.Catalog(temp)
   self.assertEqual(c.packaged_for_title('[첫걸음] 승천의 탐'),[])
   self.assertEqual([k for k,_,_ in c.packaged_for_title('[외전] 항아리를 옮긴 자')],['외전|항아리를옮긴자|8'])
   self.assertEqual([k for k,_,_ in c.packaged_for_title('항아리를 옮긴 자 8')],['외전|항아리를옮긴자|8'])
  image=r.packaged_knowledge()['quests']['외전|항아리를옮긴자|8']['title_image']
  f=frame(BLANK);self.assertEqual(d.tracked_title_y(f,image),126)
  f[126:143,731:738]=f[165:182,731:738];self.assertIsNone(d.tracked_title_y(f,image))
 def test_contradicting_fresh_requirement_disables_only_that_entry(self):
  import owner_emote_requirements as r
  temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(temp.cleanup)
  c=r.Catalog(temp.name);c.invalidate('외전|항아리를옮긴자|8','황당')
  self.assertIsNone(c.packaged('외전|항아리를옮긴자|8'))
  self.assertEqual(c.packaged_for_title('[외전] 항아리를 옮긴 자'),[])
  self.assertIsNotNone(c.packaged('외전|동굴에서들린소리|4'))
 def test_fresh_other_emote_at_that_row_blocks_input_and_invalidates(self):
  with patch.object(d,'known_goal',return_value=('황당',148)):
   first,_,clicks,_,remaining=self._run(BLANK,TITLE,once=True)
  self.assertIs(first,False);self.assertEqual(clicks,[]);self.assertEqual(remaining,0)
 def _mismatch(self,name,rows,title):
  from owner_emote_requirements import EmoteQuestMismatch
  from owner_skill_goal import Pending
  self.assertTrue(issubclass(EmoteQuestMismatch,Pending))
  with self.assertRaises(EmoteQuestMismatch) as caught:self._run(name,rows,title=title,once=True)
  self.assertEqual(self.seen.clicks,[]);self.assertNotIn('emote_attempt',self.seen.book.item['quests']['quest'])
  self.assertEqual(Rate(self.seen.root,'scope','char',clock=lambda:self.seen.now[0]).remaining(),0)
  self.assertEqual(caught.exception.quest,title);return caught.exception
 def test_actual_0855_book_and_tracked_quest_differ(self):
  # The book had selected this quest while the game kept tracking 항아리 8.
  error=self._mismatch('emote-angry-goal-0855-40.png',TITLE,'[첫걸음] 승천의 탐')
  self.assertEqual(error.hud,'외전|항아리를옮긴자|8');self.assertEqual(error.target,'화남')
 def test_unshipped_tracked_quest_is_caught_by_two_title_readings(self):
  with patch('owner_emote_requirements.Catalog.packaged_images',return_value=[]):
   error=self._mismatch(GOAL,[{'text':'[의전]방아리를옮긴 자8','score':.99}],'[첫걸음] 승천의 탐')
  self.assertEqual(error.target,'화남')
 def test_noisy_or_partial_title_is_not_called_a_mismatch(self):
  from owner_emote_requirements import title_disagrees as differ
  for text,book in (('[의전방아리를 옮간,자8 학','[외전] 항아리를 옮긴 자'),('[의항아리를옮긴자4제','[외전] 항아리를 옮긴 자'),('0에서들리소리4','[외전] 동굴에서 들린 소리'),('어동굴에서들린 소리4','[외전] 동굴에서 들린 소리'),('[외전]교','[외전] 교대가 늦어진 이유'),('소리4','[외전] 동굴에서 들린 소리'),('','[외전] 동굴에서 들린 소리')):
   self.assertFalse(differ(text,book),text)
  self.assertTrue(differ('[의전]항아리를음긴 자8제','[첫걸음] 승천의 탐'))
  self.assertTrue(differ('[외전]동굴에서들린소리4','[외전] 항아리를 옮긴 자'))
 def test_unreadable_title_keeps_the_fresh_requirement(self):
  # No shipped image and no readable title: nothing proves another quest.
  with patch('owner_emote_requirements.Catalog.packaged_images',return_value=[]):
   first,_,clicks,_,_=self._run(GOAL,(),title='[첫걸음] 승천의 탐',once=True)
  self.assertIs(first,True);self.assertEqual(clicks,[(281,460)])

class Shipped(unittest.TestCase):
 def test_every_entry_is_portable_and_never_claims_a_send(self):
  import owner_emote_requirements as r
  data=r.packaged_knowledge();self.assertEqual(len(data['quests']),5)
  for key,entry in data['quests'].items():
   from owner_emote_atlas import names
   self.assertEqual(len(key.split('|')),3,key);self.assertIn(entry['emote'],set(d.NAMES)|names(),key)
   self.assertTrue(entry['observed'],key);self.assertIs(entry['send_verified'],False,key)
   self.assertFalse({'x','y','point','character','scope'}&set(entry),key)
   if entry['title_image']:
    d.asset(entry['title_image']['root']);d.asset(entry['title_image']['digit'])
  for name,card in data['cards'].items():
   if 'card' in card:self.assertEqual(d.NAMES[name],card['card'])
   if 'native_image' in card:self.assertEqual(d.NATIVE_CARDS[name],card['native_image'])
   self.assertFalse({'x','y','point'}&set(card))
 def test_original_smile_card_proves_only_itself_at_the_first_position(self):
  det=real_detector();point=d.card_point(det,frame(GOAL),'웃음')
  self.assertIsNotNone(point);self.assertLess(point[0],300);self.assertLess(point[1],360)
  self.assertIsNone(d.card_point(det,frame('emote-panel-row-420.png'),'웃음'))
  self.assertIsNone(d.card_point(det,frame(NO_WORD),'웃음'))
 def test_a_hint_orders_the_search_but_cannot_select_a_card(self):
  import owner_emote_requirements as r
  self.assertEqual(r.search_order('화남'),(1,-1));self.assertEqual(r.search_order('졸기'),(-1,1));self.assertEqual(r.search_order('처음보는감정'),(-1,1))
  self.assertIsNone(d.card_point(real_detector(),frame('emote-panel-bottom.png'),'화남'))
 def test_rate_is_per_character_and_survives_restart_across_quests(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   now=[1000.];mk=lambda c:Rate(temp,'scope',c,clock=lambda:now[0])
   mk('A').reserve('외전|항아리를옮긴자|8','화남')
   self.assertEqual(mk('A').remaining(),61);self.assertEqual(mk('B').remaining(),0)
   with self.assertRaises(Exception):mk('A').reserve('외전|동굴에서들린소리|4','황당')
   now[0]+=61;self.assertEqual(mk('A').remaining(),0)

del Worker
if __name__=='__main__':unittest.main()
