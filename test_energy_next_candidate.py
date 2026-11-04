import tempfile,time,unittest
from pathlib import Path
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_next_candidate import run_next_trial
class Port:
 def __init__(self):self.actions=[]
 def prepare_one(self,name,guard):
  self.actions.append(('select',name));t=time.monotonic();return dict(verified=True,name=name,quantity=1,boxes=48,detail_boxes=48,frame_ids=['a','b'],captured_at=[t-.01,t])
 def submit(self,final,mark_sent,guard):mark_sent();self.actions.append(('submit',final['name']))
 def receipt(self,name,guard):self.actions.append(('capture',name));return None
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.temp.cleanup);self.j=Journal(self.temp.name,'same');s=self.j.read();s['confirmed']['여명']=1;s['manual_observations']=[dict(name='생명',quantity=1,balancing_only=True)];self.j.save(s);self.p=Port()
 def test_dream_is_first_and_pending_prevents_repeat(self):
  with self.assertRaises(Hold):run_next_trial(self.p,self.j,['생명','여명','몽환'],guard=lambda:True)
  self.assertEqual(self.p.actions,[('select','몽환'),('submit','몽환'),('capture','몽환')]);pending=self.j.read()['pending'];self.assertEqual(pending['phase'],'sent');self.assertEqual(pending['name'],'몽환');self.assertTrue(pending['operation_id'])
  with self.assertRaises(Hold):run_next_trial(self.p,self.j,['생명','여명','몽환'],guard=lambda:True)
  self.assertEqual(len(self.p.actions),3)
 def test_unchecked_crimson_never_used(self):
  s=self.j.read();s['confirmed']['몽환']=1;self.j.save(s)
  with self.assertRaises(Hold):run_next_trial(self.p,self.j,['생명','여명','몽환'],guard=lambda:True)
  self.assertEqual(self.p.actions,[('select','생명'),('submit','생명'),('capture','생명')])
  self.assertNotIn(('select','홍염'),self.p.actions)
 def test_wrong_quantity_blocks(self):
  old=self.p.prepare_one
  def bad(*a,**k):v=old(*a,**k);v['quantity']=2;return v
  self.p.prepare_one=bad
  with self.assertRaises(Hold):run_next_trial(self.p,self.j,['생명','여명','몽환'],guard=lambda:True)
  self.assertEqual(len(self.p.actions),1);self.assertIsNone(self.j.read()['pending'])
if __name__=='__main__':unittest.main()
