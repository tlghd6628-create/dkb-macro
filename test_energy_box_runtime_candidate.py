import tempfile,time,unittest
from pathlib import Path
from owner_energy_box_runtime_candidate import Journal,Hold,run,choose,fresh_character
from types import SimpleNamespace as NS
class Port:
 def __init__(self):self.actions=[];self.valid=True
 def prepare_one(self,name,guard):
  self.actions.append(('select',name));t=time.monotonic();return dict(verified=True,name=name,quantity=1,boxes=49,detail_boxes=49,frame_ids=['a','b'],captured_at=[t-.01,t])
 def submit(self,before,mark_sent,guard):mark_sent();self.actions.append(('submit',before['name']))
 def receipt(self,name,guard):
  t=time.monotonic();return dict(verified=True,name=name,quantity=1,boxes=48 if self.valid else 49,toast_verified=True,frame_ids=['c','d'],captured_at=[t-.01,t])
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.tmp.cleanup);self.j=Journal(self.tmp.name,'s|c');self.p=Port()
 def test_balancing(self):
  d=self.j.read();d['manual_observations']=[dict(name='생명',quantity=1,balancing_only=True)];self.j.save(d)
  self.assertEqual(choose(['생명','여명','몽환'],d),'여명');self.assertEqual(run(self.p,self.j,['생명','여명','몽환'],guard=lambda:True),'confirmed')
  self.assertEqual(self.j.read()['confirmed']['생명'],0);self.assertEqual(self.j.read()['confirmed']['여명'],1)
  with self.assertRaises(Hold):run(self.p,self.j,['생명','여명'],guard=lambda:True)
 def test_unconfirmed_blocks_retry(self):
  self.p.valid=False
  with self.assertRaises(Hold):run(self.p,self.j,['생명'],guard=lambda:True)
  self.assertEqual(self.j.read()['pending']['phase'],'sent');previous=list(self.p.actions)
  with self.assertRaises(Hold):run(self.p,self.j,['생명'],guard=lambda:True)
  self.assertEqual(self.p.actions,previous)
 def test_guard_change_blocks_commit(self):
  with self.assertRaises(Hold):run(self.p,self.j,['생명'],guard=lambda:len(self.p.actions)==0)
  self.assertEqual(self.p.actions,[('select','생명')])
 def test_disagree_detail_blocks(self):
  old=self.p.prepare_one
  def bad(*a,**kw):
   result=old(*a,**kw);result['detail_boxes']=50;return result
  self.p.prepare_one=bad
  with self.assertRaises(Hold):run(self.p,self.j,['생명'],guard=lambda:True)
  self.assertIsNone(self.j.read()['pending'])
 def test_absent_toast_blocks(self):
  old=self.p.receipt
  def bad(*a,**kw):
   result=old(*a,**kw);result['toast_verified']=False;return result
  self.p.receipt=bad
  with self.assertRaises(Hold):run(self.p,self.j,['생명'],guard=lambda:True)
  self.assertEqual(self.j.read()['confirmed']['생명'],0)
 def test_fresh_character_same_context(self):
  context=object();p=NS(character='a',level=50,observed=time.monotonic());adapter=NS(_owner_progression_observation=(context,p.observed,'a'))
  self.assertTrue(fresh_character(adapter,context,p))
  self.assertFalse(fresh_character(adapter,object(),p))
  p.observed-=181;adapter._owner_progression_observation=(context,p.observed,'a')
  self.assertFalse(fresh_character(adapter,context,p))
if __name__=='__main__':unittest.main()
