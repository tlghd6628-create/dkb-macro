import unittest,tempfile,time
from pathlib import Path
from owner_coupon_box_candidate import CouponBoxJournal,claim_one,Pending,TARGETS
class Port:
 def __init__(self):self.calls=[];self.owned=False;self.fragments=0;self.after=True
 def p(self,**values):
  t=time.monotonic();return dict(verified=True,frame_ids=['a','b'],captured_at=[t-.01,t],**values)
 def skill_state(self,sid,guard):self.calls.append('state');return self.p(sid=sid,owned=self.owned,unlearned_verified=True,fragments=self.fragments)
 def prepare_box(self,sid,guard):self.calls.append('prepare');return self.p(sid=sid,name=TARGETS[sid],quantity=1,boxes=5,detail_boxes=5,fragments_per_box=100)
 def submit(self,prepared,mark_sent,guard):mark_sent();self.calls.append('submit')
 def receipt(self,sid,guard):
  p=self.p(sid=sid,name=TARGETS[sid],boxes=4 if self.after else 5,fragment_receipt=True,fragments_received=100);p['frame_ids']=['c','d'];return p
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.tmp.cleanup);self.j=CouponBoxJournal(self.tmp.name,'character');self.p=Port()
 def test_owned_no_consumption(self):
  self.p.owned=True;self.assertEqual(claim_one(self.p,self.j,84,lambda:True),'already_owned');self.assertEqual(self.p.calls,['state'])
 def test_existing_fragments(self):
  self.p.fragments=100;self.assertEqual(claim_one(self.p,self.j,84,lambda:True),'ready_to_learn');self.assertEqual(self.p.calls,['state'])
 def test_confirm_and_no_duplicate(self):
  self.assertEqual(claim_one(self.p,self.j,84,lambda:True),'claim_verified');self.assertEqual(self.j.read()['receipts'][0]['sid'],84)
  with self.assertRaises(Pending):claim_one(self.p,self.j,84,lambda:True)
 def test_uncertain_never_reclick(self):
  self.p.after=False
  with self.assertRaises(Pending):claim_one(self.p,self.j,84,lambda:True)
  self.assertEqual(self.j.read()['pending']['phase'],'sent');calls=list(self.p.calls)
  with self.assertRaises(Pending):claim_one(self.p,self.j,84,lambda:True)
  self.assertEqual(calls,self.p.calls)
 def test_wrong_name(self):
  old=self.p.prepare_box
  def bad(*a,**k):v=old(*a,**k);v['name']='다른 도술';return v
  self.p.prepare_box=bad
  with self.assertRaises(Pending):claim_one(self.p,self.j,84,lambda:True)
  self.assertNotIn('submit',self.p.calls)
if __name__=='__main__':unittest.main()
