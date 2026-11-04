from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import base64,copy,hashlib,json,queue,tempfile,threading,time,unittest,zipfile
import bootstrap
import owner_update_core as core
from owner_update_worker import apply_files
from owner_auto_update import Bridge

FIX=Path(__file__).parent/'update_test_fixture'
class Signed(unittest.TestCase):
 def setUp(self):
  self.raw=(FIX/'release.json').read_bytes();self.trust=core.load((Path(__file__).parent/'owner_update_trust.json').read_bytes())
  self.doc=core.verify_signed(self.raw,self.trust,1)
 def test_actual_windows_signer_signature_and_bundle(self):self.assertTrue(core.verify_zip(FIX/'bundle.zip',self.doc))
 def test_payload_change_rejected(self):
  obj=json.loads(self.raw);payload=base64.b64decode(obj['payload']);obj['payload']=base64.b64encode(payload+b' ').decode()
  with self.assertRaises(core.UpdateError):core.verify_signed(json.dumps(obj).encode(),self.trust,1)
 def test_signature_change_rejected(self):
  obj=json.loads(self.raw);sig=bytearray(base64.b64decode(obj['signature']));sig[-1]^=1;obj['signature']=base64.b64encode(sig).decode()
  with self.assertRaises(core.UpdateError):core.verify_signed(json.dumps(obj).encode(),self.trust,1)
 def test_old_release_rejected(self):
  with self.assertRaises(core.UpdateError):core.verify_signed(self.raw,self.trust,2)
 def test_path_and_personal_state_rejected(self):
  for path in ['owner/../start.py','owner\\a.py','C:/owner/a.py','owner/settings/password.json','owner/logs/a.png','owner/owner_update_trust.json','vendor/DKB_Auto/launch.py','owner/launcher/a.exe']:
   self.assertFalse(core.allowed(path),path)
 def test_duplicate_json_key_rejected(self):
  with self.assertRaises(core.UpdateError):core.load('{"sequence":1,"sequence":2}')
 def test_zip_corruption_rejected(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as d:
   path=Path(d)/'bundle.zip';path.write_bytes((FIX/'bundle.zip').read_bytes()+b'extra')
   with self.assertRaises(core.UpdateError):core.verify_zip(path,self.doc)
 def test_apply_and_rollback_touch_only_explicit_paths(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as d:
   root=Path(d);old=root/'owner/owner_update_probe.py';old.parent.mkdir();old.write_bytes(b'old')
   settings=root/'owner/settings/user.json';settings.parent.mkdir();settings.write_bytes(b'preserve')
   apply_files(root,FIX/'bundle.zip',self.doc,root/'rollback')
   self.assertEqual(old.read_bytes(),b'value=2\n');self.assertEqual(settings.read_bytes(),b'preserve')
   old.write_bytes(b'old');calls=[]
   def failure(path,data):calls.append(path);core.atomic(path,data);raise OSError('simulated disk failure')
   with self.assertRaises(OSError):apply_files(root,FIX/'bundle.zip',self.doc,root/'rollback2',write=failure)
   self.assertEqual(old.read_bytes(),b'old');self.assertEqual(settings.read_bytes(),b'preserve')
 def test_symlink_target_cannot_escape_root(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as d:
   root=Path(d)
   with self.assertRaises(core.UpdateError):core.target(root,'owner/../owner_update_probe.py')

class State(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.calls=[];self.status='running';self.closed=threading.Event()
  def stopped():self.status='stopped';self.calls.append('stop')
  session=S(start=lambda:self.calls.append('start'),resume=lambda:self.calls.append('resume'),pause=lambda:self.calls.append('pause'),stop=stopped,snapshot=lambda:{'status':self.status,'worker_alive':False,'error':''})
  root=S(protocol=lambda *a:None,after=lambda *a:None)
  def close(**kw):session.stop();self.closed.set()
  gui=S(session=session,root=root,closed=self.closed,close=close,set_execution_mode=lambda mode:self.calls.append(('mode',mode)),load_settings_model=lambda:S(mode='sub_quest'),project=S(root=self.root/'vendor/DKB_Auto'),game_window=S(hwnd=123),start_requested=lambda:self.calls.append('start_requested'))
  self.bridge=Bridge.__new__(Bridge);b=self.bridge;b.gui=gui;b.root=self.root;b.cache=self.root/'.owner-update';b.control=gui.project.root/'settings/owner-update-control.json'
  b.epoch=0;b.internal=False;b.closing_for_update=False;b.updating=False;b.pending=None;b.helper=None;b.blocked=set();b.cancel=threading.Event();b.original_stop=session.stop;b._wire()
 def test_internal_shutdown_does_not_replace_running_intent(self):
  b=self.bridge;b.intent('running');b.updating=True;b.closing_for_update=True;b.gui.close(force=True)
  self.assertEqual(core.load(b.control.read_bytes())['desired'],'running')
 def test_user_stop_fences_restart(self):
  b=self.bridge;b.intent('running');old=b.epoch;b.updating=True;b.gui.session.stop()
  self.assertGreater(b.epoch,old);self.assertEqual(core.load(b.control.read_bytes())['desired'],'stopped')
 def test_user_exit_is_persisted(self):
  self.bridge.gui.close();self.assertTrue(core.load(self.bridge.control.read_bytes())['user_exit'])
 def token(self,**kwargs):
  b=self.bridge;b.intent('running');data=dict(epoch=b.epoch,resume=True,expires=time.time()+60,mode='sub_quest',profile='scope',nonce='one');data.update(kwargs);core.save(b.cache/'resume.json',data)
 def test_matching_resume_consumed_before_one_start(self):
  self.token()
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):self.bridge.resume();self.bridge.resume()
  self.assertEqual(self.calls.count('start_requested'),1);self.assertIn(('mode','sub_quest'),self.calls)
 def test_stop_pause_expiry_and_character_change_never_start(self):
  for variation in ['stop','pause','expiry','profile','resume_false']:
   self.calls.clear();self.token()
   if variation=='stop':self.bridge.intent('stopped')
   if variation=='pause':self.bridge.intent('paused')
   if variation=='expiry':self.token(expires=time.time()-1)
   if variation=='resume_false':self.token(resume=False)
   with patch('owner_hunt_rules_candidate.configured_identity',return_value='other' if variation=='profile' else 'scope'):self.bridge.resume()
   self.assertNotIn('start_requested',self.calls,variation)
 def test_prepare_incomplete_does_not_consume_resume(self):
  self.token();self.bridge.gui._paddle_preparation=S(done=threading.Event())
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):self.bridge.resume()
  self.assertTrue((self.bridge.cache/'resume.json').exists());self.assertNotIn('start_requested',self.calls)
 def test_stop_after_async_start_request_still_cancels_delayed_start(self):
  self.token()
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):self.bridge.resume()
  self.bridge.gui.session.stop();self.bridge.gui.session.start()
  self.assertNotIn('start',self.calls)
 def test_explicit_new_start_may_replace_cancelled_automatic_request(self):
  self.token()
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):self.bridge.resume()
  self.bridge.gui.session.stop();self.bridge.gui.start_requested();self.bridge.gui.session.start()
  self.assertIn('start',self.calls)
 def test_helper_preparation_failure_never_stops_running_macro(self):
  b=self.bridge;folder=b.cache/'downloads/case';folder.mkdir(parents=True)
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):b.begin(folder,{'sequence':2,'version':'test'})
  self.assertNotIn('stop',self.calls)
  with patch('owner_auto_update.subprocess.Popen',side_effect=OSError('simulated spawn failure')):b.finish_handoff()
  b.cancel.set();self.assertNotIn('stop',self.calls);self.assertFalse(b.updating)
 def test_ready_helper_then_cooperative_cleanup_closes_only_gui(self):
  b=self.bridge;folder=b.cache/'downloads/case';folder.mkdir(parents=True)
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):b.begin(folder,{'sequence':2,'version':'test'})
  b.helper=S(pid=42,poll=lambda:None);core.save(folder/'ready.json',{'pid':42})
  b.finish_handoff();self.assertTrue(self.closed.is_set());self.assertIn('stop',self.calls)
  self.assertEqual(core.load(b.control.read_bytes())['desired'],'running')

class Worker(unittest.TestCase):
 def case(self,desired='running',epoch=3,user_exit=False):
  import shutil
  tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(tmp.cleanup);root=Path(tmp.name)
  core.save(root/'owner/owner_release.json',{'sequence':1})
  folder=root/'.owner-update/downloads/test';folder.mkdir(parents=True)
  for name in ['release.json','bundle.zip']:shutil.copy2(FIX/name,folder/name)
  core.save(root/'vendor/DKB_Auto/settings/owner-update-control.json',{'epoch':epoch,'desired':desired,'user_exit':user_exit})
  core.save(folder/'job.json',{'root':str(root),'wait_pids':[99999],'was_running':True,'epoch':3,'nonce':'testnonce','mode':'sub_quest','profile':'scope'})
  return root,folder
 def test_real_worker_apply_control_and_start_submission(self):
  import owner_update_worker as worker
  root,folder=self.case()
  with patch.object(worker,'alive',return_value=False),patch.object(worker.subprocess,'Popen') as spawn:worker.main(folder/'job.json')
  self.assertEqual((root/'owner/owner_update_probe.py').read_bytes(),b'value=2\n')
  self.assertTrue(core.load((root/'.owner-update/resume.json').read_bytes())['resume'])
  self.assertEqual(core.load((root/'.owner-update/current.json').read_bytes())['sequence'],2)
  spawn.assert_called_once();self.assertFalse((root/'.owner-update/applying.json').exists())
 def test_stop_during_handoff_reopens_without_macro_start(self):
  import owner_update_worker as worker
  root,folder=self.case(desired='stopped',epoch=4)
  with patch.object(worker,'alive',return_value=False),patch.object(worker.subprocess,'Popen') as spawn:worker.main(folder/'job.json')
  self.assertFalse(core.load((root/'.owner-update/resume.json').read_bytes())['resume']);spawn.assert_called_once()
 def test_explicit_user_exit_never_reopens_program(self):
  import owner_update_worker as worker
  root,folder=self.case(desired='stopped',epoch=4,user_exit=True)
  with patch.object(worker,'alive',return_value=False),patch.object(worker.subprocess,'Popen') as spawn:worker.main(folder/'job.json')
  spawn.assert_not_called();self.assertFalse((root/'.owner-update/resume.json').exists())
 def test_apply_failure_blocks_bad_release_and_reopens_verified_old_program(self):
  import owner_update_worker as worker
  root,folder=self.case()
  with patch.object(worker,'alive',return_value=False),patch.object(worker,'apply_files',side_effect=OSError('disk failure before writes')),patch.object(worker.subprocess,'Popen') as spawn:
   self.assertEqual(worker.main(folder/'job.json'),1)
  result=core.load((root/'.owner-update/last-result.json').read_bytes())
  self.assertTrue(result['rolled_back']);self.assertEqual(result['blocked_sequence'],2);spawn.assert_called_once()
  self.assertTrue(core.load((root/'.owner-update/resume.json').read_bytes())['resume'])
 def interrupted(self,state='prepared'):
  root,folder=self.case();backup=root/'.owner-update/rollback/interrupted';backup.mkdir(parents=True)
  dest=root/'owner/owner_update_probe.py';dest.write_bytes(b'new');(backup/'0.old').write_bytes(b'old')
  core.save(backup/'transaction.json',{'state':state,'files':[{'path':'owner/owner_update_probe.py','existed':True,'old_sha256':core.digest(b'old'),'new_sha256':core.digest(b'new')}]})
  return root,backup,dest,{'sequence':2,'version':'isolated-test','transaction':str(backup)}
 def test_dead_writer_prepared_transaction_restores_previous_bytes(self):
  import owner_update_worker as worker
  root,backup,dest,info=self.interrupted();worker.recover(root,info)
  self.assertEqual(dest.read_bytes(),b'old');self.assertEqual(core.load((backup/'transaction.json').read_bytes())['state'],'rolled_back')
 def test_unexpected_manual_changes_are_not_overwritten_by_recovery(self):
  import owner_update_worker as worker
  root,backup,dest,info=self.interrupted();dest.write_bytes(b'edited elsewhere')
  with self.assertRaises(core.UpdateError):worker.recover(root,info)
  self.assertEqual(dest.read_bytes(),b'edited elsewhere')
 def test_committed_transaction_recovers_version_without_replaying_action(self):
  import owner_update_worker as worker
  root,backup,dest,info=self.interrupted('committed');worker.recover(root,info)
  self.assertEqual(dest.read_bytes(),b'new');self.assertEqual(core.load((root/'.owner-update/current.json').read_bytes())['sequence'],2)
if __name__=='__main__':unittest.main()
