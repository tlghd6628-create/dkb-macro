import bootstrap
import unittest,threading,tempfile,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

class Repairs(unittest.TestCase):
 def test_extra_reader_never_selects_materials_or_publishes_values(self):
  from owner_feature_check_growth_candidate import read_extra
  service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=object())
  context=object();source=NS(service=service,context=context);service._owner_checker_gear=source
  class Observer:
   last_reason='unknown'
   def __init__(self,source,kind):pass
   def prepare_material(self):raise AssertionError('no material selection')
   def read_pair(self,resources=True,*,publish=True):
    test.assertFalse(resources);test.assertFalse(publish)
    return {'screen_proof':True,'second':NS(grade='희귀',breakthrough=3,awakening=None),'maximum_reached':True}
  test=self
  with patch('owner_gear_extra_runtime_candidate.ExtraObserver',Observer):
   result=read_extra(service,context,'breakthrough')
  self.assertEqual(result['current'],3);self.assertTrue(result['maximum'])
 def test_break_unlock_requires_a_fresh_read_zero_stage(self):
  from owner_feature_check_growth_candidate import read_extra
  for proof,stage,expected in ((True,0,True),(True,1,False),(False,0,False)):
   service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=object());context=object()
   service._owner_checker_gear=NS(service=service,context=context,last_levels=[41,41])
   calls=[]
   class Observer:
    last_reason='unread'
    def __init__(self,*args):pass
    def read_pair(self,resources=True,*,publish=True):
     calls.append(resources);test.assertFalse(publish)
     return {'screen_proof':proof,'second':NS(grade='희귀',breakthrough=stage),'active_pair_verified':True}
   test=self
   with patch('owner_gear_extra_runtime_candidate.ExtraObserver',Observer),patch('owner_feature_check_growth_candidate.empty_extra_list',return_value=False):
    result=read_extra(service,context,'breakthrough')
   self.assertEqual(result.get('needs_enhancement',False),expected)
   self.assertEqual(calls,[False,True] if proof and stage else [False])
   self.assertEqual(result['verified'],proof)
 def test_equipment_reader_loads_the_whole_native_contract(self):
  from owner_feature_check_growth_candidate import read_enhancement
  from owner_gear_native_observer_candidate import Hold
  from project_adapter import market_inventory as native
  from roi_runtime import RoiDetector
  service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=object())
  with patch('roi_runtime.RoiDetector',wraps=RoiDetector) as loader,patch('owner_gear_native_observer_candidate.Observer',side_effect=Hold('test boundary')):
   result=read_enhancement(service,None)
  self.assertFalse(result['verified']);names=set(loader.call_args.args[1])
  self.assertTrue(set(native.GROWTH_ENHANCE_NAMES)<=names)
  self.assertIn('범위_성장_장비탭_레벨',names)
 def test_blessing_resets_known_gear_subtab_before_changing_category(self):
  from owner_feature_check_live_candidate import MenuProbe
  events=[];probe=MenuProbe(NS(),NS(project=NS(root=bootstrap.A)),threading.Event())
  probe.normalized=True;probe.known='gear_awaken';probe._init=lambda:None
  probe.context=NS(checkpoint=lambda:None);probe.service=NS(adapter=probe.adapter)
  probe.pair=lambda f:True;probe.frame=lambda:None;probe.evidence=lambda *a,**kw:None
  probe.button=lambda name:events.append(name);probe.ensure_enhance=lambda:events.append('normalize')
  with patch('owner_feature_check_growth_candidate.read_blessing',return_value={'verified':False,'detail':'no equipped item'}),patch('owner_hunt_rules_candidate.configured_identity',return_value='configured-v1:test'):
   row=probe({'id':'blessing_growth'},probe.cancel)
  self.assertEqual(events,['normalize','버튼_성장_가호탭'])
  self.assertEqual(row['finding'],'values_unreadable');self.assertNotIn('stop_navigation',row)
 def test_off_and_disabled_are_preserved_after_an_earlier_menu_failure(self):
  import owner_feature_checks_candidate as checks
  catalog=[{'id':'a','name':'A'}, {'id':'off','name':'OFF','settings':['off.enabled']},
           {'id':'disabled','name':'DISABLED','disabled_by_user':True}]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'profiles/DKB/templates').mkdir(parents=True);(root/'settings').mkdir()
   (root/'settings/auto-settings.json').write_text(json.dumps({'values':{'off.enabled':False}}),encoding='utf-8')
   with patch('owner_feature_check_catalog_candidate.CHECKS',catalog):
    report=checks.run_checks(root,['a','off','disabled'],lambda r:None,threading.Event(),probe=lambda *a:{'verified':False,'stop_navigation':True,'stage':'menu','finding':'menu_unrecognized'})
   self.assertEqual(report['rows'][1]['assessment']['outcome'],'excluded')
   self.assertEqual(report['rows'][2]['assessment']['outcome'],'excluded')

if __name__=='__main__':unittest.main()
