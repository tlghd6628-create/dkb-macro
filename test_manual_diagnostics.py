import unittest,tempfile,json,hashlib,zipfile
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image
import bootstrap
import owner_manual_diagnostics as m

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'app/vendor/DKB_Auto';(self.root/'logs').mkdir(parents=True)
  self.device={'device':'test-device','alias':'test','token':'test-token'}
  self.moment=datetime(2026,11,2,2,0,tzinfo=timezone.utc)
  self.log=self.root/'logs/2026-11-02.log'
  self.log.write_text('2026-11-02 10:00:00,000 ERROR failed password="hidden"\n  at original traceback\n2026-11-02 10:00:01,000 INFO next\n',encoding='utf8')
 def make(self,picture=False):
  if picture:
   d=self.root/'logs/quest-incidents/20261102T010000Z-12345678';d.mkdir(parents=True)
   Image.new('RGB',(897,479),(20,30,40)).save(d/'screen.png')
   (d/'incident.json').write_text(json.dumps({'reason':'stuck','password':'do-not-send'}),encoding='utf8')
  return m.create_snapshot(self.root,{'status':'running'},self.device,moment=self.moment)
 def test_today_logs_traceback_redaction_and_sources_untouched(self):
  before=self.log.read_bytes();job,archive=self.make()
  with zipfile.ZipFile(archive) as z:
   self.assertNotIn('hidden',z.read('recent-log.txt').decode())
   events=[json.loads(s) for s in z.read('events.jsonl').splitlines()]
   self.assertEqual(len(events),3);self.assertEqual(events[1]['kind'],'error')
   self.assertIn('traceback',events[1]['message']);self.assertEqual(z.testzip(),None)
   self.assertFalse(any('settings' in n for n in z.namelist()))
  self.assertEqual(self.log.read_bytes(),before);self.assertEqual(json.loads(job.read_text())['phase'],'pending')
 def test_complete_logs_metadata_picture_then_final_receipt(self):
  job,archive=self.make(True);events={};photos={}
  def sender(path,data,token):
   if path=='/v1/events':
    for e in data['events']:
     if e['id'] in events:self.assertEqual(e,events[e['id']])
     events[e['id']]=e
    return {'accepted':[e['id'] for e in data['events']]}
   self.assertEqual(path,'/v1/attachment');photos[data['sha256']]=data['jpeg'];return {'sha256':data['sha256'],'stored':True}
  for _ in range(10):
   state=m.send_step(self.root,job,self.device,sender)
   if state['phase']=='sent':break
  self.assertEqual(state['phase'],'sent');self.assertTrue(archive.exists())
  self.assertEqual(len(photos),1);self.assertTrue(any(e['message']=='수동 진단 전송 완료' for e in events.values()))
  import base64
  metadata=b''.join(base64.b64decode(e['message']) for e in events.values() if e['context'].get('diagnostic_metadata')).decode('utf8')
  self.assertIn('stuck',metadata);self.assertNotIn('do-not-send',metadata)
  self.assertEqual(json.loads(metadata)['password'],'[REDACTED]')
 def test_lost_response_retries_same_events_without_false_success(self):
  job,_=self.make();seen=[]
  def lost(path,data,token):seen.append(data['events']);raise OSError('response lost')
  with self.assertRaises(OSError):m.send_step(self.root,job,self.device,lost)
  self.assertEqual(json.loads(job.read_text())['log_cursor'],0)
  def retry(path,data,token):self.assertEqual(data['events'],seen[0]);return {'accepted':[e['id'] for e in data['events']]}
  state=m.send_step(self.root,job,self.device,retry);self.assertEqual(state['log_cursor'],3);self.assertEqual(state['phase'],'pending')
 def test_partial_ack_never_advances_cursor(self):
  job,_=self.make()
  with self.assertRaises(ValueError):m.send_step(self.root,job,self.device,lambda p,d,t:{'accepted':[d['events'][0]['id']]})
  self.assertEqual(json.loads(job.read_text())['log_cursor'],0)
 def test_repeated_manual_snapshots_reuse_log_identity(self):
  _,a=self.make();_,b=self.make()
  with zipfile.ZipFile(a) as aa,zipfile.ZipFile(b) as bb:self.assertEqual(aa.read('events.jsonl'),bb.read('events.jsonl'))
 def test_other_device_or_outside_job_rejected_before_network(self):
  job,_=self.make()
  def nope(*a):self.fail('must not transmit')
  with self.assertRaises(ValueError):m.send_step(self.root,job,dict(self.device,device='different'),nope)
  with self.assertRaises(ValueError):m.send_step(self.root,Path(self.tmp.name)/'elsewhere.json',self.device,nope)
 def test_large_or_wrong_screen_is_not_uploaded(self):
  d=self.root/'logs/quest-incidents/20261102T010000Z-12345678';d.mkdir(parents=True)
  Image.new('RGB',(1920,1080)).save(d/'screen.png')
  _,archive=self.make()
  with zipfile.ZipFile(archive) as z:self.assertEqual(json.loads(z.read('summary.json'))['pictures'],[])
 def test_background_worker_picks_persisted_pending_job(self):
  import threading
  from types import SimpleNamespace as S
  job,_=self.make();done=threading.Event()
  def sender(path,data,token):
   if any(e['message']=='수동 진단 전송 완료' for e in data['events']):done.set()
   return {'accepted':[e['id'] for e in data['events']]}
  worker=m.ManualUpload(self.root,S(device=self.device,sender=sender))
  try:worker.wake.set();self.assertTrue(done.wait(3))
  finally:worker.close();worker.worker.join(2)
  self.assertEqual(json.loads(job.read_text())['phase'],'sent')

if __name__=='__main__':unittest.main()
