import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import bootstrap
import owner_emote_dispatch as d
from owner_emote_requirements import Catalog,quest_id,parse_target
from owner_emote_cooldown import Rate
from owner_quest_emote_candidate import empty_chat,target_zone

P=Path(__file__).parent/'live_fixtures'
def frame(name):return np.asarray(Image.open(P/name).convert('RGB'))
class Tests(unittest.TestCase):
 def test_actual_requested_goals_are_different(self):
  self.assertEqual(d.known_goal(frame('emote-sleep-goal.png'))[0],'졸기')
  self.assertEqual(d.known_goal(frame('emote-surprise-goal.png'))[0],'황당')
  self.assertIsNone(d.known_goal(np.zeros((479,897,3),dtype='uint8')))
 def test_three_cards_have_distinct_verified_native_positions(self):
  for name in ('emote-three-cards-1.png','emote-three-cards-2.png'):
   f=frame(name);self.assertEqual([d.card_hit(f,s) for s in ('졸기','뽐내기','황당')],[(279,440),(338,449),(397,440)])
 def test_empty_input_foreground_survives_translucent_background(self):
  for name in ('emote-three-cards-1.png','emote-three-cards-2.png'):self.assertTrue(empty_chat(frame(name)))
  f=frame('emote-three-cards-2.png').copy();f[450:460,200:203]=255;self.assertFalse(empty_chat(f))
 def test_actual_compact_target_ring_is_supported(self):
  self.assertTrue(target_zone(frame('emote-surprise-goal.png')))
  self.assertFalse(target_zone(np.zeros((479,897,3),dtype='uint8')))
 def test_unknown_requirement_reader_and_strict_identity(self):
  self.assertEqual(parse_target([{'text':'채팅 감정표현 중 ‘기쁨’ 사용하기','score':.999}]),'기쁨')
  self.assertIsNone(parse_target([{'text':'감정표현 중 기쁨 사용하기','score':.81}]))
  self.assertEqual(quest_id([{'text':'[외전]동굴에서 들린 소리4 진행','score':.999}]),'외전|동굴에서들린소리|4')
  self.assertIsNone(quest_id([{'text':'들린소리4','score':.999}]))
 def test_shared_catalog_reuses_same_quest_and_keeps_steps_separate(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   a=Catalog(temp);a.learn('외전|동굴에서들린소리|4','황당')
   self.assertEqual(Catalog(temp).get('외전|동굴에서들린소리|4'),'황당')
   self.assertIsNone(Catalog(temp).get('외전|동굴에서들린소리|5'))
   self.assertIs(a.read()['quests']['외전|동굴에서들린소리|4']['quest_completed'],False)
 def test_learned_requirement_image_is_shared_across_character_pixels(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   f=frame('emote-three-cards-1.png');Catalog(temp).learn('외전|동굴에서들린소리|4','황당',f[147:165,731:877].copy())
   other=f.copy();other[100:300,300:600]=0
   self.assertEqual(Catalog(temp).visual_goal(other)[0],'황당')
   other[147:165,731:877]=0;self.assertIsNone(Catalog(temp).visual_goal(other))
 def _worker_selects(self,initial,other_row=False):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   root=Path(temp);now=[1000.];actions=[]
   book=S(item={'active':'quest','quests':{'quest':{'title':'동굴에서 들린 소리'}}},commit=lambda:None)
   # Reproduce a character already at the trigger: native chat callback
   # never fires, but paired explicit tracker text still authorizes the UI.
   adapter=S(project=S(root=root,code='DKB'),_owner_emote_requested=None)
   class UI:
    def __init__(self):self.adapter=adapter;self.kind=initial;self.context=S(checkpoint=lambda:None,wait=lambda n:None)
    def frame(self):return self.kind
    def normal(self):return True
    def normal_frame(self,f):return f=='field'
    def rows(self,*a,**kw):return [{'text':'[외전]동굴에서들린소리4','score':.999}]
    def wait(self,pred,seconds):assert pred(self.kind)
    def click(self,x,y,proof):
     assert proof(self.kind)
     actions.append((x,y));self.kind='chat' if (x,y)==(114,447) else 'menu'
     if (x,y)==(397,440):assert Rate(root,'scope','char',clock=lambda:now[0]).remaining()==61
    def wheel(self,*a,**kw):raise AssertionError('correct card already visible')
   class Detector:
    def find(self,name,f,threshold):
     if name=='체크_채팅창' and f in ('chat','menu'):return (1,1,(0,0,2,2))
     if name=='버튼_채팅창_감정' and f=='chat':return (198,429,(190,421,206,437))
   ui=UI()
   # A prior unreadable scroll phase backs off OCR only. A later paired
   # explicit known label must still be able to select its card.
   import time
   ui._owner_emote_unreadable_until=time.monotonic()+100
   observations=[0]
   def moving_tracker(f):
    observations[0]+=1
    return ('황당',146) if observations[0]<=2 else (('졸기',184) if other_row else None)
   # The requirement leaves the marquee immediately after its paired
   # confirmation, reproducing the actual09:27 failure.
   with patch.object(d,'known_goal',side_effect=moving_tracker),patch.object(d,'target_zone',return_value=True),patch.object(d,'empty_chat',return_value=True),patch.object(d,'panel',side_effect=lambda f:f=='menu'),patch.object(d,'card_hit',side_effect=lambda f,t:(397,440) if f=='menu' else None),patch.object(d,'close_chat',side_effect=lambda u,x:setattr(u,'kind','field')),patch('roi_runtime.RoiDetector',return_value=Detector()),patch('owner_progression.state',return_value=S(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'),patch.object(d,'Rate',side_effect=lambda r,s,c:Rate(r,s,c,clock=lambda:now[0])):
    expected=[(114,447),(198,429),(397,440)] if initial=='field' else [(397,440)]
    self.assertTrue(d.run(ui,book,'quest'));self.assertEqual(actions,expected)
    self.assertFalse(d.run(ui,book,'quest'));self.assertEqual(len(actions),len(expected))
   self.assertEqual(book.item['quests']['quest']['emote_attempt']['phase'],'input_intent_unverified')
 def test_worker_selects_required_card_and_cooldown_blocks_another_target(self):self._worker_selects('field')
 def test_already_open_emotion_panel_is_resumed_without_reopening_or_chat_text(self):self._worker_selects('menu')
 def test_another_accepted_quest_emote_in_different_tracker_row_does_not_cancel_current(self):self._worker_selects('menu',True)

if __name__=='__main__':unittest.main()
