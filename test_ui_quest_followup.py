import bootstrap
import copy,json,logging,queue,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import tkinter as tk
from tools.gui_settings import SettingsModel,fields
from user_log import LogQueue
from owner_manual_diagnostics import log_transfer
from owner_settings_layout import consolidated,GROWTH_SWITCHES
from owner_settings_console import NativeFields,SettingsConsole,category
from owner_schedule_settings import rows
from owner_timetable import JOBS
import owner_timetable as timetable
from owner_mission_controller import wait_selection
from owner_story_groups import Groups,StorySelectionPending

class Diagnostic(unittest.TestCase):
 def test_actual_user_log_queue_retains_success_wait_and_failure(self):
  q=queue.Queue();logger=logging.getLogger('diagnostic-test');handler=LogQueue(q)
  logger.addHandler(handler);logger.setLevel(logging.INFO)
  try:
   log_transfer(logger,{'phase':'sent','logs':88,'pictures':3,'id':'fixture'})
   self.assertIn('진단 전송 완료',q.get_nowait())
   log_transfer(logger,{'phase':'waiting','id':'fixture'});self.assertIn('전송 대기',q.get_nowait())
   log_transfer(logger,{'phase':'failed'});self.assertIn('전송 실패',q.get_nowait())
   log_transfer(logger,{'phase':'sending'});self.assertTrue(q.empty())
  finally:logger.removeHandler(handler)

class Console(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.path=self.root/'settings/auto-settings.json'
  self.schema=consolidated(json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8')))
  self.caps=lambda:{f['capability'] for f in fields(self.schema)}
  self.model=lambda:SettingsModel(self.schema,self.path,capabilities=self.caps)
  self.gui=S(load_settings_model=self.model,session=S(snapshot=lambda:{'status':'stopped','worker_alive':False}),refresh_summary=lambda:None,project=S(root=self.root))
  self.tk=tk.Tk();self.tk.withdraw();self.addCleanup(self.close_tk);self.gui.root=self.tk
 def close_tk(self):
  self.tk.update();self.tk.destroy()
 def test_all_editable_basic_roles_have_one_category(self):
  self.assertEqual(category('auto_challenge.secret_exploration.enabled'),'비경·보스')
  self.assertEqual(category('auto_growth.clan_cooperative_training.lamp'),'문파')
  native=NativeFields(self.gui)
  for name in ('기본 설정','보상·정리','비경·보스','수련','문파'):
   native.build(tk.Frame(self.tk),name)
  self.assertNotIn(GROWTH_SWITCHES['equipment'],native.vars)
  self.assertTrue(all(not key.startswith('custom.') for key in native.vars))
  self.assertIn('auto_schedule.field_boss.enabled',native.vars)
  self.assertNotIn('common.daily_restart.minute',native.vars)
 def test_new_console_tabs_and_default_schedule_are_constructible(self):
  console=SettingsConsole(self.gui,{})
  console.window.withdraw();self.tk.update_idletasks()
  self.assertLess(console.window.winfo_reqwidth(),1200)
  self.assertIsNotNone(console.native.vars.get('common.potion_and_favorite.enabled'))
  console.window.destroy()
 def test_native_save_does_not_overwrite_master_changed_in_growth_dialog(self):
  self.model().save('main_quest',self.model().values)
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'보상·정리')
  key='auto_rewards.mail.enabled';native.vars[key].set(not native.baseline[key])
  external=self.model();external.save(external.mode,dict(external.values,**{GROWTH_SWITCHES['equipment']:True}))
  native.save();self.assertTrue(self.model().values[GROWTH_SWITCHES['equipment']])
 def test_default_weekly_is_tuesday_and_events_mail_are_not_manual(self):
  cfg={'jobs':{j.key:{'time':j.clock} for j in JOBS},'jitter_seconds':60}
  projected={r[0]:r for r in rows(cfg)}
  self.assertEqual(projected['weekly_missions'][2],'화')
  self.assertEqual(projected['weekly_missions'][3],'23:45')
  self.assertEqual(projected['treasure'][2],'일회성')
  self.assertNotIn('mail',projected);self.assertNotIn('events',projected)
 def test_multiple_schedule_edits_are_validated_before_any_write(self):
  cfg=timetable.config(self.root);path=self.root/'settings/owner-timetable.json';before=path.read_bytes()
  changes={'guide':{'clock':'08:10','weekdays':[0,1,2,3,4,5,6],'jitter_seconds':15},
           'tower':{'clock':'25:80','weekdays':[1],'jitter_seconds':60}}
  with self.assertRaises(ValueError):timetable.save_user_rules(self.root,changes,expected_rules={key:cfg['jobs'][key] for key in changes})
  self.assertEqual(path.read_bytes(),before)
 def test_schedule_drafts_survive_selecting_another_row(self):
  from owner_schedule_settings import ScheduleEditor
  editor=ScheduleEditor(tk.Frame(self.tk),self.root)
  editor.tree.selection_set('guide');editor.select();editor.hour.set('08');editor.minute.set('12')
  editor.tree.selection_set('tower');editor.select()
  editor.tree.selection_set('guide');editor.select()
  self.assertEqual((editor.hour.get(),editor.minute.get()),('08','12'))
  self.assertTrue(editor.save())
  self.assertEqual(timetable.config(self.root)['jobs']['guide']['time'],'08:12')

class Quest(unittest.TestCase):
 def test_first_visible_handoff_failure_does_not_choose_a_lower_row(self):
  book=S(path='fixture',item={'active':None,'quests':{'first':{'title':'first'},'next':{'title':'next'}}},commit=lambda:None)
  ui=S(frame=lambda:'frame');g=Groups(ui,book,100000);actions=[]
  g.compact=lambda:None;g.identify=lambda f,r:r['key'];g.select=lambda key:actions.append(key) or False
  g._last_unlocated='first'
  with patch('owner_story_groups.group_rows',return_value=[{'y':120,'key':'first'},{'y':260,'key':'next'}]),patch('owner_story_groups.completed_root',return_value=False),patch('owner_story_groups.dots',return_value=True),patch('owner_story_groups.suitable',return_value=True),patch('owner_story_groups.group_eligible',return_value=True),patch('owner_story_groups.locate_backoff',return_value=False),patch('owner_story_groups.mark_locate_backoff'):
   with self.assertRaises(StorySelectionPending):g.choose(['first','next'])
  self.assertEqual(actions,['first'])
 def test_first_visible_root_wins_even_when_saved_root_is_visible_below(self):
  book=S(path='fixture',item={'active':'old','quests':{'first':{'title':'first'},'old':{'title':'old'}}},commit=lambda:None)
  ui=S(frame=lambda:'frame');g=Groups(ui,book,100000);actions=[]
  g.compact=lambda:None;g.identify=lambda f,r:r['key'];g.select=lambda key:actions.append(key) or True;g.activate=lambda key:None
  with patch('owner_story_groups.group_rows',return_value=[{'y':120,'key':'first'},{'y':260,'key':'old'}]),patch('owner_story_groups.completed_root',return_value=False),patch('owner_story_groups.dots',return_value=True),patch('owner_story_groups.suitable',return_value=True),patch('owner_story_groups.group_eligible',return_value=True):
   self.assertEqual(g.choose(['old','first'],prefer_saved=True),'first')
  self.assertEqual(actions,['first'])
 def test_handoff_wait_keeps_menu_and_does_not_count_death_or_catalog_error(self):
  adapter=S(_owner_catalog_errors=2);ui=Mock();context=S(wait=Mock())
  with patch('owner_mission_controller.time.monotonic',return_value=100):wait_selection(adapter,ui,context,StorySelectionPending('fixture'))
  self.assertEqual(adapter._owner_catalog_errors,2);ui.close_known.assert_not_called();context.wait.assert_called_once_with(1)
  with patch('owner_mission_controller.time.monotonic',return_value=131),self.assertRaises(RuntimeError):
   wait_selection(adapter,ui,context,StorySelectionPending('fixture'))

if __name__=='__main__':unittest.main()
