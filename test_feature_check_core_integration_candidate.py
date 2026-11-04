"""Exercise the real check core and UI using a temporary, non-game profile."""
exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest,tempfile,json,threading,shutil
from pathlib import Path
from types import SimpleNamespace as NS
import tkinter as tk
from tkinter import ttk
from owner_feature_check_ui_candidate import FeaturePanel
from project_adapter import protected_assets

FIXTURES=('버튼_전체매뉴_임무.png','체크_임무.png')

class Session:
 def snapshot(self):return {'status':'stopped','worker_alive':False}
 def start(self):raise AssertionError('macro must not start')
 def stop(self):raise AssertionError('macro must not stop')

class Integration(unittest.TestCase):
 def test_real_core_records_results_without_input_and_ui_exposes_report(self):
  with tempfile.TemporaryDirectory() as tmp:
   rootpath=Path(tmp);(rootpath/'settings').mkdir();target=rootpath/'profiles/DKB/templates';target.mkdir(parents=True)
   (rootpath/'settings/auto-settings.json').write_text(json.dumps({'values':{'auto_rewards.album.enabled':True}}),encoding='utf-8')
   # Reuse the installed protected-asset reader instead of a moved old build tree.
   for name in FIXTURES:
    (target/name).write_bytes(protected_assets.read_bytes(A/'profiles/DKB/templates'/name))
   root=tk.Tk();root.withdraw()
   try:
    gui=NS(root=root,closed=threading.Event(),session=Session(),project=NS(root=rootpath),
      _owner_main=NS(frame=ttk.Frame(root)),visual_view=NS(widgets={},originals={}),
      input_preparation=NS(busy=lambda:False),game_hint=tk.StringVar(root),start_requested=lambda:None,
      launch_flow=NS(start=lambda:None))
    gui.start_button=ttk.Button(root);panel=FeaturePanel(gui);panel.open()
    self.assertTrue(panel.start(['main','album']));panel.worker.join(timeout=15);self.assertFalse(panel.active());panel.poll()
    main=panel.tree.item('main','values');album=panel.tree.item('album','values')
    # Columns are 기능/설정/화면/단계/결과; a contract-only row never claims a screen.
    self.assertEqual((main[2],main[4]),('미검증','미검증 · 화면 미점검'))
    self.assertEqual((album[1],album[2],album[3],album[4]),('사용 불가','제외','미연결','제외 · 사용 불가'))
    self.assertIsNotNone(panel.report_path);report=json.loads(Path(panel.report_path).read_text(encoding='utf-8'))
    self.assertFalse(report['gameplay_execution_tested']);self.assertEqual({row['id'] for row in report['rows']},{'main','album'})
    self.assertIn('coverage',report);self.assertEqual(report['stopped_after'],None)
    for row in report['rows']:
     self.assertIn('steps',row);self.assertEqual(row['steps'][0]['stage'],'settings');self.assertEqual(row['steps'][1]['stage'],'wiring')
    self.assertIn(str(rootpath),panel.report_path);self.assertIn('자동 저장',panel.status.get())
   finally:root.destroy()
if __name__=='__main__':unittest.main(verbosity=2)
