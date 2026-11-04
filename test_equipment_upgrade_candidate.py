import bootstrap
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
import owner_equipment_upgrade_candidate as upgrade

class EquipUpgrade(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.journal=upgrade.Journal(Path(self.tmp.name),'character-A');self.clicks=[]
  self.context=NS(checkpoint=lambda:None)
 def pair(self,**changes):
  common={'verified':True,'character':'character-A','slot':'반지','current_item':'일반 반지 ID',
          'current_grade':'일반','candidate_item':'희귀 반지 ID','candidate_grade':'희귀',
          'target_bounds':[400,400,440,430],**changes}
  return dict(common,frame_id='a',captured_at=99.6),dict(common,frame_id='b',captured_at=99.8)
 def attempt(self,pair=None,final=True,context=None):
  return upgrade.run_once(context or self.context,self.journal,lambda:pair or self.pair(),lambda _:final,
                          lambda bounds:self.clicks.append(bounds),clock=lambda:100)
 def result(self,item='희귀 반지 ID'):
  common=dict(verified=True,character='character-A',slot='반지',item=item,grade='희귀',worn=True)
  return dict(common,frame_id='c',captured_at=100.2),dict(common,frame_id='d',captured_at=100.3)
 def test_actual_one_click_then_fresh_worn_evidence(self):
  self.assertEqual(self.attempt(),'pending_confirmation');self.assertEqual(len(self.clicks),1)
  with self.assertRaises(upgrade.Hold):self.attempt()
  with self.assertRaises(upgrade.Hold):upgrade.confirm(self.context,self.journal,lambda:self.result('잘못된 반지'),clock=lambda:101)
  self.assertEqual(upgrade.confirm(self.context,self.journal,self.result,clock=lambda:101),'confirmed')
  self.assertIsNone(self.journal.read()['pending'])
 def test_only_general_to_exact_rare_and_same_slot(self):
  for changes in ({'current_grade':'희귀'},{'candidate_grade':'영웅'},{'candidate_grade':'희귀 이상'},
                  {'current_grade':None},{'candidate_grade':None},{'slot':'알수없음'}):
   with self.subTest(changes=changes),self.assertRaises(upgrade.Hold):self.attempt(self.pair(**changes))
  a,b=self.pair();b['slot']='팔찌'
  with self.assertRaises(upgrade.Hold):self.attempt((a,b))
  self.assertEqual(self.clicks,[])
 def test_power_decrease_does_not_change_approved_policy(self):
  self.assertEqual(self.attempt(self.pair(current_power=1000,candidate_power=100)),'pending_confirmation')
 def test_matching_names_do_not_reject_an_independently_proved_rare_candidate(self):
  self.assertEqual(self.attempt(self.pair(candidate_item='일반 반지 ID')),'pending_confirmation')
 def test_missing_or_changed_proof_never_clicks_and_prepared_clears(self):
  with self.assertRaises(upgrade.Hold):self.attempt(final=False)
  self.assertEqual(self.clicks,[]);self.assertIsNone(self.journal.read()['pending'])
  a,b=self.pair();b['candidate_item']='다른 희귀 반지'
  with self.assertRaises(upgrade.Hold):self.attempt((a,b))
 def test_interruption_after_mark_sent_remains_pending_across_restart(self):
  checks=[]
  def checkpoint():
   checks.append(1)
   if len(checks)==4:raise RuntimeError('stop')
  with self.assertRaises(RuntimeError):self.attempt(context=NS(checkpoint=checkpoint))
  self.assertEqual(self.journal.read()['pending']['phase'],'sent')
  with self.assertRaises(upgrade.Hold):self.attempt()
  self.assertEqual(self.clicks,[])
 def test_old_or_reused_result_frames_do_not_confirm(self):
  self.attempt();a,b=self.result();a['frame_id']='a'
  with self.assertRaises(upgrade.Hold):upgrade.confirm(self.context,self.journal,lambda:(a,b),clock=lambda:101)
  self.assertEqual(self.journal.read()['pending']['phase'],'sent')
 def test_initial_equipment_requires_two_empty_proofs_and_explicit_allowlist(self):
  def pair(**kwargs):
   v={'verified':True,'character':'character-A','slot':'반지','empty':True,
      'candidate_item':'허용 반지','candidate_grade':'일반','target_bounds':[400,400,440,430],**kwargs}
   return dict(v,frame_id='a',captured_at=99.6),dict(v,frame_id='b',captured_at=99.8)
  permitted={('반지','허용 반지')}
  for params,allowed in [({'empty':False},permitted),({'candidate_grade':'영웅'},permitted),({},set()),({}, {('반지','다른 장비')})]:
   with self.subTest(params=params,allowed=allowed),self.assertRaises(upgrade.Hold):upgrade.paired_initial(*pair(**params),allowed_items=allowed,clock=lambda:100)
  result=upgrade.run_once(self.context,self.journal,pair,lambda _:True,lambda b:self.clicks.append(b),clock=lambda:100,initial_allowed=permitted)
  self.assertEqual(result,'pending_confirmation');self.assertEqual(len(self.clicks),1)
  def result_pair():
   common=dict(verified=True,character='character-A',slot='반지',item='허용 반지',grade='일반',worn=True)
   return dict(common,frame_id='c',captured_at=100.2),dict(common,frame_id='d',captured_at=100.3)
  self.assertEqual(upgrade.confirm(self.context,self.journal,result_pair,clock=lambda:101),'confirmed')
 def test_category_confirmation_does_not_claim_instance_identity(self):
  self.attempt()
  def rows(slot='반지',grade='희귀'):
   common=dict(verified=True,character='character-A',slot=slot,grade=grade,worn=True)
   return dict(common,frame_id='c',captured_at=100.2),dict(common,frame_id='d',captured_at=100.3)
  with self.assertRaises(upgrade.Hold):upgrade.confirm_category(self.context,self.journal,lambda:rows(slot='팔찌'),clock=lambda:101)
  with self.assertRaises(upgrade.Hold):upgrade.confirm_category(self.context,self.journal,lambda:rows(grade='영웅'),clock=lambda:101)
  self.assertEqual(upgrade.confirm_category(self.context,self.journal,rows,clock=lambda:101),'confirmed_category')
  self.assertEqual(self.journal.read()['completed'][0]['verified_as'],'slot_and_grade')
  request=self.journal.growth_request();self.assertEqual(request['result_frame_ids'],['c','d'])
  self.journal.mark_growth_dispatched(request['growth_request_id']);self.assertIsNone(self.journal.growth_request())

if __name__=='__main__':unittest.main(verbosity=2)
