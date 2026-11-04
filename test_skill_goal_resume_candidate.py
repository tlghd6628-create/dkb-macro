import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from unittest.mock import patch
from owner_skill_goal import Ledger,Pending,complete_requested_aoe,aoe_matches_request,desired_learning_ids,eligible
from owner_aoe_preset_candidate import SLOTS,ORDER

class UI:
 def __init__(self,owned):self.owned=owned;self.scans=0
 def scan_owned(self):self.scans+=1;return self.owned
 def close_known(self):pass
 def purchase_required_and_learn(self,ledger):raise Pending('missing verified shop')

class GoalResume(unittest.TestCase):
 def test_purchase_intent_flushes_before_becoming_visible(self):
  import os
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5)
   real_fsync=os.fsync
   with patch('owner_skill_goal.os.fsync',wraps=real_fsync) as synced:
    self.assertTrue(ledger.begin_purchase('39',{'currency':'엽전','price':10000,'bundles':1,'fragments':100,'item':'쇠뇌 사격'}))
    self.assertGreaterEqual(synced.call_count,1)
   self.assertEqual(Ledger(root,'A').item['purchases']['39']['status'],'intent')
 def test_skill_goal_remains_eligible_above_level_50(self):
  from types import SimpleNamespace
  for level in (50,51,75):
   self.assertTrue(eligible(SimpleNamespace(character='A',level=level,power=None),{'stage':'story'}))
  for level in (None,49,True):
   self.assertFalse(eligible(SimpleNamespace(character='A',level=level,power=None),{'stage':'story'}))
 def test_already_learned_skills_never_purchase_and_saved_goal_skips_repeat(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5);ledger.save()
   ui=UI(desired_learning_ids()|set(SLOTS)|{65});calls=[]
   def preset(module,ui,ledger,**kwargs):
    calls.append(kwargs['character']);ledger.preset_receipt('aoe',list(SLOTS),list(ORDER));return True
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate',side_effect=preset):
    self.assertTrue(complete_requested_aoe(ui,ledger,'A',lambda:None))
    self.assertEqual(calls,['A']);self.assertEqual(ui.scans,1)
    reloaded=Ledger(root,'A')
    self.assertTrue(complete_requested_aoe(ui,reloaded,'A',lambda:None))
    self.assertEqual(calls,['A']);self.assertEqual(ui.scans,1)
   self.assertTrue(aoe_matches_request(reloaded.item))
 def test_missing_skill_or_wrong_character_never_configures(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5)
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate') as configure:
    with self.assertRaises(Pending):complete_requested_aoe(UI(set(SLOTS)-{59}),ledger,'A',lambda:None)
    with self.assertRaises(Pending):complete_requested_aoe(UI(desired_learning_ids()|set(SLOTS)|{65}),ledger,'B',lambda:None)
    configure.assert_not_called()
 def test_ultimate_can_be_verified_after_placing_its_style_slots(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5)
   ui=UI(desired_learning_ids()|set(SLOTS))
   def configure(module,ui,ledger,**kwargs):
    ledger.preset_receipt('aoe',list(SLOTS),list(ORDER));return True
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate',side_effect=configure):
    self.assertTrue(complete_requested_aoe(ui,ledger,'A',lambda:None))
   self.assertTrue(aoe_matches_request(ledger.item))
   self.assertNotIn(65,desired_learning_ids())
 def test_failed_order_never_records_done(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='presets',story_step=5,learning_ids=sorted(desired_learning_ids()))
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate',side_effect=Pending('order')):
    with self.assertRaises(Pending):complete_requested_aoe(UI(set()),ledger,'A',lambda:None)
   self.assertEqual(ledger.item['stage'],'presets');self.assertFalse(aoe_matches_request(ledger.item))
 def test_no_bulk_or_preset_before_final_story_receipt(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=4)
   ui=UI(set(SLOTS)|{65})
   with self.assertRaises(Pending):complete_requested_aoe(ui,ledger,'A',lambda:None)
   self.assertEqual(ui.scans,0)
 def test_partial_learning_can_finish_aoe_without_claiming_all_styles_or_editing_again(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5);ledger.save()
   ui=UI(set(SLOTS)|{65})
   ui.purchase_required_and_learn=lambda ledger:{'status':'partial','aoe_ready':True,'unresolved':['금전 구매 대기']}
   calls=[]
   def configure(module,ui,ledger,**kwargs):
    calls.append(1);ledger.preset_receipt('aoe',list(SLOTS),list(ORDER));return True
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate',side_effect=configure):
    self.assertTrue(complete_requested_aoe(ui,ledger,'A',lambda:None))
    self.assertEqual(ledger.item['stage'],'learning_pending');self.assertEqual(ledger.item['status'],'partial')
    self.assertNotIn('learning_ids',ledger.item)
    reloaded=Ledger(root,'A')
    self.assertTrue(complete_requested_aoe(ui,reloaded,'A',lambda:None))
    self.assertEqual(calls,[1]);self.assertTrue(aoe_matches_request(reloaded.item))
 def test_purchase_pending_still_applies_owned_aoe_after_cleanup(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5);ledger.save()
   ui=UI(set(SLOTS)|{65});ui.closed=0
   def close():ui.closed+=1
   ui.close_known=close
   def configure(module,ui,ledger,**kwargs):ledger.preset_receipt('aoe',list(SLOTS),list(ORDER));return True
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate',side_effect=configure):
    self.assertTrue(complete_requested_aoe(ui,ledger,'A',lambda:None))
   self.assertEqual(ui.closed,1);self.assertEqual(ui.scans,2)
   self.assertEqual(ledger.item['stage'],'learning_pending');self.assertEqual(ledger.item['requested_learning']['status'],'partial')
   self.assertIn('missing verified shop',ledger.item['requested_learning']['reason'])
   self.assertNotIn('learning_ids',ledger.item)
 def test_unrecognized_cleanup_never_resumes_or_records_preset(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A');ledger.item.update(stage='purchase',story_step=5)
   ui=UI(set(SLOTS)|{65})
   def close():raise Pending('unknown dialog')
   ui.close_known=close
   with patch('owner_aoe_skill_bridge_candidate.attempt_live_candidate') as configure:
    with self.assertRaises(Pending):complete_requested_aoe(ui,ledger,'A',lambda:None)
    configure.assert_not_called()
 def test_scoped_receipts_separate_servers_and_do_not_adopt_old_unscoped_clear(self):
  with tempfile.TemporaryDirectory() as root:
   old=Ledger(root,'same-name-hash');old.item.update(story_step=5,stage='done');old.save()
   one=Ledger(root,'same-name-hash',scope='server-1');one.item['story_step']=5;one.save()
   two=Ledger(root,'same-name-hash',scope='server-2')
   self.assertEqual(two.item['story_step'],0)
   self.assertEqual(Ledger(root,'same-name-hash',scope='server-1').item['story_step'],5)
   self.assertEqual(Ledger(root,'same-name-hash').item['story_step'],5)
 def test_single_preset_receipt_no_longer_authorized(self):
  with tempfile.TemporaryDirectory() as root:
   ledger=Ledger(root,'A')
   with self.assertRaises(ValueError):ledger.preset_receipt('single',list(SLOTS),list(ORDER))

class StoryClearReading(unittest.TestCase):
 def test_exact_final_selected_leaf_requires_two_completion_frames(self):
  import owner_skill_ui as module
  from owner_skill_ui import SkillUI
  from types import SimpleNamespace
  for second,expected in ((False,False),(True,True)):
   with tempfile.TemporaryDirectory() as root:
    ledger=Ledger(root,'A');frames=iter(['first','second'])
    ui=SimpleNamespace(open_story=lambda:None,select_story=lambda n:self.assertEqual(n,5),
      frame=lambda:next(frames),context=SimpleNamespace(wait=lambda x:None))
    def match(frame,name,*args):
     if name=='story-title5':return (1,1,())
     return (1,1,()) if frame=='first' or second else None
    with patch.object(module,'quest_screen',return_value=True),patch.object(module,'match',side_effect=match),patch.object(module,'selected_quest_box',return_value=(40,200,615,30)):
     self.assertEqual(SkillUI.confirm_final_story(ui,ledger),expected)
    self.assertEqual(ledger.item['story_step'],5 if expected else 0)

if __name__=='__main__':unittest.main()

