"""Feature-check safety contracts with temporary files; no game operations."""
import sys,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_feature_check_catalog_candidate as catalog
import owner_feature_checks_candidate as core
def config(path):raise AssertionError('old planner must not call the disk-writing config')

class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);(self.root/'profiles/DKB/templates').mkdir(parents=True);(self.root/'settings').mkdir()
  (self.root/'settings/auto-settings.json').write_text(json.dumps({'mode':'sub_quest','values':{'enabled.test':True}}),encoding='utf-8')
  self.items=[{'id':'a','name':'점검 A','settings':['enabled.test'],'native':[],'templates':[]}]
 def run_check(self,probe=None,cancel=None):
  seen=[]
  with patch.object(catalog,'CHECKS',self.items):
   result=core.run_checks(self.root,[i['id'] for i in self.items],seen.append,cancel or threading.Event(),probe)
  self.assertTrue(Path(result['report_file']).is_file());return result,seen
 def test_flat_values_and_no_screen_never_green(self):
  result,rows=self.run_check()
  self.assertEqual(core.load_values(self.root),{'enabled.test':True})
  self.assertEqual(rows[0]['settings'],'켜짐');self.assertTrue(rows[0]['contract_ok'])
  self.assertEqual(rows[0]['result'],'확인 필요');self.assertFalse(result['gameplay_execution_tested'])
 def test_existing_action_is_never_executed(self):
  self.items[0]['native']=[('unittest.mock','patch')]
  with patch('unittest.mock.patch',side_effect=AssertionError('must not execute')):
   result,rows=self.run_check()
  self.assertTrue(rows[0]['contract_ok'])
 def test_menu_alone_and_decision_are_distinct(self):
  _,rows=self.run_check(lambda *args:{'verified':True,'screen':'메뉴 확인','detail':'선택 단계 미확인'})
  self.assertEqual(rows[0]['result'],'확인 필요');self.assertTrue(rows[0]['screen_verified'])
  _,rows=self.run_check(lambda *args:{'verified':True,'decision_verified':True,'screen':'판독 확인','detail':'모의 입력 없음'})
  self.assertEqual(rows[0]['result'],'정상');self.assertFalse(rows[0]['end_to_end'])
 def test_disabled_album_and_cancel_never_probe(self):
  self.items[0]['disabled_by_user']=True
  _,rows=self.run_check(lambda *args:self.fail('disabled probe'))
  self.assertEqual(rows[0]['settings'],'사용 불가')
  self.items[0].pop('disabled_by_user');cancel=threading.Event();cancel.set()
  _,rows=self.run_check(lambda *args:self.fail('cancelled probe'),cancel)
  self.assertEqual(rows[0]['result'],'중지')
 def test_schedule_preview_does_not_rewrite_settings_or_receipts(self):
  (self.root/'settings/manager_identity.json').write_text(json.dumps({'server_name':'s','character_name':'c'}),encoding='utf-8')
  (self.root/'settings/owner-timetable.json').write_text(json.dumps({'version':1,'seed':'test','jobs':{}}),encoding='utf-8')
  (self.root/'settings/owner-timetable-state.json').write_text(json.dumps({'version':1,'characters':{'s / c':{}}}),encoding='utf-8')
  before={p:p.read_bytes() for p in (self.root/'settings').iterdir()}
  result=core.inspect_schedule(self.root,{'enabled.test':True})
  self.assertTrue(result['verified']);self.assertEqual(before,{p:p.read_bytes() for p in (self.root/'settings').iterdir()})
 def test_legacy_planner_without_readonly_has_private_config_and_no_commit(self):
  from types import SimpleNamespace
  from datetime import datetime
  class OldPlanner:
   def build(self,at):
    self.cfg=config(self.root)
    self.state['preview']={'status':'pending'}
    self.commit()
   def commit(self):raise AssertionError('old commit must not be used')
  (self.root/'settings/owner-timetable.json').write_text(json.dumps({'version':1,'seed':'test','jobs':{}}),encoding='utf-8')
  (self.root/'settings/owner-timetable-state.json').write_text(json.dumps({'version':1,'characters':{}}),encoding='utf-8')
  before={p:p.read_bytes() for p in (self.root/'settings').iterdir()}
  old=SimpleNamespace(Planner=OldPlanner,BY_KEY={},identity=lambda root:'test',now=datetime.now)
  with patch.dict(sys.modules,{'owner_timetable':old}):result=core.inspect_schedule(self.root,{})
  self.assertTrue(result['verified']);self.assertEqual(before,{p:p.read_bytes() for p in (self.root/'settings').iterdir()})

if __name__=='__main__':unittest.main()
