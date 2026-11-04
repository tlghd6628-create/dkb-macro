"""Actual log filter and isolated reset planner, without GUI/game actions."""
import bootstrap
import unittest,tempfile,queue,logging
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
from owner_update_core import save
from owner_auto_update import release_notice,visible_log,LOG
from user_log import LogQueue
import owner_timetable as t

class Notice(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(self.tmp.cleanup)
  self.cache=Path(self.tmp.name);self.release={'sequence':3,'version':'r21-flow-display-3'}
 def records(self):
  save(self.cache/'current.json',dict(self.release,applied_at=1))
  save(self.cache/'last-result.json',{'ok':True,'sequence':3})
  save(self.cache/'resume.json',{'resume':False})
 def test_applied_matching_receipt_is_explicit_completion(self):
  self.records();self.assertEqual(release_notice(self.cache,self.release),'업데이트 완료 · 적용 버전 3')
 def test_download_or_fresh_install_is_not_fake_completion(self):
  self.assertEqual(release_notice(self.cache,self.release),'현재 적용 버전 · 3')
 def test_failed_or_mismatched_apply_does_not_claim_completion(self):
  self.records();save(self.cache/'last-result.json',{'ok':False,'sequence':3})
  self.assertNotIn('완료',release_notice(self.cache,self.release))
  self.records();save(self.cache/'current.json',{'sequence':2,'version':'old'})
  self.assertNotIn('완료',release_notice(self.cache,self.release))
 def test_next_manual_launch_shows_current_not_new_completion(self):
  self.records();(self.cache/'resume.json').unlink()
  self.assertEqual(release_notice(self.cache,self.release),'현재 적용 버전 · 3')
 def test_real_user_log_queue_retains_explicit_message(self):
  messages=queue.Queue();handler=LogQueue(messages);old=LOG.level;LOG.setLevel(logging.INFO);LOG.addHandler(handler)
  try:visible_log('업데이트 완료 · 적용 버전 3')
  finally:LOG.removeHandler(handler);LOG.setLevel(old)
  self.assertIn('업데이트 완료 · 적용 버전 3',messages.get_nowait())

class WeeklyCheck(unittest.TestCase):
 def test_weekly_verification_is_before_existing_wednesday05_reset(self):
  job=t.BY_KEY['shop_weekly_verify'];at=datetime(2026,11,2,16,tzinfo=t.KST)
  cfg={'enabled':True,'jobs':{},'seed':'fixture'}
  planned=t.preferred_base(job,cfg,at,t.period(job,at))
  self.assertEqual(planned.weekday(),1);self.assertEqual(planned.strftime('%H:%M'),'23:10')
  self.assertEqual(t.period(job,planned),t.period(job,at))
  self.assertLess(planned,datetime(2026,11,4,5,tzinfo=t.KST))
 def test_verification_uses_same_guarded_shop_dispatch(self):
  from types import SimpleNamespace as S
  adapter=S();context=S();inputs=object()
  with patch('owner_shop_runtime_candidate.dispatch_configured',return_value={'status':'partial'}) as run:
   self.assertFalse(t.invoke(adapter,t.BY_KEY['shop_weekly_verify'],context,inputs))
  run.assert_called_once_with(adapter,context,inputs)
 def test_projection_includes_weekly_check(self):
  import owner_schedule as s
  self.assertEqual(t.CATALOG_JOB['weekly_shop_verify'],'shop_weekly_verify')
  self.assertEqual(s.BY_KEY['weekly_shop_verify'].period,'week')

if __name__=='__main__':unittest.main()
