"""Starter owned-skill checks use fake UI only; no boxes or game input."""
exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf-8'))
import json,tempfile,time,threading,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import owner_starter_choice_candidate as choice,owner_progression,owner_quest_preflight,owner_skill_ui
from owner_learned_skills_candidate import LearnedSkills
from owner_skill_goal import runtime_ledger

class TestChoices(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'S','character_name':'C'}),encoding='utf8')
  self.adapter=NS(project=NS(root=self.root));self.context=NS(checkpoint=lambda:None,stop=threading.Event())
  self.progress=NS(level=30,character='fingerprint',observed=0.)
 def test_options_zero_one_many_and_revision(self):
  store=choice.Choices(self.root,'profile');data,rev=store.snapshot()
  self.assertEqual(data['energies'],['생명','여명','몽환'])
  store.write(dict(data,energies=[]),rev);updated,revision=store.snapshot();self.assertEqual(updated['energies'],[])
  store.write(dict(updated,energies=['홍염']),revision)
  with self.assertRaises(ValueError):store.write(data,revision)
  choice.Choices.validate({'version':1,'energy_mode':'balanced','energies':['생명','홍염']})
 def test_owned_three_are_recorded_and_reopen_skips_scan(self):
  calls=[]
  def refresh(*_):self.progress.observed=time.monotonic();return True
  ui=NS(scan_owned=lambda:calls.append('scan') or {84,68,89},close_known=lambda:calls.append('close'),skill_rows=lambda:[])
  with patch.object(owner_progression,'state',return_value=self.progress),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(choice,'owned_filter_proved',return_value=True):
   self.assertEqual(choice.scan_learned(self.adapter,self.context,None),'all_known')
   self.assertEqual(choice.scan_learned(self.adapter,self.context,None),'all_known')
  self.assertEqual(calls,['scan','close'])
  ledger=runtime_ledger(self.adapter,self.progress.character);store=LearnedSkills(self.root,ledger.receipt_key)
  self.assertTrue(all(store.known(n) for n in choice.SKILLS))
 def test_absent_skills_not_marked_unlearned_or_box_consumed(self):
  def refresh(*_):self.progress.observed=time.monotonic();return True
  ui=NS(scan_owned=lambda:{84},close_known=lambda:None,skill_rows=lambda:[])
  with patch.object(owner_progression,'state',return_value=self.progress),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(choice,'owned_filter_proved',return_value=True):
   self.assertEqual(choice.scan_learned(self.adapter,self.context,None),'unknown')
  ledger=runtime_ledger(self.adapter,self.progress.character);store=LearnedSkills(self.root,ledger.receipt_key)
  self.assertTrue(store.known('생명의 흐름'));self.assertFalse(store.known('방패 밀기'))
 def test_cleanup_failure_is_not_silently_successful(self):
  def refresh(*_):self.progress.observed=time.monotonic();return True
  ui=NS(scan_owned=lambda:{84},close_known=lambda:(_ for _ in ()).throw(RuntimeError('stuck')),skill_rows=lambda:[])
  with patch.object(owner_progression,'state',return_value=self.progress),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(choice,'owned_filter_proved',return_value=True):
   with self.assertRaises(choice.ChoiceNavigationError):choice.scan_learned(self.adapter,self.context,None)
  self.assertFalse((self.root/'settings/owner-learned-skills.json').exists())
 def test_unproven_owned_filter_does_not_record_any_skill(self):
  from owner_skill_goal import Pending
  def refresh(*_):self.progress.observed=time.monotonic();return True
  ui=NS(scan_owned=lambda:{84,68,89},close_known=lambda:None,skill_rows=lambda:[])
  with patch.object(owner_progression,'state',return_value=self.progress),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(choice,'owned_filter_proved',return_value=False):
   with self.assertRaises(Pending):choice.scan_learned(self.adapter,self.context,None)
  self.assertFalse((self.root/'settings/owner-learned-skills.json').exists())
 def test_saved_skill_icons_identify_without_claiming_filter_or_ownership(self):
  import numpy as np
  from PIL import Image
  from owner_skill_goal import Pending
  p=Path(__file__).parent/'live_fixtures'
  frames=[np.asarray(Image.open(p/f'skill_list_20261101_{suffix}.jpg').convert('RGB'))[31:510,1:898,:] for suffix in ('a','b')]
  found={sid for sid,y in choice.positive_skill_icons(*frames)}
  self.assertTrue({84,89}.issubset(found))
  ui=NS(skill_rows=lambda:[],frame=lambda:frames[0].copy(),context=NS(wait=lambda *_:None))
  choice._enable_owned_icon_fallback(ui)
  with patch.object(choice,'owned_filter_proved',return_value=False):
   with self.assertRaises(Pending):ui.skill_rows()
 def test_original_owned_filter_paired_and_checked_rejected(self):
  import numpy as np
  from PIL import Image
  p=Path(__file__).parent/'live_fixtures'
  a,b=[np.asarray(Image.open(p/f'skill_owned_filter_native_{i}.png').convert('RGB')) for i in (1,2)]
  frames=iter((a,b));ui=NS(frame=lambda:next(frames),context=NS(wait=lambda *_:None))
  self.assertTrue(choice.owned_filter_proved(ui))
  self.assertTrue({84,89}.issubset({sid for sid,_ in choice.positive_skill_icons(a,b)}))
  checked=owner_skill_ui.asset('skill-checked-all');replaced=a.copy();h,w=checked.shape[:2]
  replaced[57:57+h,687:687+w]=checked
  ui.frame=lambda:replaced
  self.assertFalse(choice.owned_filter_proved(ui))
 def test_three_proved_skills_stop_owned_scan_without_scanning_rest(self):
  pages=iter([[{'id':84,'y':100},{'id':89,'y':150}],[{'id':68,'y':200}]])
  ui=NS(skill_rows=lambda:next(pages),frame=lambda:None,context=NS(wait=lambda *_:None),_owner_last_rows_pair=([None,None],None,None))
  choice._enable_owned_icon_fallback(ui)
  with patch.object(choice,'owned_filter_proved',return_value=True),patch.object(choice,'owned_filter_frame',return_value=True),patch.object(choice,'positive_skill_icons',return_value=[]):
   self.assertEqual({r['id'] for r in ui.skill_rows()},{84,89})
   with self.assertRaises(choice._RequiredSkillsFound) as result:ui.skill_rows()
  self.assertEqual(result.exception.owned,{68,84,89})
 def test_filter_change_on_skill_frames_rejects_rows(self):
  from owner_skill_goal import Pending
  ui=NS(skill_rows=lambda:[{'id':84,'y':100}],frame=lambda:None,context=NS(wait=lambda *_:None),_owner_last_rows_pair=([None,None],None,None))
  choice._enable_owned_icon_fallback(ui)
  with patch.object(choice,'owned_filter_proved',return_value=True),patch.object(choice,'owned_filter_frame',return_value=False):
   with self.assertRaises(Pending):ui.skill_rows()
 def test_old_positive_entries_without_owned_filter_attestation_are_rechecked(self):
  from owner_skill_goal import Pending
  ledger=runtime_ledger(self.adapter,self.progress.character);old=LearnedSkills(self.root,ledger.receipt_key)
  for name in choice.SKILLS:old.observed(name,verified=True)
  calls=[]
  def refresh(*_):self.progress.observed=time.monotonic();return True
  ui=NS(scan_owned=lambda:calls.append('scan') or {84,68,89},close_known=lambda:None,skill_rows=lambda:[])
  with patch.object(owner_progression,'state',return_value=self.progress),patch.object(owner_quest_preflight,'read_power',side_effect=refresh),patch.object(owner_skill_ui,'SkillUI',return_value=ui),patch.object(choice,'owned_filter_proved',return_value=False):
   with self.assertRaises(Pending):choice.scan_learned(self.adapter,self.context,None)
  self.assertEqual(calls,['scan']);self.assertFalse(choice.SkillAttestation(self.root,ledger.receipt_key).known())
 def test_balancing_uses_only_confirmed_acquisitions_and_retains_history(self):
  book=choice.EnergyLedger(self.root,'profile|fingerprint')
  self.assertIsNone(book.next([]));self.assertEqual(book.next(['생명','여명','몽환']),'생명')
  book.begin('생명',{'verified':True,'owned':10,'boxes':2,'frame_ids':['a','b'],'captured_at':time.time()})
  with self.assertRaises(ValueError):book.next(['생명','여명','몽환'])
  with self.assertRaises(ValueError):book.confirm({'verified':True,'name':'생명','owned':10,'boxes':1,'frame_ids':['c','d'],'receipt':True,'captured_at':time.time()})
  self.assertEqual(book.confirm({'verified':True,'name':'생명','owned':20,'boxes':1,'frame_ids':['c','d'],'receipt':True,'captured_at':time.time()}),10)
  self.assertEqual(book.next(['생명','여명','몽환']),'여명')
  # Removing and re-adding a choice never destroys earlier counts.
  self.assertEqual(book.next(['홍염']),'홍염');self.assertEqual(book.read()['confirmed']['생명'],10)
  with self.assertRaises(ValueError):book.begin('여명',{'verified':True,'owned':1,'boxes':1,'frame_ids':['c','d'],'captured_at':time.time()})
 def test_receipts_are_scoped_and_never_accept_unverified_after(self):
  one=choice.EnergyLedger(self.root,'profile|a');other=choice.EnergyLedger(self.root,'profile|b')
  one.begin('몽환',{'verified':True,'owned':0,'boxes':1,'frame_ids':['a','b'],'captured_at':time.time()})
  with self.assertRaises(ValueError):one.confirm({'verified':False,'name':'몽환','owned':1,'boxes':0,'frame_ids':['c','d'],'receipt':True,'captured_at':time.time()})
  self.assertEqual(other.read()['confirmed']['몽환'],0)
 def test_install_wraps_native_inventory_without_replacing_original(self):
  from project_adapter import market_inventory
  from project_adapter._entry import Adapter
  original_module=market_inventory.run_inventory_use;original_method=Adapter.run_inventory_use;calls=[]
  def native(*_args,**_kwargs):calls.append('native');return True
  try:
   market_inventory.run_inventory_use=native
   Adapter.run_inventory_use=lambda adapter,context,inputs:market_inventory.run_inventory_use(adapter,context,inputs)
   with patch.object(choice,'scan_learned',side_effect=lambda *_:calls.append('scan')):
    choice.install(NS());self.assertTrue(Adapter.run_inventory_use(self.adapter,self.context,None))
   self.assertEqual(calls,['native','scan'])
  finally:
   market_inventory.run_inventory_use=original_module;Adapter.run_inventory_use=original_method
 def test_timetable_skipped_inventory_never_starts_followup_scan(self):
  from project_adapter import market_inventory
  from project_adapter._entry import Adapter
  original_module=market_inventory.run_inventory_use;original_method=Adapter.run_inventory_use
  def skipped(adapter,*_):adapter._owner_inventory_skip_generation=getattr(adapter,'_owner_inventory_skip_generation',0)+1;return True
  try:
   market_inventory.run_inventory_use=skipped
   Adapter.run_inventory_use=lambda adapter,context,inputs:market_inventory.run_inventory_use(adapter,context,inputs)
   with patch.object(choice,'scan_learned') as scan:
    choice.install(NS());self.assertTrue(Adapter.run_inventory_use(self.adapter,self.context,None));scan.assert_not_called()
  finally:market_inventory.run_inventory_use=original_module;Adapter.run_inventory_use=original_method
if __name__=='__main__':unittest.main(verbosity=2)
