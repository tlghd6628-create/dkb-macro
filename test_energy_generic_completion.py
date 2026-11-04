"""Actual archived receipts/Sky screenshots and cloned ledgers; no game input."""
import copy,hashlib,json,shutil,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
from owner_energy_box_detail_candidate import warm_count_reader,read_count_text,count,evidence_detail
from owner_energy_reward_candidate import READERS
from owner_energy_box_runtime_candidate import Journal,Hold
from owner_energy_nonce_reconcile_candidate import reconcile

LIFE='d55113d063ef46cb80813f0e575cc7ca'
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.engine=warm_count_reader(bootstrap.A)
 def frame(self,name):return np.asarray(Image.open(name).convert('RGB'))
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def source(self):return bootstrap.A/'logs/energy-claim-evidence'/LIFE
 def fresh(self,n=46):
  t=time.monotonic();return dict(verified=True,boxes=n,frame_ids=['new-current-a','new-current-b'],captured_at=[t-.01,t])
 def clone(self):
  src=next(p for p in (bootstrap.A/'settings').glob('owner-energy-claim-*.json') if (json.loads(p.read_text(encoding='utf8')).get('pending') or {}).get('operation_id')=='08600d62a7be4386ad6b1e6d7a40fd40')
  self.source_journal=src;self.source_hash=hashlib.sha256(src.read_bytes()).hexdigest()
  data=json.loads(src.read_text(encoding='utf8'));self.j=Journal(self.root,data['identity']);self.j.save(copy.deepcopy(data))
  dest=self.root/'logs/energy-claim-evidence'/LIFE;dest.parent.mkdir(parents=True);shutil.copytree(self.source(),dest)
  self.manifest=json.loads((dest/'capture-manifest.json').read_text(encoding='utf8'))
 def reconcile(self,**kwargs):
  identity=self.manifest['identity']
  return reconcile(self.root,self.j,self.fresh(),character=identity['character'],scope=identity['scope'],guard=lambda:True,refresh_current=self.fresh,**kwargs)
 def test_actual_native_life_toast_two_frames_and_other_targets_excluded(self):
  for n in (5,6):
   frame=self.frame(self.source()/f'after-{n:02d}.png')
   self.assertTrue(READERS['생명'](frame));self.assertFalse(READERS['여명'](frame));self.assertFalse(READERS['몽환'](frame))
  frame=self.frame(self.source()/'after-18.png');self.assertFalse(READERS['생명'](frame));self.assertEqual(evidence_detail(frame),46)
  changed=self.frame(self.source()/'after-05.png').copy();changed[151:160,455:465]=0
  self.assertFalse(READERS['생명'](changed))
 def test_generic_count_reads_native_46_and_current_sky_pair(self):
  actual=self.frame(self.source()/'after-18.png')
  self.assertEqual(read_count_text(actual,self.engine),46);self.assertEqual(count(actual),46)
  for name in ('energy46_current1.png','energy46_current2.png'):
   # These are Sky screenshots, not native capture templates/action proof.
   frame=self.frame(Path(__file__).parent/'live_growth_20261102'/name)
   self.assertEqual(read_count_text(frame,self.engine),46)
 def test_count_parser_requires_unit_high_confidence_and_unique_reading(self):
  frame=self.frame(self.source()/'after-18.png')
  for text,score,expected in [('123개',.999,123),('0개',.999,0),('46',.999,None),('046개',.999,None),('46개',.97,None),('46개 기타',.999,None)]:
   engine=S(predict=lambda image,t=text,s=score:[{'rec_texts':[t],'rec_scores':[s]}])
   self.assertEqual(read_count_text(frame,engine),expected)
  engine=S(predict=lambda image:[{'rec_texts':['46개','46개'],'rec_scores':[.999,.999]}])
  self.assertIsNone(read_count_text(frame,engine))
 def test_actual_life_nonce_reconciles_clone_and_preserves_installed_sent_receipt(self):
  self.clone();self.assertEqual(self.reconcile(),'confirmed')
  data=self.j.read();self.assertIsNone(data['pending']);self.assertEqual(data['confirmed']['생명'],1)
  self.assertEqual(data['receipts'][-1]['operation_id'],'08600d62a7be4386ad6b1e6d7a40fd40')
  self.assertEqual(hashlib.sha256(self.source_journal.read_bytes()).hexdigest(),self.source_hash)
 def test_missing_life_receipt_never_clears_cloned_pending(self):
  self.clone();folder=self.root/'logs/energy-claim-evidence'/LIFE
  for row in self.manifest['frames']:
   frame=self.frame(folder/row['file'])
   if READERS['생명'](frame):shutil.copyfile(folder/'after-18.png',folder/row['file'])
  with self.assertRaises(Hold):self.reconcile()
  self.assertEqual(self.j.read()['pending']['phase'],'sent')
 def test_changed_current_remaining_never_clears_cloned_pending(self):
  self.clone();identity=self.manifest['identity']
  with self.assertRaises(Hold):reconcile(self.root,self.j,self.fresh(),character=identity['character'],scope=identity['scope'],guard=lambda:True,refresh_current=lambda:self.fresh(45))
  self.assertIsNotNone(self.j.read()['pending'])

if __name__=='__main__':unittest.main()
