import tempfile,time,unittest
from pathlib import Path
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_balanced_runner_candidate import run_balanced,abort_own_prepared
class Port:
 def __init__(self):self.n=48;self.seq=0;self.calls=[];self.bad=False
 def prepare_one(self,name,guard):
  self.seq+=1;self.calls.append(name);t=time.monotonic();return dict(verified=True,name=name,quantity=1,boxes=self.n,detail_boxes=None,detail_identity=True,frame_ids=[f'a{self.seq}',f'b{self.seq}'],captured_at=[t-.01,t])
 def submit(self,final,mark_sent,guard):mark_sent();self.n-=1
 def close_known(self):pass
 def receipt(self,name,guard):
  t=time.monotonic();return dict(verified=True,name='다름' if self.bad else name,quantity=1,boxes=self.n,toast_verified=True,frame_ids=[f'c{self.seq}',f'd{self.seq}'],captured_at=[t-.01,t],evidence_ids=[f'e{i}-{self.seq}' for i in range(4)],evidence_sha256=['a'*64]*4,evidence_dir='test')
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.temp.cleanup);self.j=Journal(self.temp.name,'profile');v=self.j.read();v['confirmed']['여명']=1;v['manual_observations']=[dict(name='생명',quantity=1,balancing_only=True)];self.j.save(v);self.p=Port()
 def test_three_max_equal(self):
  done=run_balanced(self.p,self.j,['생명','여명','몽환'],guard=lambda:True,validated_targets={'생명','여명','몽환'})
  self.assertEqual(done,['몽환','생명','여명']);self.assertEqual(len(self.p.calls),3);self.assertNotIn('홍염',self.p.calls)
 def test_missing_reader_never_submits(self):
  with self.assertRaises(Hold):run_balanced(self.p,self.j,['생명','여명','몽환'],guard=lambda:True,validated_targets={'여명'})
  self.assertEqual(self.p.calls,[]);self.assertIsNone(self.j.read()['pending'])
 def test_mismatch_retains_pending(self):
  self.p.bad=True
  with self.assertRaises(Hold):run_balanced(self.p,self.j,['생명','여명','몽환'],guard=lambda:True,validated_targets={'생명','여명','몽환'})
  self.assertEqual(self.j.read()['pending']['phase'],'sent');self.assertEqual(self.j.read()['confirmed']['몽환'],0)
 def test_preinput_stop_audits_prepared_without_claiming_a_receipt(self):
  class Stop(BaseException):pass
  self.p.submit=lambda *a,**k:(_ for _ in ()).throw(Stop())
  with self.assertRaises(Stop):run_balanced(self.p,self.j,['생명','여명','몽환'],guard=lambda:True,validated_targets={'생명','여명','몽환'})
  state=self.j.read();self.assertIsNone(state['pending']);self.assertEqual(state['confirmed']['몽환'],0)
  self.assertEqual(state['receipts'][-1]['result'],'preinput_aborted');self.assertEqual(state['receipts'][-1]['quantity'],0)
 def test_own_prepared_restart_is_audited_but_sent_and_legacy_never_cleared(self):
  expected={'phase':'prepared','protocol':'energy-balanced-v2','operation_id':'a'*32,'name':'생명','quantity':1,'boxes_before':46,'before_frame_ids':['a','b']}
  state=self.j.read();state['pending']=expected;self.j.save(state)
  self.assertTrue(abort_own_prepared(self.j,expected));self.assertIsNone(self.j.read()['pending'])
  for patch in ({'phase':'sent'},{'protocol':'unknown'}):
   bad=dict(expected,**patch);state=self.j.read();state['pending']=bad;self.j.save(state)
   self.assertFalse(abort_own_prepared(self.j,bad));self.assertEqual(self.j.read()['pending'],bad)
if __name__=='__main__':unittest.main()
