import tempfile,time,unittest,shutil,json
from pathlib import Path
import bootstrap
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_nonce_reconcile_candidate import reconcile
ROOT=bootstrap.A
DIR='bce6b90f82da485eb81f6ee3189c8b2d';CHAR='256b0f6111f96bcaaf78501c';RECEIPT='scoped-v1:e3e3adc1e220d59f2aa0c8ef924ae44d0354dbabc729d02c21a9709b8180cfe3';SCOPE='configured-v1:b90482f60c6d7efa11a3847b98f3b927d105ad3a8903ed2b6aed52dbafe26eab'
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  folder=self.root/'logs'/'energy-claim-evidence'/DIR;folder.parent.mkdir(parents=True);shutil.copytree(ROOT/'logs'/'energy-claim-evidence'/DIR,folder)
  self.j=Journal(self.root,RECEIPT);saved=self.j.read();saved['confirmed']['여명']=1
  saved['pending']=dict(phase='sent',operation_id='a96b3cfb70ac45f18e7c666ac7f39a27',name='몽환',quantity=1,boxes_before=48,
    before_frame_ids=['30638b23a58b4d4598eef53e26623698','23a36ee1d3324f83854a9acd1e05c382'],at=1793568493.9875872)
  self.j.save(saved)
  t=time.monotonic();self.current=dict(verified=True,boxes=47,frame_ids=['fresh-one','fresh-two'],captured_at=[t-.01,t])
 def call(self):
  # Production refreshes the current-detail pair after historical evidence
  # reading. Mirror that contract even while a cold OCR model initializes.
  def refresh():
   tick=time.monotonic()
   return dict(self.current,frame_ids=['new-fresh-one','new-fresh-two'],captured_at=[tick-.01,tick])
  return reconcile(self.root,self.j,self.current,character=CHAR,scope=SCOPE,guard=lambda:True,refresh_current=refresh)
 def test_actual_nonce_dream_one(self):
  self.assertEqual(self.call(),'confirmed');d=self.j.read();self.assertIsNone(d['pending']);self.assertEqual(d['confirmed']['몽환'],1);self.assertEqual(d['receipts'][-1]['proof'],'nonce_reward_and_decrement')
  with self.assertRaises(Hold):self.call()
 def test_other_nonce_holds(self):
  d=self.j.read();d['pending']['operation_id']='a'*32;self.j.save(d)
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.j.read()['confirmed']['몽환'],0)
 def test_wrong_fresh_remaining_holds(self):
  self.current['boxes']=48
  with self.assertRaises(Hold):self.call()
  self.assertIsNotNone(self.j.read()['pending'])
 def test_wrong_identity_holds(self):
  with self.assertRaises(Hold):reconcile(self.root,self.j,self.current,character='wrong',scope=SCOPE,guard=lambda:True)
 def test_changed_or_missing_reward_never_confirms(self):
  d=self.root/'logs'/'energy-claim-evidence'/DIR
  for n in range(3,16):shutil.copyfile(d/'after-18.png',d/('after-%02d.png'%n))
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.j.read()['confirmed']['몽환'],0)
if __name__=='__main__':unittest.main()
