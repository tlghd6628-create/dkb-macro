import tempfile,time,unittest,types
from pathlib import Path
from unittest.mock import patch
import bootstrap
# Initialize real reader dependencies before replacing only the state ports.
import owner_energy_generic_port_candidate,owner_energy_nonce_reconcile_candidate
import owner_energy_next_integration_candidate as x
from owner_energy_box_runtime_candidate import Journal
class Context:
 def checkpoint(self):pass
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.ctx=Context();self.p=types.SimpleNamespace(character='c',level=50,observed=time.monotonic());self.a=types.SimpleNamespace(project=types.SimpleNamespace(root=self.root),values={'auto_rewards.inventory_use.enabled':True},_owner_progression_observation=(self.ctx,self.p.observed,'c'))
  self.j=Journal(self.root,'r');self.data=self.j.read();self.data['manual_observations']=[dict(name='생명',quantity=1,balancing_only=True)];self.j.save(self.data)
  self.choices=types.SimpleNamespace(snapshot=lambda:({'version':1,'energy_mode':'balanced','energies':['생명','여명','몽환']},'rev'))
  self.calls=[]
  self.mods={'owner_progression':types.SimpleNamespace(state=lambda a:self.p),'owner_hunt_rules_candidate':types.SimpleNamespace(configured_identity=lambda r:'scope'),'owner_skill_goal':types.SimpleNamespace(runtime_ledger=lambda *a:types.SimpleNamespace(receipt_key='r')),'owner_starter_choice_candidate':types.SimpleNamespace(Choices=lambda *a:self.choices),'owner_energy_next_candidate':types.SimpleNamespace(attempt_next=lambda *a:self.calls.append('trial') or 'trial')}
 def test_pending_first_uses_only_established_recovery(self):
  import owner_energy_box_runtime_candidate as base
  self.data['pending']={'phase':'sent'};self.j.save(self.data)
  with patch.dict('sys.modules',self.mods),patch.object(base,'attempt',side_effect=lambda *a:self.calls.append('old') or 'old'):
   self.assertEqual(x.attempt(self.a,self.ctx,None),'old')
  self.assertEqual(self.calls,['old'])
 def test_after_confirm_routes_to_next_one(self):
  import owner_energy_box_runtime_candidate as base
  from test_energy_batch_runner_candidate import BatchPort
  self.data['confirmed']['여명']=1;self.data['receipts']=[{'proof':'legacy_49_to_48_and_dawn_one'}];self.j.save(self.data)
  port=BatchPort(48);self.a._owner_energy_generic_port_factory=lambda *a:port
  with patch.dict('sys.modules',self.mods),patch.object(base,'attempt',side_effect=AssertionError('not allowed')):
   self.assertEqual(x.attempt(self.a,self.ctx,None),'confirmed')
  self.assertEqual(port.calls,[('생명',16),('여명',16),('몽환',16)])
  self.assertEqual(self.j.read()['confirmed'],{'생명':16,'여명':17,'몽환':16,'홍염':0})
 def test_wrong_context_never_dispatches(self):
  self.a._owner_progression_observation=(object(),self.p.observed,'c')
  with patch.dict('sys.modules',self.mods):self.assertEqual(x.attempt(self.a,self.ctx,None),'character_unknown')
  self.assertEqual(self.calls,[])
 def test_new_nonce_pending_does_not_reopen_inventory(self):
  import owner_energy_box_runtime_candidate as base
  self.data['pending']={'phase':'sent','operation_id':'new-op'};self.j.save(self.data)
  with patch.dict('sys.modules',self.mods),patch.object(base,'attempt',side_effect=AssertionError('must not reopen')):
   self.assertEqual(x.attempt(self.a,self.ctx,None),'new_reward_evidence_pending')
  self.assertEqual(self.calls,[])
 def test_disabled_all_preserves_pending_without_any_ui(self):
  import owner_energy_box_runtime_candidate as base
  self.data['pending']={'phase':'sent','operation_id':'new-op','name':'몽환'};self.j.save(self.data)
  self.choices.snapshot=lambda:({'energies':[]},'rev')
  with patch.dict('sys.modules',self.mods),patch.object(base,'attempt',side_effect=AssertionError('must not open')):
   self.assertEqual(x.attempt(self.a,self.ctx,None),'disabled')
  self.assertEqual(self.calls,[]);self.assertEqual(self.j.read()['pending']['operation_id'],'new-op')
 def test_confirmation_only_reconciles_prior_nonce_without_new_claims(self):
  self.data['pending']={'phase':'sent','operation_id':'a'*32,'name':'생명','quantity':1,'boxes_before':47}
  self.j.save(self.data);self.a._owner_energy_box_reconcile_only=True
  port=types.SimpleNamespace(current_detail=lambda guard:{'count':'fake-proof'},close_known=lambda:self.calls.append('close'))
  self.a._owner_energy_generic_port_factory=lambda *a:port
  def confirm(root,journal,current,**kw):
   value=journal.read();value['pending']=None;value['confirmed']['생명']+=1;journal.save(value);return 'confirmed'
  with patch.dict('sys.modules',self.mods),patch('owner_energy_nonce_reconcile_candidate.reconcile',side_effect=confirm),patch('owner_energy_batch_runner_candidate.run_batched',side_effect=AssertionError('new claim in confirmation-only')):
   self.assertEqual(x.attempt(self.a,self.ctx,None),'confirmed')
  self.assertEqual(self.a._owner_energy_box_outcome['remaining'],46);self.assertTrue(self.a._owner_energy_box_outcome['needs_recheck'])
  self.assertIsNone(self.j.read()['pending'])
 def test_confirmation_only_without_pending_does_not_construct_ui(self):
  self.a._owner_energy_box_reconcile_only=True
  self.a._owner_energy_generic_port_factory=lambda *a:(_ for _ in ()).throw(AssertionError('unneeded UI'))
  with patch.dict('sys.modules',self.mods):self.assertEqual(x.attempt(self.a,self.ctx,None),'nothing_pending')
if __name__=='__main__':unittest.main()
