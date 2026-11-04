"""Isolated calendar and fake confirmation routing; no live input."""
from pathlib import Path
import bootstrap
import copy,threading,unittest
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_timetable as t

class Tests(unittest.TestCase):
 def setUp(self):
  self.at=datetime(2026,11,2,12,tzinfo=t.KST);self.job=t.BY_KEY['inventory']
  self.p=t.Planner.__new__(t.Planner);self.p.root=Path('unused');self.p.identity='char'
  self.p.cfg={'enabled':True,'seed':'test','jobs':{}};self.p.values={self.job.setting:True}
  self.p.state={'inventory':{'period':t.period(self.job,self.at),'at':self.at.isoformat(),'status':'processed','attempts':1}}
  self.p.commit=Mock();self.patch=patch.object(t,'busy_windows',return_value=[]);self.patch.start();self.addCleanup(self.patch.stop)
  self.old_job=getattr(t.LOCAL,'job',None);self.old_native=getattr(t.LOCAL,'native_job',None)
  t.LOCAL.job=None;t.LOCAL.native_job=None;self.addCleanup(setattr,t.LOCAL,'job',self.old_job);self.addCleanup(setattr,t.LOCAL,'native_job',self.old_native)
 def claim(self):return {'state':'confirmed','confirmed':['생명','여명','몽환'],'remaining':43,'needs_recheck':True}
 def test_confirmed_partial_requeues_one_minute_as_pending_not_completed(self):
  self.assertTrue(self.p.repeat_energy(self.claim(),self.at));row=self.p.state['inventory']
  self.assertEqual(row['status'],'pending');self.assertEqual(t.parse_at(row['at']),self.at+timedelta(minutes=1))
  self.assertEqual(row['energy_followup'],{'mode':'claim','remaining':43});self.assertTrue(row['result_unverified']);self.assertEqual(row['attempts'],0)
 def test_unknown_sent_result_only_requeues_confirmation_with_two_retry_limit(self):
  out={'needs_recheck':True,'reconcile_only':True,'pending_operation':'a'*32}
  for retry in (1,2):
   self.p.state['inventory']['status']='processed'
   self.assertTrue(self.p.repeat_energy(out,self.at));row=self.p.state['inventory']
   self.assertEqual(row['energy_followup']['mode'],'reconcile');self.assertEqual(row['energy_confirm_retries'],retry)
  self.p.state['inventory']['status']='processed';self.assertFalse(self.p.repeat_energy(out,self.at))
 def test_disabled_master_weekday_and_reset_boundary_do_not_requeue(self):
  self.p.values[self.job.setting]=False;self.assertFalse(self.p.repeat_energy(self.claim(),self.at))
  self.p.values[self.job.setting]=True;self.p.cfg['jobs']['inventory']={'weekdays':[1]}
  self.assertFalse(self.p.repeat_energy(self.claim(),self.at))
  self.p.cfg['jobs']={};edge=datetime(2026,11,3,4,59,tzinfo=t.KST)
  self.p.state['inventory']['period']=t.period(self.job,edge)
  self.assertFalse(self.p.repeat_energy(self.claim(),edge))
 def test_boss_window_and_prior_job_are_avoided(self):
  start=self.at;end=self.at+timedelta(minutes=20)
  with patch.object(t,'busy_windows',return_value=[(start,end)]):self.assertTrue(self.p.repeat_energy(self.claim(),self.at))
  self.assertGreaterEqual(t.parse_at(self.p.state['inventory']['at']),end)
 def test_no_confirmed_claim_or_remaining_never_creates_followup(self):
  for out in ({'needs_recheck':True,'confirmed':[],'remaining':43},{'needs_recheck':True,'confirmed':['생명'],'remaining':0},{'needs_recheck':True,'reconcile_only':True,'pending_operation':'wrong'}):
   self.assertFalse(self.p.repeat_energy(out,self.at))
 def plan(self):
  state={'inventory':{'status':'pending','attempts':0,'at':self.at.isoformat(),'energy_followup':{'mode':'reconcile','operation_id':'a'*32}}}
  def begin(k):state[k].update(status='running',attempts=1)
  def finish(k,ok,**kw):state[k].update(status='processed' if ok else 'failed')
  return S(state=state,values={self.job.setting:True},reason=lambda k:None,begin=begin,finish=finish,repeat_energy=Mock(return_value=False),commit=Mock())
 def test_confirmation_followup_never_runs_native_inventory_or_new_claims(self):
  p=self.plan();adapter=S(project=S(root=Path('unused')),mode='auto_mode');ctx=S(checkpoint=lambda:None,stop=threading.Event());inputs=object()
  def confirm(a,c,i):
   self.assertIs(c,ctx);self.assertIs(i,inputs);self.assertTrue(a._owner_energy_box_reconcile_only)
   a._owner_energy_box_outcome={'state':'held'};return 'held'
  with patch.object(t,'planner',return_value=p),patch.object(t,'config',return_value={'jobs':{}}),patch('owner_energy_next_integration_candidate.attempt',side_effect=confirm):
   self.assertFalse(t.scheduled_call(lambda:self.fail('native inventory in confirm-only'),'인벤토리 사용',(),{},adapter,timed_dispatch=True,run_context=ctx,run_inputs=inputs))
  self.assertEqual(p.state['inventory']['status'],'failed');self.assertFalse(adapter._owner_energy_box_reconcile_only)
 def test_user_stop_during_confirmation_remains_pending_without_false_failure(self):
  class Stop(BaseException):pass
  p=self.plan();ctx=S(checkpoint=lambda:None,stop=threading.Event());ctx.stop.set();adapter=S(project=S(root=Path('unused')),mode='auto_mode')
  def cancel(*a):raise Stop()
  with patch.object(t,'planner',return_value=p),patch.object(t,'config',return_value={'jobs':{}}),patch('owner_energy_next_integration_candidate.attempt',side_effect=cancel):
   with self.assertRaises(Stop):t.scheduled_call(lambda:self.fail('native'),'인벤토리 사용',(),{},adapter,timed_dispatch=True,run_context=ctx,run_inputs=object())
  self.assertEqual(p.state['inventory']['status'],'pending');self.assertEqual(p.state['inventory']['attempts'],0)

if __name__=='__main__':unittest.main()
