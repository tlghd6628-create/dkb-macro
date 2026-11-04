exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest,tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
from PIL import Image
import numpy as np
import owner_mission_ui as m
from owner_mission_reading import title_from_rows,read_selected_title,MissionRowUnreadable
from owner_mission_policy import QuestBook
from owner_skill_goal import Pending

def row(text,x=80,y=155,score=.99):return {'text':text,'x':x,'y':y,'score':score}

class Reading(unittest.TestCase):
 def test_accept_does_not_commit_without_verified_capacity_change(self):
  ui=object.__new__(m.MissionUI);ui.click_word=lambda *a,**k:None;ui.wait=lambda *a,**k:None
  ui.frame=lambda:object();ui.service=NS(detector=object())
  book=NS(item={'quests':{'q':{'title':'시험 임무','accepted':False}}},commit=lambda:self.fail('must not save unverified acceptance'))
  with patch('owner_mission_ui.selected_center',return_value=100),patch('owner_mission_reading.read_selected_title',return_value=('시험 임무',100)),patch('owner_mission_ui.auto_button_hit',return_value=True),patch('owner_mission_ui.accepted_quota',return_value=None):
   with self.assertRaises(Pending):ui.accept_only(book,'q',5)
  self.assertFalse(book.item['quests']['q']['accepted'])
 def test_actual_npc_dialogue_hands_to_native_skip_without_menu_click(self):
  ui=object.__new__(m.MissionUI);ui.adapter=NS(mode='sub_quest',project=NS(root=A,code='DKB'));ui.frame=lambda:np.asarray(Image.open(T/'live/story-npc-dialogue.png'));ui.context=NS(wait=lambda s:None)
  ui.click_auto=lambda:self.fail('dialogue must not click mission button')
  self.assertTrue(ui.execution_dialogue_pair());ui.start_selected();self.assertIsNone(ui.opened)
 def test_active_quest_dialogue_does_not_reopen_mission_menu(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a');key=b.observe('sub_quest','active',suitable=True,actionable=True);b.activate(key)
   ui=object.__new__(m.MissionUI);ui.execution_dialogue_pair=lambda:True
   self.assertEqual(ui.pick(b,'sub_quest',100000),key)
 def test_auto_progress_closes_proved_remaining_mission_panel(self):
  ui=object.__new__(m.MissionUI);current=[np.asarray(Image.open(T/'live/title-failure-r19.png'))];closed=[]
  ui.context=NS(wait=lambda s:None);ui.frame=lambda:current[0];ui.execution_dialogue_pair=lambda:False;ui.execution_dialogue=lambda f:False;ui.click_auto=lambda:True
  def close():closed.append(True);current[0]=np.zeros_like(current[0])
  ui.close_known=close;ui.wait=lambda predicate,**kw:self.assertTrue(predicate(ui.frame()))
  ui.start_selected();self.assertEqual(closed,[True]);self.assertIsNone(ui.opened)
 def test_split_title_fragments_joined(self):
  self.assertEqual(title_from_rows([row('[외전]',80),row('헤어진 두 도사',130),row('1',240)]),'[외전] 헤어진 두 도사 1')
 def test_wrapped_title_joined(self):
  self.assertEqual(title_from_rows([row('[외전] 도술 구매의',680,86),row('자격 증명 1',680,99)]),'[외전] 도술 구매의 자격 증명 1')
 def test_conflicting_or_summary_text_rejected(self):
  for rows in ([row('[외전] 영혼1'),row('[외전] 물건1')],[row('본 임무는 요약 정보를 제공하지 않습니다')],[row('[외전]')],[row('[외전] 영혼1',score=.70)]):self.assertIsNone(title_from_rows(rows))
 def fake_reader(self,detail=()):
  f=np.asarray(Image.open(T/'live/story-list.png'))
  return NS(frame=lambda:f,context=NS(wait=lambda s:None),rows=lambda box,**kwargs:[row('[외전] 호랑이의 영혼1')] if box[0]==70 else list(detail))
 def test_actual_selected_row_after_scroll(self):
  ui=self.fake_reader([row('[외전] 호랑이의 영혼1')]);title,y=read_selected_title(ui,400)
  self.assertEqual(y,156);self.assertIn('영혼1',title)
 def test_wide_row_can_resolve_unreadable_small_header(self):
  title,_=read_selected_title(self.fake_reader(),156);self.assertIn('영혼1',title)
 def test_different_detail_cannot_authorize_row(self):
  with self.assertRaises(MissionRowUnreadable):read_selected_title(self.fake_reader([row('[서사] 완전히 다른 임무')]),156)
 def test_weaker_metadata_needs_two_independent_paired_regions(self):
  ui=self.fake_reader();ui.rows=lambda box,**kwargs:[row('[외전] 황무지 마을의 여울1',score=.82)]
  self.assertIn('황무지',read_selected_title(ui,156)[0])
  ui.rows=lambda box,**kwargs:[row('[외전] 황무지 마을의 여울1',score=.82)] if box[0]==70 else []
  with self.assertRaises(MissionRowUnreadable):read_selected_title(ui,156)
 def test_observed_small_font_metadata_keeps_category_and_step_corroboration(self):
  ui=self.fake_reader();ui.rows=lambda box,**kwargs:[row('[외전] 활무지 마을의 여흡 1',score=.839)] if box[0]==70 else [row('[외전] 항무지 마음의 0',690,88,.863),row('1여플 1',790,88,.765)]
  self.assertIn('활무지',read_selected_title(ui,156)[0])
 def test_missing_active_is_held_not_completed_and_other_verified_quest_runs(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a');old=b.observe('sub_quest','[외전] 사라진 임무1',suitable=True,actionable=True,accepted=True,completed=False);b.activate(old);b.seal_batch()
   f=np.asarray(Image.open(T/'live/story-list.png'))
   ui=object.__new__(m.MissionUI);ui.context=NS(checkpoint=lambda:None,wait=lambda s:None);ui.frame=lambda:f;ui.open=lambda mode:None;ui.wheel=lambda *a:None
   ui.selected=lambda mode,y,book,power:book.observe(mode,'[외전] 현재 보이는 임무1',suitable=True,actionable=True,accepted=True,completed=False)
   with patch.object(m,'markers',side_effect=lambda f,n,**kw:[] if n=='group-closed' else [156]),patch.object(m,'row_signature',return_value='row'),patch.object(m,'quest_screen',return_value=True):
    picked=ui._pick_legacy(b,'sub_quest',100000)
   self.assertIsNotNone(picked);self.assertNotEqual(picked,old);self.assertFalse(b.item['quests'][old]['completed']);self.assertEqual(b.item['quests'][old]['block']['reason'],'condition')
 def test_unseen_old_batch_cannot_block_refill_forever(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a');old=b.observe('sub_quest','[외전] 이전 묶음1',suitable=True,actionable=True,accepted=True,completed=False)
   b.batch_add(old);b.seal_batch();f=np.asarray(Image.open(T/'live/story-list.png'))
   ui=object.__new__(m.MissionUI);ui.context=NS(checkpoint=lambda:None,wait=lambda s:None);ui.frame=lambda:f;ui.open=lambda mode:None;ui.wheel=lambda *a:None
   ui.selected=lambda mode,y,book,power:book.observe(mode,'[외전] 새로운 임무1',suitable=True,actionable=True,accepted=True,completed=False)
   with patch.object(m,'markers',side_effect=lambda f,n,**kw:[] if n=='group-closed' else [156]),patch.object(m,'row_signature',return_value='row'),patch.object(m,'quest_screen',return_value=True):
    picked=ui._pick_legacy(b,'sub_quest',100000)
   self.assertIsNotNone(picked);self.assertNotEqual(picked,old);self.assertFalse(b.item['quests'][old]['completed']);self.assertEqual(b.item['quests'][old]['block']['reason'],'condition')
 def test_paired_ocr_bucket_boundary_jitter_is_allowed(self):
  from owner_skill_ui import paired_rows_match
  self.assertTrue(paired_rows_match([row('[외전] 임무1',80,154)],[row('[외전] 임무1',81,155)]))
 def test_paired_ocr_still_rejects_changed_text(self):
  from owner_skill_ui import paired_rows_match
  self.assertFalse(paired_rows_match([row('임무1')],[row('임무2')]))
 def test_paired_ocr_rejects_distinct_row_position(self):
  from owner_skill_ui import paired_rows_match
  self.assertFalse(paired_rows_match([row('임무1',80,154)],[row('임무1',80,180)]))
 def test_paired_ocr_detector_order_is_not_identity(self):
  from owner_skill_ui import paired_rows_match
  a=[row('[외전]',80),row('임무1',140)]
  self.assertTrue(paired_rows_match(a,list(reversed(a))))
 def fill(self,all_bad=False,many=False):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);book=QuestBook(tmp.name,'test')
  f=np.asarray(Image.open(T/'live/story-list.png')).copy();ys=[156,194,232,271] if many else [156,194]
  for y in ys:f[y-8:y-4,70:150]=255
  ui=object.__new__(m.MissionUI);ui.context=NS(checkpoint=lambda:None,wait=lambda s:None);ui.frame=lambda:f;ui.open=lambda mode:None;ui.wheel=lambda *a:None
  calls=[]
  def selected(mode,y,b,power):
   calls.append(y)
   if all_bad or (y!=156 if many else y==156):raise MissionRowUnreadable('unreadable title')
   return b.observe(mode,'[외전] 확인된 임무1',suitable=True,actionable=True,accepted=True,completed=False)
  ui.selected=selected
  with patch.object(m,'markers',side_effect=lambda f,n,**kw:[] if n=='group-closed' else ys),patch.object(m,'row_signature',side_effect=lambda f,y:str(y)),patch.object(m,'accepted_quota',return_value=10),patch.object(m,'quest_screen',return_value=True):
   if all_bad:
    with self.assertRaises(Pending):ui._pick_legacy(book,'sub_quest',100000,fill=True)
   else:ui._pick_legacy(book,'sub_quest',100000,fill=True)
  return book,calls
 def test_one_unreadable_row_does_not_restart_or_stop_whole_scan(self):
  book,calls=self.fill();self.assertEqual(calls,[156,194]);self.assertEqual(len(book.item['batch']['keys']),1)
  self.assertEqual(book.item['batch']['unreadable_rows'],1);self.assertEqual(book.item['batch']['phase'],'drain')
  self.assertTrue(all(not r.get('completed') for r in book.item['quests'].values()))
 def test_no_readable_rows_never_means_all_complete(self):
  book,calls=self.fill(True);self.assertEqual(book.item['batch']['phase'],'filling');self.assertEqual(book.item['quests'],{})
 def test_three_bad_rows_release_verified_subset_without_false_clear(self):
  book,calls=self.fill(many=True)
  self.assertEqual(calls,[156,194,232,271]);self.assertEqual(len(book.item['batch']['keys']),1)
  self.assertFalse(book.item['batch']['scan_complete']);self.assertEqual(book.item['batch']['unreadable_rows'],3)
  self.assertEqual(book.item['batch']['phase'],'drain')
 def test_actual_auto_button_glyph_and_dim_overlay(self):
  from roi_runtime import RoiDetector
  detector=RoiDetector(A/'profiles/DKB',list(m.AUTO_BUTTONS))
  f=np.asarray(Image.open(T/'live/title-failure-r19.png'))
  self.assertIsNotNone(m.auto_button_hit(detector,f))
  self.assertIsNone(m.auto_button_hit(detector,(f*.55).astype('uint8')))
  self.assertIsNone(m.auto_button_hit(detector,np.zeros_like(f)))
 def test_minor_title_glyph_keeps_active_quest_and_death_record(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a');key=b.observe('sub_quest','[외전] 호랑이의 영촌1',objective='호량이의영혼과대화하기',suitable=True,actionable=True)
   b.activate(key);b.death(key,100000)
   updated=b.observe('sub_quest','[외전] 호랑이의 영혼1',objective='호랑이의영혼과대화하기',suitable=True,actionable=True)
   self.assertEqual(key,updated);self.assertEqual(b.item['active'],key);self.assertEqual(b.item['quests'][key]['deaths'],1)
 def test_different_step_never_reuses_previous_quest_identity(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a');a=b.observe('sub_quest','[외전] 호랑이의 영혼1',objective='호랑이와대화하기')
   c=b.observe('sub_quest','[외전] 호랑이의 영혼2',objective='호랑이와대화하기');self.assertNotEqual(a,c)
 def test_existing_old_variant_cannot_steal_active_identity(self):
  with tempfile.TemporaryDirectory() as directory:
   b=QuestBook(directory,'a')
   a=b.observe('sub_quest','[외전] 호랑이의 영혼1',objective='호랑이의영혼과대화하기')
   # Reproduce duplicate historical records from the earlier OCR reader.
   from owner_mission_policy import quest_key
   active=quest_key('sub_quest','[외전] 호랑이의 영촌1','호량이의영혼과대화하기')
   b.item['quests'][active]={'mode':'sub_quest','title':'[외전] 호랑이의 영촌1','objective':'호량이의영혼과대화하기','deaths':1};b.item['active']=active
   updated=b.observe('sub_quest','[외전] 호랑이의 영혼1',objective='호랑이의영혼과대화하기',suitable=True,actionable=True)
   self.assertEqual(updated,active);self.assertEqual(b.item['quests'][a]['identity_alias_of'],active);self.assertFalse(b.eligible(a,100000))

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Reading))
 (T/'mission_reading_validation.json').write_text(json.dumps({'checks':r.testsRun,'passed':r.wasSuccessful(),'live_game_input':False},indent=2),encoding='utf-8');sys.exit(not r.wasSuccessful())
