import bootstrap
import unittest,tempfile,json,threading,time
import numpy as np
from types import SimpleNamespace as NS
from pathlib import Path
from unittest.mock import patch
import owner_feature_check_gear_candidate as gear
from owner_feature_check_status_candidate import status

class GearDecisions(unittest.TestCase):
 def run_case(self,reading,goal):
  with patch('owner_feature_check_growth_candidate.read_enhancement',return_value=reading),patch.object(gear,'goals',return_value={'grades':{'희귀':goal}}):
   return gear.diagnose(None,None,None,'configured-v1:test')
 def test_native_colour_matches_the_actual_grade_goal(self):
  self.assertEqual(gear.goal_for({'grades':{'희귀':{'enhance':49}}},'파랑'),{'enhance':49})
 def test_only_paired_native_ready_gives_ready(self):
  row=self.run_case({'verified':True,'grade':'파랑','enhancement':32,'native_ready':True},{'enabled':True,'enhance':49})
  self.assertEqual(row['finding'],'ready');self.assertNotEqual(status(dict(row,result='확인 필요')),'정상')
 def test_unknown_materials_are_not_shortage(self):
  row=self.run_case({'verified':True,'grade':'파랑','enhancement':32,'native_ready':False,'materials':None},{'enabled':True,'enhance':49})
  self.assertEqual(row['finding'],'materials_unreadable')
 def test_explicit_material_shortage(self):
  row=self.run_case({'verified':True,'grade':'파랑','enhancement':32,'materials':'재료 부족'},{'enabled':True,'enhance':49})
  self.assertEqual(row['finding'],'materials_short')
 def test_goal_reached_does_not_need_materials(self):
  row=self.run_case({'verified':True,'grade':'파랑','enhancement':49},{'enabled':True,'enhance':49})
  self.assertEqual(row['finding'],'goal_reached')
 def test_off_goal_is_not_read_failure(self):
  row=self.run_case({'verified':True,'grade':'파랑','enhancement':10},{'enabled':False,'enhance':49})
  self.assertEqual(row['finding'],'goal_off')

class Sweep(unittest.TestCase):
 def test_later_wiring_failure_keeps_the_exact_missing_file(self):
  import owner_feature_checks_candidate as checks
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'profiles/DKB/templates').mkdir(parents=True);(root/'settings').mkdir()
   (root/'settings/auto-settings.json').write_text(json.dumps({'values':{'a.on':True,'b.on':True}}),encoding='utf-8')
   catalog=[{'id':'a','name':'A','settings':['a.on']},{'id':'b','name':'B','settings':['b.on'],'templates':['missing.png']}]
   with patch('owner_feature_check_catalog_candidate.CHECKS',catalog):
    report=checks.run_checks(root,['a','b'],lambda row:None,threading.Event(),probe=lambda *a:{'verified':False,'stop_navigation':True,'stage':'menu','finding':'menu_unrecognized'})
   self.assertIn('missing.png',report['rows'][1]['detail'])
   self.assertEqual(report['rows'][1]['stage'],'contract')

class ReadOnlyFacades(unittest.TestCase):
 def test_blessing_selects_only_the_proven_item_and_restores_service(self):
  from owner_feature_check_growth_candidate import read_blessing
  from project_adapter import market_inventory as native
  frame=np.zeros((479,897,3),dtype=np.uint8);events=[];original=object()
  row={'index':1,'slot':{'cell_x':700,'cell_y':100,'cell_w':40,'cell_h':40}}
  context=NS(checkpoint=lambda:None,wait=lambda seconds:time.sleep(.02))
  service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=original,capture=lambda:frame.copy(),
             check=lambda:None,click_hit=events.append,growth_selected_index=99)
  class Observer:
   def __init__(self,*args):self.last_state={'slot':2,'level':38,'active':True}
   def read_pair(self,require_resource,*,publish):
    self_test.assertFalse(require_resource);self_test.assertFalse(publish);return {'screen_proof':True}
  self_test=self
  from owner_native_contracts import region_names
  detector=NS(entries={name:{} for name in region_names('blessing')})
  with patch('roi_runtime.RoiDetector',return_value=detector),patch('owner_blessing_native_candidate.worn_candidates',return_value=[row]),patch('owner_blessing_native_candidate.BlessingObserver',Observer),patch.object(native,'_click_xy',return_value=(720,120)),patch.object(native,'inspect_growth_equipment',return_value=[row]):
   result=read_blessing(service,context,'configured-v1:test')
  self.assertTrue(result['verified'],result);self.assertEqual(result['level'],38);self.assertEqual(len(events),1)
  self.assertEqual(events[0],(720,120,(700,100,740,140)))
  self.assertIs(service.detector,original);self.assertEqual(service.growth_selected_index,99)
  self.assertFalse(hasattr(service,'growth_selection_confirmed'))
 def test_blessing_unknown_worn_list_never_selects(self):
  from owner_feature_check_growth_candidate import read_blessing
  service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=object(),capture=lambda:np.zeros((479,897,3),dtype=np.uint8),check=lambda:None,click_hit=lambda hit:self.fail('no click'))
  from owner_native_contracts import region_names
  detector=NS(entries={name:{} for name in region_names('blessing')})
  with patch('roi_runtime.RoiDetector',return_value=detector),patch('owner_blessing_native_candidate.worn_candidates',return_value=[]):
   result=read_blessing(service,NS(checkpoint=lambda:None,wait=lambda s:None),'configured-v1:test')
  self.assertFalse(result['verified'])
 def test_styles_use_paired_visible_ocr_without_selection(self):
  from owner_feature_check_growth_candidate import read_styles
  frame=np.zeros((479,897,3),dtype=np.uint8);ticks=[time.monotonic(),time.monotonic()]
  row={'text':'파멸+19','score':.99,'bounds':(710,70,750,90)}
  ui=NS(frame=lambda:frame,rows_batch=lambda specs:None,_owner_last_rows_raw=([frame,frame],ticks,[[[row],[row]]]),_owner_last_rows_pair=([frame,frame],ticks,[[row]]))
  with patch('owner_skill_ui.SkillUI',return_value=ui),patch('owner_skill_growth_candidate.tab',return_value=True),patch('owner_skill_growth_candidate._same_pixels',return_value=True):
   result=read_styles(NS(adapter=None),NS(checkpoint=lambda:None),None)
  self.assertTrue(result['verified']);self.assertEqual(result['levels']['파멸'],19)

if __name__=='__main__':unittest.main()
