import unittest,tempfile,logging,json
from pathlib import Path
from types import SimpleNamespace as S
import bootstrap
from owner_telemetry import Transport

class Tests(unittest.TestCase):
 def make(self,folder,sender):
  self.credential={'device':'test-device','token':'x'*32,'alias':'test'}
  return Transport(folder,credential_store=S(read=lambda:self.credential,write=lambda d:None),sender=sender,start=False)
 def log(self,t,text='ordinary status'):
  t.emit(logging.LogRecord('project_gui.DKB',logging.WARNING,'',0,text,(),None))
 def test_failure_retains_same_event_and_retry_acknowledges_it(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   attempts=[]
   def send(path,data,token):
    attempts.append(data['events'][0]['id'])
    if len(attempts)==1:raise OSError('offline')
    return {'accepted':[e['id'] for e in data['events']]}
   t=self.make(folder,send);self.log(t)
   with self.assertRaises(OSError):t.flush()
   self.assertEqual(len(t.spool.batch()),1);t.flush()
   self.assertEqual(attempts[0],attempts[1]);self.assertEqual(t.spool.batch(),[])
 def test_redaction_before_local_spool_and_no_raw_settings(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   t=self.make(folder,None);self.log(t,'password="not-public" token=private-code');t.drain()
   raw=t.spool.path.read_text();self.assertNotIn('not-public',raw);self.assertNotIn('private-code',raw)
 def test_duplicate_state_rate_limit_and_no_recursive_transport_logging(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   t=self.make(folder,None)
   for _ in range(10):self.log(t)
   t.emit(logging.LogRecord('dkb.telemetry',logging.ERROR,'',0,'ignored',(),None));t.drain()
   self.assertEqual(len(t.spool.batch()),1)
 def test_unknown_ack_does_not_erase_local_evidence(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   t=self.make(folder,lambda *a:{'accepted':['not-sent']});self.log(t)
   with self.assertRaises(ValueError):t.flush()
   self.assertEqual(len(t.spool.batch()),1)
 def test_unregistered_pc_never_transmits_or_queues(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   t=Transport(folder,credential_store=S(read=lambda:None),sender=lambda *a:self.fail('must not transmit'),start=False)
   self.log(t);self.assertFalse(t.flush());self.assertFalse(t.spool.path.exists())
 def test_image_store_failure_does_not_block_logs_and_keeps_picture_for_retry(self):
  from PIL import Image
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as folder:
   identity='20261102T012442Z-0c34b615';p=Path(folder)/'logs/quest-incidents'/identity;p.mkdir(parents=True)
   Image.new('RGB',(897,479),(30,30,30)).save(p/'screen.png')
   calls=[]
   def send(path,data,token):
    calls.append(path)
    if path=='/v1/attachment':raise OSError('image store unavailable')
    return {'accepted':[e['id'] for e in data['events']]}
   t=self.make(folder,send);self.log(t,'진행 진단 저장 완료 · '+identity)
   self.assertTrue(t.flush());self.assertEqual(calls,['/v1/attachment','/v1/events'])
   self.assertEqual(t.pending_pictures,[['incident',identity]]);self.assertEqual(t.spool.batch(),[])

if __name__=='__main__':unittest.main()
