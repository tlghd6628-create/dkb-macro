"""Hidden-widget and fake-callback checks; no installed settings or game."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,unittest,tkinter as tk
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from test_settings_theme_20261103 import Base,walk
from owner_settings_console import NativeFields,SettingsConsole,UNAVAILABLE
KEY='auto_rewards.training_log.enabled'


class Tests(Base):
 def test_checkbox_and_test_disabled_reason_visible_and_value_preserved(self):
  native=NativeFields(self.gui);original=native.model.values[KEY]
  frame=tk.Frame(self.tk);native.build(frame,'보상·정리');native.refresh_controls()
  widget=next(w for item,w in native.controls if item['id']==KEY)
  self.assertEqual(str(widget.cget('state')),'disabled')
  row=widget.master;buttons=[w for w in row.winfo_children() if w.winfo_class()=='TButton']
  self.assertEqual(len(buttons),1);self.assertEqual(str(buttons[0].cget('state')),'disabled')
  labels=[w for w in row.winfo_children() if w.winfo_class()=='TLabel']
  self.assertTrue(any(self.tk.getvar(str(w.cget('textvariable')))==UNAVAILABLE[KEY] for w in labels))
  self.assertEqual(native.model.values[KEY],original);self.assertEqual(native.vars[KEY].get(),original)
  self.assertFalse((self.root/'settings/auto-settings.json').exists())
 def test_callback_cannot_start_or_save_even_if_called_directly(self):
  fake=S(save=Mock());result=Mock()
  with patch('owner_reward_action_test.controller') as controller:
   SettingsConsole.test_action(fake,KEY,result)
  result.set.assert_called_once_with(UNAVAILABLE[KEY]);fake.save.assert_not_called();controller.assert_not_called()
 def test_other_reward_switches_remain_editable(self):
  native=NativeFields(self.gui);native.build(tk.Frame(self.tk),'보상·정리')
  for key in ('auto_rewards.mail.enabled','auto_rewards.event.enabled','auto_register.equipment_disassembly.enabled'):
   widget=next(w for item,w in native.controls if item['id']==key)
   self.assertNotEqual(str(widget.cget('state')),'disabled',key)


if __name__=='__main__':unittest.main()
