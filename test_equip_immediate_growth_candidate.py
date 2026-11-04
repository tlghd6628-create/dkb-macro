"""Same-worker queue/receipt regressions; no running game input."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch,Mock
import tempfile,threading,time,json,base64,unittest
import numpy as np
import bootstrap
import owner_equip_growth_due_candidate as subject
from owner_equipment_upgrade_candidate import Journal
from owner_gear_native_install_candidate import _post_equip_preference


class Tests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.journal=Journal(self.root,'profile|character')
  proof={'character':self.journal.identity,'slot':'장갑','current_item':'old','candidate_item':'new','current_grade':'일반','candidate_grade':'희귀','frame_ids':['pre1','pre2']}
  self.journal.prepare(proof);self.journal.mark_sent();self.journal.complete(proof,result_frame_ids=['post1','post2'])
  self.request=self.journal.growth_request();self.events=[];self.block=False
  self.plan=NS(cfg={'enabled':True},values={'auto_growth.equipment.enabled':True},state={'gear':{'status':'pending','attempts':0}},commit=lambda:self.events.append('commit'))
  def begin(key):self.plan.state[key].update(status='running',attempts=1);self.events.append('begin')
  self.plan.begin=begin;self.plan.finish=lambda key,ok,**kw:self.events.append(('finish',ok,kw))
  self.adapter=NS(project=NS(root=self.root));self.inputs=NS(held=());self.ctx=NS(checkpoint=lambda:None,input_depth=0,stop=threading.Event())
  self.timetable=NS(LOCAL=threading.local(),BY_KEY={'gear':NS(key='gear')},LOG=Mock(),now=lambda:__import__('datetime').datetime.now(),selected_days=lambda *a:None,planner=lambda a:self.plan)
  def invoke(adapter,job,context,inputs):self.events.append(('invoke',threading.get_ident(),dict(adapter._owner_post_equip_target)));return True
  def post(adapter,context,inputs,plan):
   if self.block or time.monotonic()<getattr(adapter,'_owner_post_equip_retry_at',0):return False
   context.checkpoint();adapter._owner_post_equip_retry_at=time.monotonic()+600
   self.timetable.invoke(adapter,self.timetable.BY_KEY['gear'],context,inputs)
   self.journal.mark_growth_dispatched(self.request['growth_request_id']);return True
  self.timetable.post_equip_growth=post;self.timetable.invoke=invoke
  self.timetable.idle_once=lambda *a:self.events.append('ordinary_due') or False
  subject.install(self.timetable)
 def pending(self,*a):
  current=self.journal.growth_request()
  return (self.journal,current,'profile','character') if current else None
 def run_idle(self):
  with patch.object(subject,'pending_request',side_effect=self.pending),patch.object(subject,'idle_admissible',return_value=True):
   return self.timetable.idle_once(self.adapter,self.ctx,self.inputs)
 def test_new_equip_runs_before_other_due_work_on_the_same_worker(self):
  self.assertTrue(self.run_idle());self.assertNotIn('ordinary_due',self.events)
  entry=next(e for e in self.events if isinstance(e,tuple) and e[0]=='invoke')
  self.assertEqual(entry[1],threading.get_ident());self.assertEqual(entry[2]['slot'],'장갑')
  self.assertIsNone(self.journal.growth_request())
  self.assertIsNone(Journal(self.root,'profile|character').growth_request())
  self.run_idle();self.assertEqual(sum(isinstance(e,tuple) and e[0]=='invoke' for e in self.events),1)
 def test_incomplete_goal_uses_existing_unverified_recheck_planner(self):
  self.run_idle()
  self.assertIn(('finish',True,{'unverified':True}),self.events)
  self.assertNotIn('enhancement',self.journal.read()['completed'][0])
 def test_boss_admission_deferral_does_not_claim_request(self):
  self.block=True;self.assertFalse(self.run_idle());self.assertEqual(self.journal.growth_request()['growth_state'],'pending')
  self.assertFalse(any(isinstance(e,tuple) and e[0]=='invoke' for e in self.events))
 def test_new_request_is_not_delayed_by_an_old_request_retry(self):
  self.adapter._owner_post_equip_retry_at=time.monotonic()+600;self.adapter._owner_post_equip_request_key=('old','character','other-receipt')
  self.assertTrue(self.run_idle())
 def test_user_stop_before_admission_sends_nothing_and_keeps_queue(self):
  def stop():raise RuntimeError('user stopped')
  self.ctx.checkpoint=stop
  with self.assertRaisesRegex(RuntimeError,'user stopped'):self.run_idle()
  self.assertEqual(self.journal.growth_request()['growth_state'],'pending');self.assertFalse(self.events)
 def test_inventory_worker_active_never_enters_growth_recursively(self):
  from owner_equip_runtime_install_candidate import LOCAL as equipment
  from owner_schedule_priority import LOCAL as priority
  import owner_schedule_priority
  equipment.active=True
  try:
   with patch.object(owner_schedule_priority,'hold_reason',return_value=None):
    self.assertFalse(subject.idle_admissible(self.timetable,self.adapter,self.ctx,self.inputs))
  finally:equipment.active=False
 def test_claim_survives_restart_without_clearing_other_resource_record(self):
  other=self.root/'settings/owner-gear-intent.json';other.write_text('{"phase":"sent"}',encoding='utf8')
  self.journal.claim_growth_dispatch(self.request['growth_request_id'])
  self.assertIsNone(Journal(self.root,self.journal.identity).growth_request());self.assertEqual(other.read_text(),'{"phase":"sent"}')
 def test_preference_uses_current_dynamic_icon_and_rejects_ambiguous_duplicates(self):
  random=np.random.default_rng(101);icon=random.integers(0,255,(20,20,3),dtype=np.uint8)
  req={'verified_as':'same_item','candidate_grade':'희귀','candidate_item':json.dumps({'icon_rgb':base64.b64encode(icon.tobytes()).decode('ascii')})}
  f=np.zeros((479,897,3),np.uint8);rows=[]
  for i,x in enumerate((709,747),1):
   rows.append({'index':i,'grade':'파랑','slot':{'cell_x':x,'cell_y':89}})
   f[97:115,x+8:x+26]=icon[1:19,1:19] if i==2 else 255-icon[1:19,1:19]
  self.assertEqual(_post_equip_preference(f,rows,req),2)
  f[97:115,717:735]=icon[1:19,1:19]
  self.assertIsNone(_post_equip_preference(f,rows,req))
 def test_real_existing_post_callback_is_connected_without_changing_saved_values(self):
  import owner_timetable as timetable,owner_hunt_rules_candidate,owner_progression
  from owner_gear_settings_candidate import Store
  store=Store(self.root,'profile');document=store.read();document['grades']['희귀']['enabled']=True;store.write(document)
  self.adapter.values={'saved':'preserved'};self.adapter.mode='sub_quest';self.adapter.exit_sleep_mode=lambda *a:None
  old=(timetable.post_equip_growth,timetable.idle_once,timetable.invoke)
  native=Mock(return_value=True);timetable.invoke=native
  try:
   subject.install(timetable)
   with patch.object(subject,'idle_admissible',return_value=True),patch.object(subject,'pending_request',side_effect=self.pending),patch.object(timetable,'planner',return_value=self.plan),patch.object(timetable,'selected_days',return_value=None),patch.object(timetable,'busy_windows',return_value=[]),patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='profile'),patch.object(owner_progression,'state',return_value=NS(character='character',observed=time.monotonic())):
    self.assertTrue(timetable.idle_once(self.adapter,self.ctx,self.inputs))
   native.assert_called_once();self.assertIsNone(self.journal.growth_request())
   self.assertEqual(self.adapter.values,{'saved':'preserved'})
   self.assertEqual(self.journal.read()['completed'][0]['growth_state'],'dispatched_unverified')
  finally:timetable.post_equip_growth,timetable.idle_once,timetable.invoke=old


if __name__=='__main__':unittest.main()
