import json,os,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from owner_blessing_original_fence_candidate import install,install_runtime

class Tests(unittest.TestCase):
 def test_native_compiled_fake_trace_reaches_reward_and_summon_without_old_equip(self):
  script=Path(__file__).parent/'probe_blessing_original_fake.py'
  def run(*args):
   p=subprocess.run([sys.executable,'-B',str(script),'--summary','--equip',*args],capture_output=True,text=True,encoding='utf8',timeout=30)
   self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout.strip().splitlines()[-1])
  baseline=run();fenced=run('--fence')
  self.assertGreater(baseline['grid_clicks'],0);self.assertEqual(fenced['grid_clicks'],0)
  self.assertEqual(fenced['protection_enter'],1);self.assertEqual(fenced['protection_exit'],1)
  self.assertGreater(fenced['candidate_checks'],0);self.assertTrue(fenced['reward_detect']);self.assertTrue(fenced['summon_detect'])
 def test_protection_and_other_thread_keep_unmodified_rows(self):
  rows=[{'equipped':True},{'equipped':False}];seen=[]
  market=SimpleNamespace(inspect_growth_equipment=lambda *a,**k:rows)
  def protect(*a,**k):seen.append(('protected',len(market.inspect_growth_equipment(reward_slots=True))))
  def reward(adapter,ctx,inputs):
   module._blessing_bulk_skip_reason();seen.append(('old_equip',len(market.inspect_growth_equipment(reward_slots=True))))
   t=threading.Thread(target=lambda:seen.append(('other_thread',len(market.inspect_growth_equipment(reward_slots=True)))));t.start();t.join()
  module=SimpleNamespace(run_blessing_rewards=reward,_blessing_bulk_skip_reason=protect,_blessing_tradeable_candidates=protect)
  install(module,market,should_fence=lambda adapter:True)
  module.run_blessing_rewards(None,None,None)
  self.assertEqual(seen,[('protected',2),('old_equip',1),('other_thread',2)])
  self.assertEqual(len(market.inspect_growth_equipment(reward_slots=True)),2)
 def test_exception_restores_thread_scope(self):
  rows=[{'equipped':True},{'equipped':False}];market=SimpleNamespace(inspect_growth_equipment=lambda *a,**kw:rows)
  def fail(*a,**kw):raise RuntimeError('test')
  module=SimpleNamespace(run_blessing_rewards=fail,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
  install(module,market,should_fence=lambda adapter:True)
  with self.assertRaises(RuntimeError):module.run_blessing_rewards(None,None,None)
  self.assertEqual(len(market.inspect_growth_equipment(reward_slots=True)),2)
 def test_runtime_retains_native_rewards_then_runs_new_policy_unfenced(self):
  from owner_gear_settings_candidate import Store
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   rows=[{'equipped':True},{'equipped':False}];seen=[];market=SimpleNamespace(inspect_growth_equipment=lambda *a,**k:rows)
   def native(adapter,ctx,inputs):seen.append(('native',len(market.inspect_growth_equipment(reward_slots=True))));return True
   module=SimpleNamespace(run_blessing_rewards=native,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
   Store(temp,'test').write(Store(temp,'test').read());adapter=SimpleNamespace(project=SimpleNamespace(root=temp));context=SimpleNamespace(checkpoint=lambda:None)
   def run(a,c,i,identity,order,settings_check):
    seen.append(('policy',len(market.inspect_growth_equipment(reward_slots=True)),order,settings_check()))
    return {'state':'processed_unverified'}
   alias=SimpleNamespace(run_blessing_rewards=native)
   install_runtime(module,market,lambda a:'test',alias_modules=(alias,),runner=run)
   self.assertIs(alias.run_blessing_rewards,module.run_blessing_rewards)
   self.assertIs(module.run_blessing_rewards(adapter,context,None),True)
   self.assertEqual(seen,[('native',1),('policy',2,[],True)])
   self.assertEqual(adapter._owner_blessing_policy_outcome['state'],'processed_unverified')
   previous=module.run_blessing_rewards;install_runtime(module,market,lambda a:'test',alias_modules=(alias,),runner=run)
   self.assertIs(previous,module.run_blessing_rewards)
 def test_native_failure_never_starts_new_policy(self):
  seen=[];market=SimpleNamespace(inspect_growth_equipment=lambda *a,**k:[])
  module=SimpleNamespace(run_blessing_rewards=lambda *a:False,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
  install_runtime(module,market,lambda a:'test',runner=lambda *a,**k:seen.append('policy'))
  adapter=SimpleNamespace();self.assertIs(module.run_blessing_rewards(adapter,None,None),False)
  self.assertEqual(adapter._owner_blessing_policy_outcome['state'],'native_unconfirmed');self.assertEqual(seen,[])
if __name__=='__main__':unittest.main()
