"""Existing screenshots and fake readers only; no game input."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
import owner_emote_dispatch as d
from owner_emote_atlas import Atlas,names
from owner_emote_requirements import Catalog,parse_target,learn_selected_requirement

P=Path(__file__).parent/'live_fixtures'
def frame(n):return np.array(Image.open(P/n).convert('RGB'))

class Memory(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.atlas=Atlas(self.temp.name)
 def test_all_fifteen_available_names_have_saved_grid_slots(self):
  self.assertEqual(len(names()),15)
  for name,e in self.atlas.entries().items():
   with self.subTest(name=name):
    f=frame(e['source']);p=self.atlas.find(f,name)
    self.assertIsNotNone(p);self.assertTrue(self.atlas.matches(f,name,p))
 def test_atlas_never_borrows_another_slot_or_other_page(self):
  f=frame('emote-panel-top.png')
  self.assertIsNotNone(self.atlas.find(f,'웃음'))
  self.assertIsNone(self.atlas.find(f,'졸기'))
  self.assertFalse(self.atlas.matches(f,'웃음',self.atlas.find(f,'부끄')))
  self.assertIsNone(self.atlas.find(np.zeros((720,1280,3),dtype='uint8'),'웃음'))
 def test_direction_uses_visible_grid_and_never_sends_input(self):
  self.assertEqual(self.atlas.direction(frame('emote-panel-top.png'),'졸기'),-1)
  self.assertEqual(self.atlas.direction(frame('emote-panel-row-324.png'),'웃음'),1)
 def test_all_names_parse_compact_but_unknown_item_needs_emote_context(self):
  for name in names():self.assertEqual(parse_target([{'text':f'‘{name}’ 사용하기','score':.95}]),name)
  self.assertIsNone(parse_target([{'text':'‘물약’ 사용하기','score':.99}]))
  self.assertEqual(parse_target([{'text':'‘쉿’ 사용하기','score':.99}],emote_context=True),'쉿')
  self.assertEqual(parse_target([{'text':'감정표현 중 쉿 사용하기','score':.99}]),'쉿')
  self.assertIsNone(parse_target([{'text':'감정표현 중 쉿 사용하기','score':.949}]))
  self.assertEqual(parse_target([{'text':'감정표현 중 으쪽 사용하기','score':.97}]),'으쓱')
  self.assertIsNone(parse_target([{'text':'감정표현 중 으쪽 사용하기','score':.936}]))
 def test_learned_one_character_quest_survives_another_character(self):
  c=Catalog(self.temp.name);self.assertTrue(c.learn('외전|새로운감정임무|7','쉿'))
  self.assertEqual(Catalog(self.temp.name).get('외전|새로운감정임무|7'),'쉿')
  self.assertEqual(c.known_for_title('[외전] 새로운 감정 임무')[0][2]['emote'],'쉿')
  self.assertIsNone(c.get('외전|새로운감정임무|8'))
 def test_new_card_learn_requires_two_identical_fresh_label_masks(self):
  a=frame('emote-panel-top.png');bounds=(262,366,297,375)
  self.assertTrue(self.atlas.learn('새감정',[a,a.copy()],bounds))
  other=Atlas(self.temp.name);self.assertIsNotNone(other.find(a,'새감정'))
  b=a.copy();b[367,270]=[0,0,0] if b[367,270].min()>150 else [255]*3
  self.assertFalse(self.atlas.learn('잘못된감정',[a,b],bounds))

class KnownBinding(unittest.TestCase):
 def test_verified_group_reuses_root_but_stage_still_needs_point95(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   for score,expected in ((.97,'외전|새로운감정임무|7'),(.949,None)):
    ui=S(adapter=S(project=S(root=Path(temp))),frame=lambda:object(),rows=lambda *a,**kw:[{'text':'도사7','score':score}])
    with patch('owner_mission_reading.selected_center',return_value=155),patch('owner_skill_ui.quest_screen',return_value=True):
     result=learn_selected_requirement(ui,[{'text':'감정표현 중 으쓱 사용하기','score':.99}],'[외전] 새로운감정임무')
    self.assertEqual(result,(expected,'으쓱'))
 def test_unseen_arrival_uses_fixed_detail_even_without_native_chat_callback(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   actions=[];book=S(item={'active':'q','quests':{'q':{'title':'동굴에 같헌 도사'}}},commit=lambda:None)
   adapter=S(project=S(root=Path(temp)),_owner_emote_requested=None)
   class UI:
    def __init__(self):self.adapter=adapter;self.kind='field';self.context=S(wait=lambda n:None,checkpoint=lambda:None)
    def frame(self):return self.kind
    def normal_frame(self,f):return f=='field'
    def wait(self,pred,seconds):assert pred(self.kind)
    def click(self,x,y,proof):
     assert proof(self.kind);actions.append((x,y));self.kind='chat' if x==114 else 'menu'
    def wheel(self,*a,**kw):raise AssertionError('remembered card visible')
   class Detector:
    def find(self,name,f,threshold):
     if name=='체크_채팅창' and f in ('chat','menu'):return (1,1,(0,0,2,2))
     if name=='버튼_채팅창_감정':return (198,429,(0,0,2,2))
   ui=UI()
   def unreadable(u):u._owner_emote_requirement_hint=True;return None
   locator=S(atlas=S(entries=lambda:{'으쓱':{}},direction=lambda *a:None),find=lambda f,t:(397,392) if f=='menu' else None,matches=lambda *a:True)
   with patch.object(d,'known_goal',return_value=None),patch.object(d,'bound_requirement',return_value=None),patch.object(d,'read_requirement',side_effect=unreadable),patch.object(d,'fixed_requirement',return_value=('외전|동굴에갇힌도사|7','으쓱')) as fixed,patch.object(d,'target_zone',return_value=True),patch.object(d,'chat_detector',return_value=Detector()),patch.object(d,'empty_chat',return_value=True),patch.object(d,'panel',side_effect=lambda f:f=='menu'),patch.object(d,'CardLocator',return_value=locator),patch.object(d,'close_chat',side_effect=lambda *a:setattr(ui,'kind','field')),patch.object(d,'closed_chat_view',return_value='field'),patch('owner_progression.state',return_value=S(character='char')),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):
    self.assertTrue(d.run(ui,book,'q'));self.assertEqual(fixed.call_count,1)
   self.assertEqual(actions,[(114,447),(198,429),(397,392)])
 def test_fixed_fallback_reuses_empty_chat_cleanup_before_mission_entry(self):
  actions=[];book=S(item={'active':'q','quests':{'q':{'title':'새로운 임무'}}})
  ui=S(adapter=S(project=S(root=Path('.'))),normal=lambda:True,
       open=lambda mode:actions.append(('open',mode)),close_known=lambda:actions.append('close_mission'),rows=lambda *a,**kw:[])
  with patch.object(d,'navigation_open',return_value=True),patch.object(d,'chat_detector',return_value=object()),patch.object(d,'close_chat',side_effect=lambda *a:actions.append('close_empty_chat')),patch.object(d,'closed_chat_view',return_value='field'),patch('owner_story_groups.Groups',return_value=S(select=lambda k:True)),patch('owner_progression.state',return_value=S(power=120000)),patch('owner_emote_requirements.learn_selected_requirement',return_value=('외전|새로운임무|7','으쓱')):
   self.assertEqual(d.fixed_requirement(ui,book,'q'),('외전|새로운임무|7','으쓱'))
  self.assertEqual(actions,['close_empty_chat',('open','sub_quest'),'close_mission'])
 def test_unseen_quest_is_learned_from_fixed_selected_detail_before_hud(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   ui=S(adapter=S(project=S(root=Path(temp))),frame=lambda:object(),
        rows=lambda *a,**kw:[{'text':'[외전]새로운감정임무7','score':.99}])
   detail=[{'text':'지정 위치에서 채팅-감정표현 중','score':.99}, {'text':'‘으쓱’ 사용하기','score':.99}]
   with patch('owner_mission_reading.selected_center',return_value=155),patch('owner_skill_ui.quest_screen',return_value=True):
    self.assertEqual(learn_selected_requirement(ui,detail,'[외전] 새로 읽힌 제목'),('외전|새로운감정임무|7','으쓱'))
   c=Catalog(temp);self.assertEqual(c.get('외전|새로운감정임무|7'),'으쓱')
   self.assertEqual(c.known_for_title('[외전] 새로 읽힌 제목')[0][0],'외전|새로운감정임무|7')
   self.assertIsNone(c.get('외전|새로운감정임무|8'))
 def test_non_emote_consumable_goal_never_enters_shared_emote_memory(self):
  ui=S(frame=lambda:(_ for _ in ()).throw(AssertionError('must not inspect unrelated goal')))
  self.assertIsNone(learn_selected_requirement(ui,[{'text':'‘물약’ 사용하기','score':.99}]))
 def test_actual_new_quest_and_observed_book_alias_share_one_stage(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   found=Catalog(temp).known_for_title('[외전] 동글에 도사')
   self.assertEqual([(k,s,e['emote']) for k,s,e in found],[('외전|동굴에갇힌도사|7','7','으쓱')])
 def test_shipped_no_png_quest_binds_title_and_stage_without_requirement_reader(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   f=frame('emote-three-cards-1.png');f[129:144,731:738]=255
   rows=[{'text':'[외전]동굴에서 들린 소리4','score':.99,'bounds':(738,128,875,144)}]
   ui=S(context=S(wait=lambda n:None),rows=lambda *a,**kw:rows,last_text_frame=f)
   with patch.object(d,'read_requirement',side_effect=AssertionError('known quest must not read goal')):
    got=d.bound_requirement(ui,{'title':'[외전] 1동굴에서 들린 소리'},Catalog(temp),f,f)
   self.assertEqual(got,('외전|동굴에서들린소리|4','황당',150))
 def test_wrong_stage_other_quest_and_unhighlighted_row_do_not_bind(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   f=frame('emote-three-cards-1.png');f[129:144,731:738]=255
   for text in ('[외전]동굴에서들린소리5','[외전]교대가늦어진이유4'):
    ui=S(context=S(wait=lambda n:None),rows=lambda *a,**kw:[{'text':text,'score':.99,'bounds':(738,128,875,144)}],last_text_frame=f)
    self.assertIsNone(d.bound_requirement(ui,{'title':'동굴에서 들린 소리'},Catalog(temp),f,f))
   f[129:144,731:738]=0
   ui=S(context=S(wait=lambda n:None),rows=lambda *a,**kw:[{'text':'[외전]동굴에서들린소리4','score':.99,'bounds':(738,128,875,144)}],last_text_frame=f)
   self.assertIsNone(d.bound_requirement(ui,{'title':'동굴에서 들린 소리'},Catalog(temp),f,f))

if __name__=='__main__':unittest.main()
