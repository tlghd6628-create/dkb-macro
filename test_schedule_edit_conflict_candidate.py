"""Concurrent schedule edits preserve different jobs and reject same-job races."""
exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf-8'))
import tempfile,unittest,copy
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import patch
import owner_timetable as t

class Edit(unittest.TestCase):
 def test_two_editors_merge_different_jobs_without_losing_metadata(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);initial=t.config(root)
   initial['jobs']['guide']['other']='preserve';t.save(root/'settings/owner-timetable.json',initial)
   first=copy.deepcopy(initial);second=copy.deepcopy(initial)
   t.save_user_rule(root,'guide','06:00',[0],10,expected_rule=first['jobs']['guide'])
   t.save_user_rule(root,'tower','11:00',[1],20,expected_rule=second['jobs']['tower'])
   after=t.config(root)
   self.assertEqual(after['jobs']['guide']['time'],'06:00');self.assertEqual(after['jobs']['guide']['other'],'preserve')
   self.assertEqual(after['jobs']['tower']['time'],'11:00')
 def test_same_job_conflict_cannot_overwrite_or_change_file(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);initial=t.config(root);old=copy.deepcopy(initial['jobs']['guide'])
   t.save_user_rule(root,'guide','06:00',[0],10,expected_rule=old)
   with self.assertRaisesRegex(ValueError,'다른 창'):
    t.save_user_rule(root,'guide','07:00',[1],20,expected_rule=old)
   self.assertEqual(t.config(root)['jobs']['guide']['time'],'06:00')
 def test_excluded_and_bad_rules_still_fail(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);cfg=t.config(root)
   for key,clock,days,spread in [('mail','05:00',[0],10),('guide','25:00',[0],10),('guide','05:00',[],10),('guide','05:00',[0],121)]:
    with self.assertRaises(ValueError):t.save_user_rule(root,key,clock,days,spread,expected_rule=cfg['jobs'][key])
 def test_native_none_is_visible_as_unverified_and_not_repeated_in_cycle(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);t.save(root/'settings/manager_identity.json',{'server_name':'S','character_name':'C'})
   start=datetime(2026,11,2,8,tzinfo=t.KST);cfg=t.config(root)
   cfg=t.set_user_rule(cfg,'guide','09:00',[0,1],0);t.save(root/'settings/owner-timetable.json',cfg)
   values={'auto_rewards.guide.enabled':True};plan=t.Planner(root,values,start)
   due=t.parse_at(plan.state['guide']['at']);adapter=SimpleNamespace(project=SimpleNamespace(root=root),values=values,mode='auto_mode',_owner_timetable=plan)
   calls=[]
   def operation():calls.append(1);return None
   with patch.object(t,'now',return_value=due):
    self.assertIsNone(t.scheduled_call(operation,'길라잡이',(),{},adapter))
    t.scheduled_call(operation,'길라잡이',(),{},adapter)
   self.assertEqual(calls,[1]);self.assertTrue(plan.state['guide']['result_unverified'])
   self.assertIn('결과 미확인',t.appointment(root,'guide',due,values))
   restarted=t.Planner(root,values,due);self.assertTrue(restarted.state['guide']['result_unverified'])
   self.assertEqual(restarted.due(due+timedelta(minutes=3)),[])
   tomorrow=t.Planner(root,values,datetime(2026,11,3,8,tzinfo=t.KST));self.assertEqual(tomorrow.state['guide']['status'],'pending')
   self.assertNotIn('result_unverified',tomorrow.state['guide'])
 def test_taoist_only_is_eligible_and_runs_existing_style_path_without_equipment(self):
  import owner_skill_growth_candidate as growth
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);t.save(root/'settings/manager_identity.json',{'server_name':'S','character_name':'C'})
   at=datetime(2026,11,2,8,tzinfo=t.KST)
   values={'auto_growth.equipment.enabled':False,'auto_growth.blessing.enabled':False,'auto_growth.taoist.enabled':True}
   plan=t.Planner(root,values,at);self.assertIn('gear',plan.state)
   class Adapter:
    def __init__(self):self.values=values
    def get_due_schedules(self):return []
    def _run_auto_features(self,*args,**kw):raise AssertionError('no native growth when only taoist enabled')
   adapter=Adapter();calls=[]
   with patch.object(growth,'run_after_native',side_effect=lambda a,c,i:calls.append(dict(a.values)) or ['done']):
    self.assertTrue(t.invoke(adapter,t.BY_KEY['gear'],None,None))
   self.assertEqual(calls,[values]);self.assertIs(adapter.values,values)
 def test_shop_schedule_appears_only_for_configured_selected_items_and_dispatches(self):
  from owner_shop_settings_candidate import ShopSettingsStore
  from owner_hunt_rules_candidate import configured_identity
  import owner_shop_runtime_candidate as shop
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);t.save(root/'settings/manager_identity.json',{'server_name':'S','character_name':'C'})
   at=datetime(2026,11,2,8,tzinfo=t.KST);plan=t.Planner(root,{},at)
   self.assertNotIn('shop',plan.state);store=ShopSettingsStore(root,configured_identity(root));doc=store.read_document()
   doc['items'][0]['enabled']=True;store.write(doc['items'],doc['coin_reserve'])
   plan.due(at);self.assertIn('shop',plan.state)
   class Adapter:
    def __init__(self):self.values={}
    def _run_auto_features(self,*a,**kw):raise AssertionError('shop must run its selected dispatcher')
   adapter=Adapter();calls=[]
   with patch.object(shop,'dispatch_configured',side_effect=lambda a,c,i:calls.append(True) or {'status':'processed'}):
    self.assertTrue(t.invoke(adapter,t.BY_KEY['shop'],None,None))
   with patch.object(shop,'dispatch_configured',return_value={'status':'partial'}):
    self.assertFalse(t.invoke(adapter,t.BY_KEY['shop'],None,None))
   self.assertEqual(calls,[True])
if __name__=='__main__':unittest.main(verbosity=2)
