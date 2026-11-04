"""Fake slider/claim receipts and persisted plans; no OS or game input."""
import tempfile,time,unittest
from pathlib import Path
import bootstrap
from owner_energy_batch_runner_candidate import run_batched
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_allocation_candidate import NAMES

class BatchPort:
 def __init__(self,n=46):self.n=n;self.seq=0;self.calls=[];self.bad=False;self.after_prepare=lambda:None
 def proof(self,**extra):
  self.seq+=1;t=time.monotonic()
  return dict(verified=True,frame_ids=[f'a{self.seq}',f'b{self.seq}'],captured_at=[t-.01,t],**extra)
 def open_selection(self,guard):
  if not guard():raise Hold('guard')
  return self.proof(boxes=self.n,quantity=1)
 def prepare_batch(self,name,quantity,guard):
  if not guard():raise Hold('guard')
  self.before=self.n;self.target=name;self.quantity=quantity
  self.after_prepare();return self.proof(name=name,quantity=quantity,boxes=self.n,detail_boxes=self.n,detail_identity=True)
 def submit(self,final,mark_sent,guard):
  mark_sent();self.calls.append((final['name'],final['quantity']));self.n-=final['quantity']
 def receipt(self,name,guard):
  return self.proof(name=name,quantity=self.quantity+(1 if self.bad else 0),boxes=self.n,toast_verified=True,
   evidence_ids=[f'e{i}-{self.seq}' for i in range(4)],evidence_sha256=['a'*64]*4,evidence_dir='fake')
 def close_known(self):pass

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.tmp.cleanup)
  self.j=Journal(self.tmp.name,'char');d=self.j.read();d['confirmed'].update({'생명':1,'여명':1,'몽환':1})
  d['manual_observations']=[{'name':'생명','quantity':1,'balancing_only':True}];self.j.save(d)
  self.setting={'version':1,'energy_mode':'balanced','energies':list(NAMES[:3])};self.port=BatchPort()
 def call(self,**kwargs):return run_batched(self.port,self.j,self.setting,guard=kwargs.pop('guard',lambda:True),validated_targets=set(NAMES[:3]),**kwargs)
 def test_all46_are_allocated_once_per_selected_kind_and_credited_by_actual_N(self):
  done=self.call();self.assertEqual(self.port.calls,[('생명',16),('여명',15),('몽환',15)])
  self.assertEqual(sum(x['quantity'] for x in done),46);self.assertEqual(self.port.n,0)
  d=self.j.read();self.assertEqual(d['confirmed'],{'생명':17,'여명':16,'몽환':16,'홍염':0})
  self.assertIsNone(d['pending']);self.assertEqual(sum(d['energy_batch_plan']['remaining'].values()),0)
  self.assertIn('energy_ratio_rounding',d)
 def test_partial_plan_survives_new_runner_without_reallocating_the_first_kind(self):
  self.call(max_batches=1);self.assertEqual(self.port.calls,[('생명',16)])
  self.call();self.assertEqual(self.port.calls,[('생명',16),('여명',15),('몽환',15)])
 def test_wrong_quantity_retains_sent_N_and_prevents_next_kind(self):
  self.port.bad=True
  with self.assertRaises(Hold):self.call()
  d=self.j.read();self.assertEqual(d['pending']['phase'],'sent');self.assertEqual(d['pending']['quantity'],16)
  self.assertEqual(d['energy_batch_plan']['remaining']['생명'],16);self.assertEqual(d['confirmed']['생명'],1)
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.port.calls,[('생명',16)])
 def test_unsupported_positive_percentage_holds_before_any_UI(self):
  self.setting={'version':1,'energy_mode':'percent','energies':['홍염'],'energy_percentages':dict(zip(NAMES,['0','0','0','100']))}
  self.port.open_selection=lambda guard:self.fail('UI before supported reward reader')
  with self.assertRaises(Hold):self.call()
  self.assertIsNone(self.j.read()['pending'])
 def test_all_zero_is_disabled_without_UI(self):
  self.setting={'version':1,'energy_mode':'percent','energies':[],'energy_percentages':dict.fromkeys(NAMES,'0')}
  self.port.open_selection=lambda guard:self.fail('disabled UI')
  self.assertEqual(self.call(),[])
 def test_settings_changed_before_submit_sends_no_resource_input(self):
  allowed=[True];self.port.after_prepare=lambda:allowed.__setitem__(0,False)
  with self.assertRaises(Hold):self.call(guard=lambda:allowed[0])
  self.assertEqual(self.port.calls,[]);self.assertIsNone(self.j.read()['pending'])
 def test_observed_remaining_change_does_not_silently_replace_persisted_plan(self):
  self.call(max_batches=1);self.port.n-=1
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.port.calls,[('생명',16)])

if __name__=='__main__':unittest.main()
