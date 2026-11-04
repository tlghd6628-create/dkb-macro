"""The settings redesign changes the picture only; no game input and no real settings."""
import bootstrap
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
from tools.gui_settings import SettingsModel,fields
from owner_settings_layout import consolidated
from owner_settings_console import NativeFields,SettingsConsole,category
import owner_settings_theme as theme

PAGES=('기본 설정','보상·정리','문파','사냥터','비경·보스','수련')
def walk(widget):
 yield widget
 for child in widget.winfo_children():yield from walk(child)

class Base(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'settings').mkdir()
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'무이2','character_name':'테스트'},ensure_ascii=False),encoding='utf-8')
  self.schema=consolidated(json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf-8')))
  caps=lambda:{f['capability'] for f in fields(self.schema)}
  self.model=lambda:SettingsModel(self.schema,self.root/'settings/auto-settings.json',capabilities=caps)
  self.tk=tk.Tk();self.tk.withdraw();self.addCleanup(self.close)
  self.gui=S(root=self.tk,load_settings_model=self.model,session=S(snapshot=lambda:{'status':'stopped','worker_alive':False}),
             refresh_summary=lambda:None,project=S(root=self.root),_owner_telemetry=S(state='',device=None,last_sent=0))
 def close(self):
  for token in self.tk.tk.call('after','info'):self.tk.after_cancel(token)
  self.tk.update();self.tk.destroy()
 def visible(self,name):
  model=self.model()
  shown={f['id']:model.visible(t) and model.visible(g) for t in self.schema['tabs'] for g in t['groups'] for f in g['fields']}
  return {i['id'] for i in fields(self.schema) if category(i['id'])==name and shown[i['id']] and i.get('visible',True) is not False}

class NativePages(Base):
 def test_each_page_shows_exactly_the_same_settings_as_before(self):
  for name in PAGES:
   native=NativeFields(self.gui);native.build(tk.Frame(self.tk),name)
   self.assertEqual(set(native.vars),self.visible(name),name)
   from owner_settings_console import UNAVAILABLE
   self.assertEqual({item['id'] for item,_ in native.controls},self.visible(name)-set(UNAVAILABLE),name)
 def test_every_item_is_in_exactly_one_section_in_schema_order(self):
  for name in PAGES:
   visible=self.visible(name)
   items=[i for i in fields(self.schema) if i['id'] in visible]
   placed=[i['id'] for _,rows in theme.sections(name,items) for i in rows]
   self.assertEqual(sorted(placed),sorted(i['id'] for i in items),name)
 def test_unknown_field_is_shown_rather_than_lost(self):
  rows=theme.sections('보상·정리',[{'id':'auto_rewards.guide.enabled'},{'id':'new.feature.enabled'}])
  self.assertEqual(rows[-1][0],'기타');self.assertEqual(rows[-1][1][0]['id'],'new.feature.enabled')
 def test_labels_are_display_only(self):
  before=json.dumps(self.schema,ensure_ascii=False,sort_keys=True)
  self.assertEqual(theme.display_label({'id':'x','label':'• 석등 선택 :'}),'석등 선택')
  self.assertEqual(theme.display_label({'id':'auto_growth.spirit_training.interval_minutes','label':'분 주기'}),'수련 주기 (분)')
  for name in PAGES:NativeFields(self.gui).build(tk.Frame(self.tk),name)
  self.assertEqual(json.dumps(self.schema,ensure_ascii=False,sort_keys=True),before)
 def test_dependent_control_still_follows_its_switch(self):
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'기본 설정')
  control={item['id']:w for item,w in native.controls}
  native.vars['common.skill_preset.enabled'].set(False);self.tk.update()
  self.assertIn('disabled',str(control['common.skill_preset.choice'].cget('state')))
  native.vars['common.skill_preset.enabled'].set(True);self.tk.update()
  self.assertEqual(str(control['common.skill_preset.choice'].cget('state')),'readonly')

class Requested(Base):
 def test_daily_restart_is_gone_from_every_page_but_its_saved_value_stays(self):
  model=self.model();key='common.daily_restart.enabled'
  model.save('main_quest',dict(model.values,**{key:True}))
  path=self.root/'settings/auto-settings.json'
  native=NativeFields(self.gui)
  for name in PAGES:native.build(tk.Frame(self.tk),name)
  self.assertFalse([k for k in native.vars if k.startswith('common.daily_restart.')])
  native.save()
  self.assertIs(self.model().values[key],True)
 def _membership(self,paid):
  from owner_membership import set_paid,paid as read
  set_paid(self.root,paid)
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'기본 설정')
  return native,read
 def test_membership_is_on_the_basic_page_and_shows_the_saved_choice(self):
  native,_=self._membership(True)
  self.assertIs(native.member.get(),True)
  self.assertTrue([w for w in walk(self.tk) if w.winfo_class()=='TCheckbutton' and str(w.cget('text'))=='멤버십 결제'])
 def test_membership_saves_only_with_the_save_button(self):
  native,read=self._membership(False)
  native.member.set(True);self.assertIs(read(self.root),False)
  with self.assertLogs('project_gui.DKB',level='INFO'):native.save()
  self.assertIs(read(self.root),True)
 def test_membership_file_is_not_rewritten_when_unchanged(self):
  native,_=self._membership(True);path=self.root/'settings/owner-membership.json'
  before=path.stat().st_mtime_ns;native.save();self.assertEqual(path.stat().st_mtime_ns,before)
 def test_other_pages_do_not_carry_membership(self):
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'보상·정리')
  self.assertFalse(hasattr(native,'member'))
 def test_main_window_no_longer_offers_membership(self):
  import owner_main,inspect
  self.assertNotIn('member_button',inspect.getsource(owner_main.MainPanel))
 def test_clan_settings_have_their_own_page_and_left_the_others(self):
  self.assertEqual(self.visible('문파')&{'auto_schedule.clan_boss_request.enabled','auto_growth.clan_cooperative_training.enabled','auto_growth.clan_cooperative_training.lamp'},
                   {'auto_schedule.clan_boss_request.enabled','auto_growth.clan_cooperative_training.enabled','auto_growth.clan_cooperative_training.lamp'})
  for name in ('수련','비경·보스','보상·정리'):
   self.assertFalse({k for k in self.visible(name) if 'clan' in k},name)
 def test_presets_are_labelled_for_their_situation_and_sit_on_the_first_page(self):
  from owner_raid_preset import add_fields
  add_fields(self.schema)
  for key,text in (('common.skill_preset.enabled','메인·서사퀘 진행'),('auto_schedule.field_boss.skill_preset.enabled','월드 보스'),('auto_schedule.boss_raid.skill_preset.enabled','레이드')):
   self.assertEqual(category(key),'기본 설정');self.assertEqual(theme.display_label({'id':key,'label':'x'}),text)
   self.assertEqual(category(key.replace('.enabled','.choice')),'기본 설정')
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'기본 설정')
  self.assertIn('auto_schedule.boss_raid.skill_preset.choice',native.vars)
 def test_potion_label_drops_hunting_but_the_saved_key_stays(self):
  self.assertEqual(theme.display_label({'id':'common.potion_and_favorite.enabled','label':'자동 물약구매 및 사냥터'}),'자동 물약구매')
 def test_coupons_show_o_and_x_from_the_native_record(self):
  from owner_settings_console import coupon_status
  root=self.root;(root/'profiles/DKB/config').mkdir(parents=True)
  (root/'profiles/DKB/config/coupons.json').write_text(json.dumps({'coupons':[{'code':'가','enabled':True},{'code':'나','enabled':True},{'code':'끔','enabled':False}]},ensure_ascii=False),encoding='utf-8')
  (root/'settings/coupon_results.json').write_text(json.dumps({'characters':{json.dumps({'pc_alias':'0000'}):{'가':{'completed':True,'status':'LIMIT_EXCEEDED'},'나':{'completed':False}}}},ensure_ascii=False),encoding='utf-8')
  before=(root/'settings/coupon_results.json').read_bytes()
  self.assertEqual(coupon_status(root),[('가',True),('나',False)])
  self.assertEqual((root/'settings/coupon_results.json').read_bytes(),before)
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'기본 설정')
  marks=[str(w.cget('text')) for w in walk(self.tk) if w.winfo_class()=='TLabel' and str(w.cget('text')) in ('O','X')]
  self.assertEqual(marks,['O','X'])
 def test_missing_coupon_record_does_not_stop_the_page(self):
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'기본 설정')
  self.assertIn('main_quest.first_coupon.enabled',native.vars)

class Console(Base):
 def console(self):
  console=SettingsConsole(self.gui,{});console.window.withdraw();self.tk.update_idletasks();self.addCleanup(console.window.destroy);return console
 def test_every_page_is_reachable_and_group_titles_lead_to_a_page(self):
  console=self.console();nav=console.navigation
  labels=[nav.item(k,'text').strip() for k in nav.get_children() if k in console.destinations]
  self.assertEqual(labels,['기본 설정','보상·정리','사냥터','상점','아이템 사용','문파','장비','도술','가호','기운','화첩','요일·시간','비경·보스','수련','진단'])
  group=next(k for k in nav.get_children() if k not in console.destinations and nav.item(k,'text')=='성장')
  nav.selection_set(group);self.tk.update()
  self.assertEqual(nav.item(nav.selection()[0],'text').strip(),'장비')
 def test_only_one_save_button_remains_and_it_saves_every_editor(self):
  console=self.console()
  shown=[w for w in walk(console.window) if w.winfo_class()=='TButton' and str(w.cget('text')) in theme.INNER_SAVES and w.winfo_manager()]
  self.assertEqual(len(shown),1);self.assertEqual(str(shown[0].cget('style')),'DkbPrimary.TButton')
  calls=[]
  for editor in console.editors:
   original=editor.save
   editor.save=lambda original=original,editor=editor:(calls.append(type(editor).__name__ if not callable(editor) else 'x'),original())[1]
  console.schedule_editor.save=lambda **k:calls.append('schedule') or True
  console.native.save=lambda:calls.append('native') or True
  self.assertIs(console.save(),True)
  self.assertEqual(len(calls),len(console.editors)+2);self.assertEqual(calls[-2:],['native','schedule'])
 def test_no_change_save_keeps_the_native_settings_file_identical(self):
  model=self.model();model.save('main_quest',model.values)
  path=self.root/'settings/auto-settings.json';before=json.loads(path.read_text(encoding='utf-8'))
  console=self.console();self.assertIs(console.save(),True)
  self.assertEqual(json.loads(path.read_text(encoding='utf-8')),before)
 def test_main_window_state_colour_does_not_reach_the_console(self):
  console=self.console();style=ttk.Style(self.tk)
  for name in ('.','TFrame','TLabel','TCheckbutton','TLabelframe'):style.configure(name,background='#EAB6BC')
  for widget in walk(console.window):
   if widget.winfo_class() in theme.CLASSES and widget.winfo_class()!='TNotebook':
    name=str(widget.cget('style'))
    self.assertTrue(name.startswith('Dkb'),(widget,name))
    self.assertNotEqual(str(style.lookup(name,'background')),'#EAB6BC',name)
 def test_rows_added_later_get_the_same_look(self):
  console=self.console()
  hunt=next(e for e in console.editors if type(e).__name__=='HuntSettings')
  hunt.add();new=hunt.rows[-1][0]
  theme.restyle(new)
  self.assertEqual(str(new.cget('style')),'Dkb.TFrame')
 def test_standalone_editors_are_not_affected(self):
  from owner_hunt_settings_candidate import HuntSettings
  editor=HuntSettings(self.tk,self.root);self.addCleanup(editor.window.destroy)
  buttons=[w for w in walk(editor.window) if w.winfo_class()=='TButton' and str(w.cget('text'))=='저장']
  self.assertEqual(len(buttons),1);self.assertTrue(buttons[0].winfo_manager())

if __name__=='__main__':unittest.main()
