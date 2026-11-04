"""Exercise the settings dialog with a temporary profile, without game input."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tkinter as tk
from tkinter import ttk
from owner_gear_settings_candidate import GearSettings, Store

class GearGUI(unittest.TestCase):
    def test_tabs_and_custom_skill_targets_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory,'test-server / test-character');original=store.read()
            original['individual']['대폭발']={'enabled':False,'awaken':None,'breakthrough':3}
            store.write(original)
            root = tk.Tk()
            root.withdraw()
            try:
                dialog = GearSettings(root, directory, 'test-server / test-character')
                dialog.window.withdraw()
                dialog.window.update_idletasks()
                notebooks = []
                def visit(widget):
                    if isinstance(widget, ttk.Notebook): notebooks.append(widget)
                    for child in widget.winfo_children(): visit(child)
                visit(dialog.window)
                self.assertEqual(len(notebooks), 1)
                notebook = notebooks[0]
                self.assertEqual([notebook.tab(tab, 'text') for tab in notebook.tabs()], ['장비', '도술', '개별 도술','가호','기운','화첩'])
                self.assertEqual(len(dialog.skill_vars), 12)
                self.assertEqual(len(dialog.individual.catalog), 105)
                self.assertEqual(len(dialog.individual.tree.get_children()), 105)
                self.assertNotIn('goal_break',dialog.individual.tree['columns'])
                self.assertLessEqual(dialog.window.winfo_reqheight(), dialog.window.winfo_screenheight())
                self.assertLessEqual(dialog.window.winfo_reqwidth(), dialog.window.winfo_screenwidth())
                dialog.skill_vars['절명']['enabled'].set(True)
                dialog.skill_vars['절명']['enhance'].set('32')
                dialog.skill_vars['파멸']['enhance'].set('47')
                dialog.album_mode.set('완성')
                dialog.blessing_vars['1번']['enabled'].set(True)
                dialog.blessing_vars['1번']['enhance'].set('49')
                dialog.blessing_vars['1번']['breakthrough'].set('0')
                dialog.blessing_equip.set(True)
                dialog.blessing_rank[0].set('나비');dialog.blessing_rank[1].set('봉황')
                dialog.energy_vars['생명']['enabled'].set(True)
                dialog.energy_vars['생명']['stage'].set('5')
                dialog.individual.tree.selection_set(dialog.individual.items['대폭발'])
                dialog.individual.select()
                dialog.individual.enabled.set(True)
                dialog.individual.awaken.set('1')
                dialog.save()
                saved = Store(directory, 'test-server / test-character').read()
                self.assertEqual(saved['skills']['절명'], {'enabled': True, 'enhance': 32,'breakthrough':0})
                self.assertEqual(saved['skills']['파멸']['enhance'], 47)
                # Album is temporarily unavailable: a programmatic change to
                # the disabled selector must not overwrite the saved choice.
                self.assertEqual(saved['album']['mode'],'조각 등록만')
                self.assertEqual(saved['blessings']['1번'],{'enabled':True,'enhance':49,'breakthrough':0})
                self.assertEqual(saved['blessing_equip'],{'enabled':True,'priorities':['나비','봉황']})
                self.assertEqual(saved['energies']['생명'],{'enabled':True,'stage':5})
                self.assertEqual(saved['individual']['대폭발'],{'enabled':True,'awaken':1,'breakthrough':3})
                self.assertEqual(saved['grades']['희귀']['enhance'], 50)
            finally:
                root.destroy()

    def test_switching_rows_keeps_edits_and_filter_limits_display(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory,'test');original=store.read()
            original['individual']['대폭발']={'enabled':False,'awaken':None,'breakthrough':4}
            store.write(original)
            root = tk.Tk();root.withdraw()
            try:
                dialog=GearSettings(root,directory,'test');dialog.window.withdraw()
                edit=dialog.individual
                edit.tree.selection_set(edit.items['대폭발']);edit.select()
                edit.enabled.set(True);edit.awaken.set('2')
                edit.tree.selection_set(edit.items['방패 밀기']);edit.select()
                self.assertEqual(edit.saved['대폭발'],{'enabled':True,'awaken':2,'breakthrough':4})
                edit.style.set('파멸');edit.change_filter()
                self.assertEqual(len(edit.tree.get_children()),13)
                self.assertIn('대폭발',edit.items)
                self.assertNotIn('방패 밀기',edit.items)
                self.assertEqual(edit.export()['대폭발']['breakthrough'],4)
                edit.style.set('전체');edit.query.set('대폭발');edit.change_filter()
                self.assertEqual(list(edit.items),['대폭발'])
            finally:root.destroy()

    def test_bad_target_rejected_before_profile_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=tk.Tk();root.withdraw()
            try:
                dialog=GearSettings(root,directory,'test');dialog.window.withdraw()
                editor=dialog.individual
                editor.tree.selection_set(editor.items['대폭발']);editor.select()
                editor.awaken.set('-1')
                with self.assertRaises(ValueError):editor.export()
                self.assertFalse(Store(directory,'test').path.exists())
            finally:root.destroy()

if __name__ == '__main__': unittest.main()
