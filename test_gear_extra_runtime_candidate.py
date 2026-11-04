"""Saved-frame rejection and fake-input extra routing; no live game input."""
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import replace
from unittest.mock import patch,Mock
import tempfile,time,unittest
import numpy as np
from PIL import Image
import bootstrap
from owner_gear_awaken_reader_candidate import parse_explicit_stage
from owner_gear_extra_runtime_candidate import tab_selected,same_static,ExtraObserver
from owner_gear_native_install_candidate import wrap,wrap_extras_decorator
from owner_gear_settings_candidate import Store
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_decision_candidate import Observation


class Context:
 def checkpoint(self):pass
 def wait(self,n):pass


class Tests(unittest.TestCase):
 def test_explicit_label_pair_only(self):
  for kind,text,current in [('awaken','각성0≫각성1',0),('breakthrough','돌파 1 → 돌파 2',1),('awaken','1각성 > 2각성',1)]:
   result=parse_explicit_stage([{'text':text,'score':.98}],kind)
   self.assertEqual(result['current'],current);self.assertEqual(result['next'],current+1)
 def test_never_infers_zero_or_accepts_counter_as_stage(self):
  for text in ['각성≫각성+','0/1','강화50','각성1→각성3','각성0→돌파1']:
   self.assertIsNone(parse_explicit_stage([{'text':text,'score':.99}],'awaken'))
  self.assertIsNone(parse_explicit_stage([{'text':'각성0→각성1','score':.94}],'awaken'))
 def test_ambiguous_duplicate_stage_does_not_authorize(self):
  rows=[{'text':'각성0→각성1','score':.99},{'text':'각성1→각성2','score':.99}]
  self.assertIsNone(parse_explicit_stage(rows,'awaken'))
 def test_real_saved_awaken_tab_and_wrong_tab(self):
  f=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/gear_awaken_hat_native_1.png').convert('RGB'))
  self.assertTrue(tab_selected(f,'awaken'));self.assertFalse(tab_selected(f,'breakthrough'))
  self.assertFalse(tab_selected(np.zeros_like(f),'awaken'))
 def test_static_label_change_invalidates_revalidated_evidence(self):
  first=np.zeros((479,897,3),np.uint8);first[130:139,350:365]=220
  second=first.copy();self.assertTrue(same_static(first,second))
  second[131,354]=0;self.assertFalse(same_static(first,second))
  second=first.copy();second[250,600]=255;self.assertTrue(same_static(first,second))
 def setup_scope(self):
  t=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(t.cleanup)
  root=Path(t.name);ctx=Context();service=NS(context=ctx,check=lambda:None,adapter=NS(project=NS(root=root)))
  store=Store(root,'character');doc=store.read();doc['grades']['희귀'].update(enabled=True,enhance=50,awaken=1,breakthrough=3);store.write(doc)
  intent=IntentStore(store.path.with_name(store.path.stem+'-intent.json'))
  return root,ctx,service,intent
 def pending(self,intent,kind,slot='growth-slot:1'):
  before=Observation(1,10.,'character','icon:saved',slot,'희귀',50,0,0,None,None,None)
  intent.begin({'kind':kind,'before':before,'second':replace(before,sequence=2,captured_at=10.1)})
  intent.mark_sent();return before
 def test_blessing_pending_routes_to_blessing_only(self):
  root,ctx,service,intent=self.setup_scope();self.pending(intent,'enhance','blessing:1');service.adapter._owner_growth_reconcile_only=True
  calls=[]
  def blessing(*args,**kwargs):
   self.assertTrue(kwargs['reconcile_only']);calls.append('blessing');intent.complete('observed_progress');return False
  fn=wrap(lambda *a,**kw:self.fail('native batch'),lambda s:'character',lambda *a:self.fail('gear read'),blessing_runner=blessing)
  with patch('owner_gear_native_install_candidate.pending_readers_factory',side_effect=AssertionError('wrong item type')):
   self.assertTrue(fn(service))
  self.assertEqual(calls,['blessing']);self.assertIsNone(intent.pending())
 def test_extra_pending_never_routes_to_enhancement_reader(self):
  root,ctx,service,intent=self.setup_scope();self.pending(intent,'awaken');service.adapter._owner_growth_reconcile_only=True
  with patch('owner_gear_native_install_candidate.pending_readers_factory',side_effect=AssertionError('enhance reader')):
   result=wrap(lambda *a,**k:self.fail('native'),lambda s:'character',None)(service)
  self.assertFalse(result);self.assertIsNotNone(intent.pending())
 def test_restart_extra_reconciles_without_new_action(self):
  root,ctx,service,intent=self.setup_scope();self.pending(intent,'breakthrough');service.adapter._owner_growth_reconcile_only=True
  calls=[];post=lambda:None
  def factory(*a):self.fail('new extra')
  def resume(*a,**kw):calls.append('resume');return lambda:None,lambda *a:False,lambda:calls.append('cleanup'),post
  factory.resume_pending=resume
  def reconcile(*a,**kw):
   self.assertIs(a[3],post);intent.complete('observed_progress');return 'observed_progress'
  fn=wrap_extras_decorator(lambda f:f,lambda s:'character',factory)(lambda *a:self.fail('new enhance'))
  with patch('owner_gear_native_install_candidate.reconcile_configured_step',side_effect=reconcile),patch('owner_gear_native_install_candidate.run_configured_step',side_effect=AssertionError('resource input')):
   self.assertTrue(fn(service))
  self.assertEqual(calls,['resume','cleanup']);self.assertIsNone(intent.pending())
 def test_unknown_restart_result_retains_pending_and_cleans(self):
  root,ctx,service,intent=self.setup_scope();self.pending(intent,'awaken');service.adapter._owner_growth_reconcile_only=True
  cleanup=Mock();factory=Mock();factory.resume_pending=Mock(return_value=(lambda:None,lambda *a:False,cleanup,lambda:None))
  fn=wrap_extras_decorator(lambda f:f,lambda s:'character',factory)(Mock())
  with patch('owner_gear_native_install_candidate.reconcile_configured_step',return_value='hold_result_unknown'),patch('owner_gear_native_install_candidate.run_configured_step',side_effect=AssertionError('resource input')):
   self.assertFalse(fn(service))
  cleanup.assert_called_once();self.assertEqual(intent.pending()['phase'],'sent');self.assertTrue(service.adapter._owner_growth_pending_hold)
 @__import__('unittest.mock',fromlist=['patch']).patch('owner_growth_reading.BREAKTHROUGH_ENABLED',True)
 def test_explicit_lower_game_cap_is_reported_without_claiming_requested_target(self):
  root,ctx,service,intent=self.setup_scope()
  class Reader:
   last_pair=({'maximum':True,'current':1},None,10)
   def read(self):return {'screen_proof':False}
  reader=Reader()
  def factory(s,c,i,targets,kind):
   return (reader.read,lambda *a:False,lambda:None,reader.read) if kind=='breakthrough' else None
  fn=wrap_extras_decorator(lambda f:f,lambda s:'character',factory)(lambda *a:True)
  with patch('owner_gear_native_install_candidate.run_configured_step',return_value='hold_policy'):
   self.assertTrue(fn(service))
  self.assertEqual(service.adapter._owner_gear_extra_outcome['status'],'game_cap_reached')
  self.assertEqual(service.adapter._owner_gear_extra_outcome['game_cap'],1)
  self.assertEqual(Store(root,'character').read()['grades']['희귀']['breakthrough'],3)
  self.assertIsNone(intent.pending())


if __name__=='__main__':unittest.main()
