import bootstrap
import unittest,time,threading
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image

class SharedReaders(unittest.TestCase):
 def test_actual_energy_menu_uses_original_native_variant(self):
  from roi_runtime import RoiDetector
  from owner_feature_check_live_candidate import MenuProbe,CHECKS
  from project_adapter import achievement_rewards as native
  frame=np.asarray(Image.open(bootstrap.T/'checker_fixtures/energy-menu-20261102.png').convert('RGB'))
  detector=RoiDetector(bootstrap.A/'profiles/DKB',[native.ENERGY_ENTRY,native.ENERGY_ENTRY2])
  self.assertIsNone(detector.find(native.ENERGY_ENTRY,frame,threshold=.95))
  self.assertIsNotNone(detector.find(native.ENERGY_ENTRY2,frame,threshold=.95))
  calls=[];probe=MenuProbe(None,None,threading.Event());probe.context=NS(checkpoint=lambda:None,wait=lambda n:None)
  probe.service=NS(check=lambda:None,capture=lambda:frame,detector=detector,click_hit=calls.append)
  probe.button(native.ENERGY_ENTRY)
  self.assertEqual(calls,[detector.find(native.ENERGY_ENTRY2,frame,threshold=.95)]);self.assertEqual(CHECKS['energy'],(native.ENERGY_CHECK,))
 def test_transparent_all_menu_is_not_the_field_behind_it(self):
  from owner_feature_check_live_candidate import MenuProbe
  from roi_runtime import RoiDetector
  frame=np.asarray(Image.open(bootstrap.T/'checker_fixtures/energy-menu-20261102.png').convert('RGB'))
  names=['버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파']
  probe=MenuProbe(None,None,threading.Event());probe.service=NS(detector=RoiDetector(bootstrap.A/'profiles/DKB',names))
  self.assertFalse(probe.field(frame))
 def test_equipment_uses_final_reader_not_the_truncated_seed(self):
  from owner_feature_check_growth_candidate import read_enhancement
  from project_adapter import market_inventory as native
  frame=np.zeros((479,897,3),dtype=np.uint8)
  row={'index':1,'grade':'파랑','equipped':True,'equipped_state':'장착'}
  class Reader:
   def __init__(self,*args):self.last_frames=[frame];self.ticket=None;self.last_reason='ok'
   def capture(self):return 1,time.monotonic(),frame.copy()
   def items(self,frame):return [row]
   def identity_reader(self,*args):return 'identity'
   def prepare_and_select(self,index):self.ticket={'index':1,'identity':'identity','grade':'희귀','row':row};return self.ticket
   def read_result_pair(self):self.last_levels=[41,41];return {'screen_proof':True,'second':NS(enhancement=41)}
   # Readiness is the same read_pair the Guard uses before a real input.
   def read_pair(self,require_resource=True):return {'screen_proof':True,'active_pair_verified':True}
  from owner_native_contracts import region_names
  detector=NS(find=lambda *a,**kw:True,entries={name:{} for name in region_names('gear')})
  service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=object())
  ctx=NS(wait=lambda s:time.sleep(.02))
  with patch('roi_runtime.RoiDetector',return_value=detector),patch('owner_gear_native_observer_candidate.Observer',Reader),patch.object(native,'_growth_selected_slot',side_effect=[None,1,1]),patch.object(native,'read_growth_equipment_detail',side_effect=AssertionError('must not use truncated seed reader')),patch.object(native,'inspect_growth_materials',return_value={'status':'재료 충분'}),patch('owner_gear_resource_candidate.NativeResources',return_value=lambda f:{'verified':True,'active':True}):
   result=read_enhancement(service,ctx)
  self.assertTrue(result['verified'],result);self.assertEqual(result['enhancement'],41);self.assertTrue(result['native_ready'])
 def test_slow_style_ocr_reuses_existing_fresh_glyph_verifier(self):
  from owner_feature_check_growth_candidate import read_styles
  frame=np.zeros((479,897,3),dtype=np.uint8);ticks=[time.monotonic()-10,time.monotonic()-9.88]
  row={'text':'파멸+19','score':.99,'bounds':(710,70,750,90)}
  ui=NS(frame=lambda:frame,rows_batch=lambda specs:None,_owner_last_rows_raw=([frame,frame],ticks,[[[row],[row]]]),_owner_last_rows_pair=([frame,frame],ticks,[[row]]))
  with patch('owner_skill_ui.SkillUI',return_value=ui),patch('owner_skill_growth_candidate.tab',return_value=True),patch('owner_skill_growth_candidate._same_pixels',return_value=True),patch('owner_skill_growth_candidate.refresh_evidence') as refresh:
   result=read_styles(NS(adapter=None),NS(checkpoint=lambda:None),None)
  self.assertTrue(result['verified']);refresh.assert_called_once()

if __name__=='__main__':unittest.main()
