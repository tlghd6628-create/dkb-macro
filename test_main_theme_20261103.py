"""The main window recolour changes the picture only; no game input and no real settings."""
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
import owner_main
import owner_main_theme as theme

class Theme(unittest.TestCase):
 def setUp(self):
  self.tk=tk.Tk();self.tk.withdraw();self.addCleanup(self.tk.destroy)
  self.calls=[];self.state=['stopped']
  self.log=tk.Text(self.tk,relief='solid',bd=1)
  gui=S(root=self.tk,config={'state_colors':{'stopped':{'background':'#EAB6BC'}},'other':1},log=self.log,_painted_state='stopped',visual_view=None)
  def sync():
   self.calls.append('host')
   key=self.state[0]
   if key!=gui._painted_state:
    self.tk.configure(bg=gui.config['state_colors'][key]['background']);gui._painted_state=key
   return 'result'
  gui.sync_compact_state=sync;self.gui=gui
 def test_every_run_state_keeps_its_own_colour(self):
  colours={theme.STATE_COLORS[k]['background'] for k in ('running','paused','stopped')}
  self.assertEqual(len(colours),3)
  self.assertEqual(len({theme.STATE_COLORS[k]['accent'] for k in theme.STATE_COLORS}),3)
  self.assertEqual(set(theme.BUTTON_COLORS),{'start','pause','stop','details'})
 def test_host_repaint_uses_the_new_colours_and_old_pink_is_gone(self):
  theme.install(self.gui)
  self.assertEqual(self.tk.cget('bg'),theme.STATE_COLORS['stopped']['background'])
  self.state[0]='running';self.assertEqual(self.gui.sync_compact_state(),'result')
  self.assertEqual(self.tk.cget('bg'),theme.STATE_COLORS['running']['background'])
  self.assertNotIn('#EAB6BC',str(self.gui.config['state_colors']))
 def test_other_config_and_profile_file_are_untouched(self):
  profile=bootstrap.A/'profiles/DKB/config/base_gui.json';before=profile.read_bytes()
  theme.install(self.gui)
  self.assertEqual(self.gui.config['other'],1);self.assertEqual(profile.read_bytes(),before)
 def test_install_is_idempotent(self):
  theme.install(self.gui);wrapped=self.gui.sync_compact_state
  theme.install(self.gui);self.assertIs(self.gui.sync_compact_state,wrapped)
 def test_button_commands_and_states_are_not_changed(self):
  fired=[];button=ttk.Button(self.tk,text='시작',style='Start.RunControl.TButton',command=lambda:fired.append(1),state='disabled')
  theme.install(self.gui)
  self.assertEqual(str(button.cget('state')),'disabled')
  button.configure(state='normal');button.invoke();self.assertEqual(fired,[1])
  self.assertEqual(ttk.Style(self.tk).lookup('Start.RunControl.TButton','background'),theme.ACCENT)
 def test_log_gets_a_soft_border(self):
  theme.install(self.gui)
  self.assertEqual(int(str(self.log.cget('borderwidth'))),0);self.assertEqual(self.log.cget('highlightbackground'),theme.BORDER)
 def test_colour_failure_does_not_stop_the_installs_that_follow(self):
  gui=S(_owner_quest_schema=True,_owner_main=S(refresh=lambda schedule=False:None))
  with patch.object(theme,'install',side_effect=RuntimeError('paint')),self.assertLogs('project_gui.DKB',level='ERROR'):
   owner_main.install(gui)

if __name__=='__main__':unittest.main()
