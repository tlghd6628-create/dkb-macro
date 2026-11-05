"""The raid preset loads inside the raid only. Fake flow and fake input; no game."""
import bootstrap
import json,unittest
from types import SimpleNamespace as S
import owner_raid_preset as raid
from owner_settings_layout import consolidated

def scenario(values,*,fail=None,events=None):
 events=[] if events is None else events
 class Flow:
  def __init__(self,adapter,context,inputs):events.append('init')
  def entry(self,stage):events.append('entry')
  def matching(self,stage,bulk):events.append('matching')
  def auto_cycle(self):events.append('auto_cycle')
  def auto_state(self):events.append('auto_state');return 'on'
  def combat(self,*,wait_for_exit=False):
   events.append('combat');self.auto_state();self.auto_cycle();self.auto_state();return 'fought'
 module=S()
 adapter=S(values=values)
 def _run(a,c,i):
  flow=Flow(a,c,i);flow.entry(1);flow.matching(1,True);flow.combat();events.append('left');return 'done'
 module._run=_run
 def change(a,c,i,*,enabled_key='common',choice_key='common'):
  events.append('preset:'+('raid' if enabled_key==raid.ENABLED else 'common'))
  if fail:raise fail
 raid.install_on(Flow,module,change)
 return module,Flow,adapter,events

class Timing(unittest.TestCase):
 def test_off_changes_nothing(self):
  module,_,adapter,events=scenario({raid.ENABLED:False,raid.COMMON:True})
  self.assertEqual(module._run(adapter,None,None),'done')
  self.assertFalse([e for e in events if e.startswith('preset')])
 def test_loads_once_after_entry_and_matching_inside_the_raid(self):
  module,_,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:False})
  module._run(adapter,None,None)
  self.assertEqual(events.count('preset:raid'),1)
  at=events.index('preset:raid')
  self.assertLess(events.index('entry'),at);self.assertLess(events.index('matching'),at);self.assertLess(events.index('combat'),at)
  self.assertLess(at,events.index('auto_state'))
 def test_everyday_preset_returns_after_leaving_when_it_is_on(self):
  module,_,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:True})
  module._run(adapter,None,None)
  self.assertEqual([e for e in events if e.startswith('preset')],['preset:raid','preset:common'])
  self.assertLess(events.index('left'),events.index('preset:common'))
 def test_everyday_preset_off_stays_on_the_raid_preset(self):
  module,_,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:False})
  module._run(adapter,None,None)
  self.assertNotIn('preset:common',events)
 def test_raid_that_never_reaches_combat_changes_no_preset(self):
  module,Flow,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:True})
  flow=Flow(adapter,None,None);flow.entry(1);flow.matching(1,True);flow.auto_state()
  self.assertFalse([e for e in events if e.startswith('preset')])
 def test_resumed_raid_loads_it_and_restores_on_exit(self):
  module,Flow,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:True})
  Flow(adapter,None,None).combat(wait_for_exit=True)
  self.assertEqual([e for e in events if e.startswith('preset')],['preset:raid','preset:common'])
 def test_failed_change_does_not_stop_the_raid_or_restore_nothing(self):
  module,_,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:True},fail=RuntimeError('menu'))
  with self.assertLogs('project_gui.DKB',level='ERROR'):
   self.assertEqual(module._run(adapter,None,None),'done')
  # A failure can be a switch that went through unread, so going back is still tried, and that may fail too.
  self.assertEqual([e for e in events if e.startswith('preset')][0],'preset:raid')
  self.assertIn('left',events)
 def test_stop_during_the_change_propagates(self):
  from biol_base.session import Cancelled
  module,_,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:True},fail=Cancelled())
  with self.assertRaises(Cancelled):module._run(adapter,None,None)
  self.assertNotIn('left',events)
 def test_install_twice_wraps_once(self):
  module,Flow,adapter,events=scenario({raid.ENABLED:True,raid.COMMON:False})
  raid.install_on(Flow,module,lambda *a,**k:events.append('second'))
  module._run(adapter,None,None)
  self.assertNotIn('second',events);self.assertEqual(events.count('preset:raid'),1)

class Native(unittest.TestCase):
 def test_real_flow_has_every_patched_step(self):
  from project_adapter import boss_raid
  for name in ('__init__','combat','auto_cycle','auto_state'):self.assertTrue(callable(getattr(boss_raid.RaidFlow,name)),name)
  self.assertTrue(callable(boss_raid._run))
 def test_native_routine_accepts_the_raid_keys(self):
  import inspect
  from project_adapter.skill_preset import run_skill_preset
  self.assertEqual({'enabled_key','choice_key'}-set(inspect.signature(run_skill_preset).parameters),set())
 def test_schema_field_defaults_off_and_is_next_to_the_raid(self):
  schema=consolidated(json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8')))
  raid.add_fields(schema);raid.add_fields(schema)
  fields=[f for t in schema['tabs'] for g in t['groups'] for f in g['fields']]
  switch=[f for f in fields if f['id']==raid.ENABLED];choice=[f for f in fields if f['id']==raid.CHOICE]
  self.assertEqual((len(switch),len(choice)),(1,1))
  self.assertIs(switch[0]['default'],False);self.assertEqual(choice[0]['enabled_if'],raid.ENABLED)
  self.assertEqual(switch[0]['capability'],'auto_schedule.boss_raid')

if __name__=='__main__':unittest.main()
