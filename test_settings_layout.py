"""Native settings keep their keys/values while display controls move."""
import bootstrap
import copy,json,threading,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from owner_settings_layout import consolidated,GrowthSwitches,GROWTH_SWITCHES,INTERNAL
from tools.gui_settings import SettingsModel,fields
from owner_gear_settings_candidate import Store
from owner_gear_settings_candidate import GearSettings
import owner_growth_report as report

class Layout(unittest.TestCase):
 def setUp(self):
  self.schema=json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8'))
 def test_hidden_fields_remain_in_schema_for_persistence(self):
  before={f['id'] for f in fields(self.schema)};after=consolidated(self.schema)
  self.assertEqual(before,{f['id'] for f in fields(after)})
  model=SettingsModel(after,capabilities=lambda:{f['capability'] for f in fields(after)})
  for key in GROWTH_SWITCHES.values():
   self.assertFalse(model.visible(model.items[key]));self.assertTrue(model.supported(model.items[key]))
  for tab in after['tabs']:
   for group in tab.get('groups',[]):
    ids=[f['id'] for f in group.get('fields',[])]
    if ids and all(i.startswith('custom.') for i in ids):self.assertFalse(model.visible(group))
 def test_input_schema_and_defaults_not_mutated(self):
  before=copy.deepcopy(self.schema);after=consolidated(self.schema)
  self.assertEqual(before,self.schema)
  original={f['id']:f for f in fields(before)}
  for f in fields(after):
   self.assertEqual(f.get('default'),original[f['id']].get('default'))
   self.assertEqual(f.get('enabled',True),original[f['id']].get('enabled',True))
 def test_save_preserves_hidden_custom_and_internal_values(self):
  with tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch') as tmp:
   path=Path(tmp)/'auto-settings.json';schema=consolidated(self.schema)
   model=SettingsModel(schema,path,capabilities=lambda:{f['capability'] for f in fields(schema)})
   original=dict(model.values)
   for k in original:
    if (k.startswith('custom.') or k in INTERNAL) and type(original[k]) is bool:original[k]=True
   model.save(model.mode,original)
   again=SettingsModel(schema,path,capabilities=model.capabilities)
   again.save(again.mode,again.values)
   for key in original:
    if key.startswith('custom.') or key in INTERNAL:self.assertEqual(again.values[key],original[key])

class Switches(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'s','character_name':'c'}),encoding='utf-8')
  self.scope=report.identity(self.root)[0]
  schema=json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8'))
  self.schema=consolidated(schema);self.events=[]
  self.caps=lambda:{f['capability'] for f in fields(self.schema)}
  self.path=self.root/'settings/auto-settings.json'
  self.model().save('main_quest',dict(self.model().values,**{key:False for key in GROWTH_SWITCHES.values()}))
  self.gui=S(project=S(root=self.root),load_settings_model=self.model,
             session=S(snapshot=lambda:{'status':'stopped','worker_alive':False}),refresh_summary=lambda:None)
 def model(self):return SettingsModel(self.schema,self.path,capabilities=self.caps)
 def test_no_changes_preserve_native_values_mode_and_goals(self):
  switches=GrowthSwitches(self.gui,self.scope);before=self.path.read_bytes();called=[]
  switches.save(dict(switches.initial),lambda:called.append(True))
  self.assertEqual(self.path.read_bytes(),before);self.assertEqual(called,[True])
 def test_enable_only_happens_after_successful_target_write(self):
  switches=GrowthSwitches(self.gui,self.scope);wanted=dict(switches.initial,equipment=True)
  def goals():
   self.assertFalse(self.model().values[GROWTH_SWITCHES['equipment']]);self.events.append('goals')
  switches.save(wanted,goals)
  self.assertTrue(self.model().values[GROWTH_SWITCHES['equipment']]);self.assertEqual(self.events,['goals'])
 def test_target_write_failure_never_enables_feature(self):
  switches=GrowthSwitches(self.gui,self.scope);wanted=dict(switches.initial,equipment=True)
  with self.assertRaises(OSError):switches.save(wanted,lambda:(_ for _ in ()).throw(OSError('disk')))
  self.assertFalse(self.model().values[GROWTH_SWITCHES['equipment']])
 def test_disable_is_applied_before_target_write_failure(self):
  model=self.model();model.save(model.mode,dict(model.values,**{GROWTH_SWITCHES['equipment']:True}))
  switches=GrowthSwitches(self.gui,self.scope);wanted=dict(switches.initial,equipment=False)
  with self.assertRaises(OSError):switches.save(wanted,lambda:(_ for _ in ()).throw(OSError('disk')))
  self.assertFalse(self.model().values[GROWTH_SWITCHES['equipment']])
 def test_changed_character_or_running_state_prevents_any_write(self):
  switches=GrowthSwitches(self.gui,self.scope);called=Mock()
  with patch('owner_hunt_rules_candidate.configured_identity',return_value='other'):
   with self.assertRaises(ValueError):switches.save(dict(switches.initial),called)
  self.gui.session.snapshot=lambda:{'status':'running','worker_alive':True}
  with self.assertRaises(ValueError):switches.save(dict(switches.initial),called)
  called.assert_not_called()
 def test_a_pause_may_save(self):
  # The user's rule: settings may change while paused (F2). pc2 11-06 was refused.
  switches=GrowthSwitches(self.gui,self.scope);called=Mock()
  self.gui.session.snapshot=lambda:{'status':'paused','worker_alive':True}
  with patch('owner_hunt_rules_candidate.configured_identity',return_value=self.scope),patch('owner_timetable.live_settings') as live:
   switches.save(dict(switches.initial),called)
  called.assert_called_once()
 def test_other_window_master_change_is_not_overwritten(self):
  switches=GrowthSwitches(self.gui,self.scope);model=self.model()
  model.save(model.mode,dict(model.values,**{GROWTH_SWITCHES['skills']:True}))
  with self.assertRaises(ValueError):switches.save(dict(switches.initial),Mock())
  self.assertTrue(self.model().values[GROWTH_SWITCHES['skills']])
 def test_display_shows_master_off_but_preserves_targets(self):
  document=Store(self.root,self.scope).read();document['skills']['파멸'].update(enabled=True,enhance=49)
  Store(self.root,self.scope).write(document)
  group=next(g for g in report.project(self.root)['groups'] if g['key']=='skills')
  self.assertFalse(group['enabled']);self.assertEqual(next(r for r in group['rows'] if r['name']=='파멸')['target'],'49 / 0')
 def test_new_controls_build_in_hidden_tk_without_starting_a_session(self):
  import tkinter as tk
  from tkinter import ttk
  root=tk.Tk();root.withdraw()
  try:
   switches=GrowthSwitches(self.gui,self.scope)
   editor=GearSettings(root,self.root,self.scope,switches=switches)
   editor.window.withdraw();root.update_idletasks()
   self.assertEqual(set(editor.feature_vars),set(GROWTH_SWITCHES))
   self.assertTrue(all(var.get() is False for var in editor.feature_vars.values()))
   self.assertLess(editor.window.winfo_reqwidth(),1150)
   self.assertLess(editor.window.winfo_reqheight(),900)
   def notebooks(node):
    found=[]
    for child in node.winfo_children():
     if isinstance(child,ttk.Notebook):found.append(child)
     found.extend(notebooks(child))
    return found
   labels=[[notebook.tab(tab,'text') for tab in notebook.tabs()] for notebook in notebooks(editor.window)]
   self.assertIn(['장비','도술','가호','기운','화첩'],labels)
   self.assertIn(['계열 강화·돌파','개별 각성'],labels)
   self.assertFalse(self.model().values[GROWTH_SWITCHES['skills']])
   editor.window.destroy()
  finally:root.destroy()

if __name__=='__main__':unittest.main()
