import json,tempfile,time,unittest,shutil
from pathlib import Path
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_legacy_reconcile_candidate import read_legacy,LEGACY_AT,LEGACY_DIR,LEGACY_BEFORE,LEGACY_CHARACTER,LEGACY_RECEIPT
R=Path('C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/vendor/DKB_Auto/logs/energy-claim-evidence')/LEGACY_DIR
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parent));self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  folder=self.root/'logs'/'energy-claim-evidence'/LEGACY_DIR;folder.parent.mkdir(parents=True);shutil.copytree(R,folder)
  self.j=Journal(self.root,LEGACY_RECEIPT);self.s=self.j.read();self.s['pending']=dict(phase='sent',name='여명',quantity=1,boxes_before=49,before_frame_ids=LEGACY_BEFORE,at=LEGACY_AT);self.j.save(self.s)
  t=time.monotonic();self.current=dict(verified=True,boxes=48,frame_ids=['fresh-a','fresh-b'],captured_at=[t-.01,t])
 def call(self):return read_legacy(self.root,self.j,self.current,character=LEGACY_CHARACTER,guard=lambda:True)
 def test_real_evidence_one_time(self):
  self.assertEqual(self.call(),'confirmed');state=self.j.read();self.assertEqual(state['confirmed']['여명'],1);self.assertIsNone(state['pending']);self.assertEqual(len(state['receipts'][0]['sha256']),4)
  with self.assertRaises(Hold):self.call()
 def test_wrong_current_count_does_not_clear(self):
  self.current['boxes']=47
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.j.read()['pending']['phase'],'sent')
 def test_manifest_mismatch_does_not_clear(self):
  path=self.root/'logs'/'energy-claim-evidence'/LEGACY_DIR/'capture-manifest.json';x=json.loads(path.read_text(encoding='utf8'));x['target']='생명';path.write_text(json.dumps(x),encoding='utf8')
  with self.assertRaises(Hold):self.call()
  self.assertEqual(self.j.read()['confirmed']['여명'],0)
 def test_wrong_character_blocks(self):
  with self.assertRaises(Hold):read_legacy(self.root,self.j,self.current,character='other',guard=lambda:True)
 def test_wrong_reward_screen_blocks(self):
  folder=self.root/'logs'/'energy-claim-evidence'/LEGACY_DIR;shutil.copyfile(folder/'after-00.png',folder/'after-06.png')
  with self.assertRaises(Hold):self.call()
  self.assertIsNotNone(self.j.read()['pending'])
if __name__=='__main__':unittest.main()
