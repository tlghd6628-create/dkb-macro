"""Treasure TEST row and region gate: saved frame + fakes. Never a game test.

Run from the candidate folder with the scratchpad copies on sys.path first:
  python -c "import sys,runpy;sys.path.insert(0,'<scratchpad>/treasure');sys.path.insert(1,'.');sys.argv=['t'];runpy.run_path('<scratchpad>/treasure/test_treasure_test_20261105.py',run_name='__main__')"
"""
import sys,logging,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock
HERE=Path(__file__).resolve().parent
CAND=Path('C:/Users/홍이/Downloads/MANAGER_RELEASE_v0.11.6/MANAGER_RELEASE_v0.11.6/dkb_candidate_20261101')
if str(CAND) not in sys.path:sys.path.insert(0,str(CAND))
import bootstrap
# bootstrap puts the candidate folder first; the proposed copies must shadow it.
sys.path.insert(0,str(HERE))
for stale in ('owner_challenge_test','owner_treasure','owner_timetable','test_challenge_test_20261104'):sys.modules.pop(stale,None)
import numpy as np
from PIL import Image
import owner_challenge_test as c
import owner_treasure as gate
import test_challenge_test_20261104 as base
from project_adapter import treasure_entry as te
from project_adapter._entry import Adapter as Native

KEY='auto_challenge.treasure_hunt.enabled';REGION='auto_challenge.treasure_hunt.region'
FRAME=CAND/'image_scope_20261104/live/e08_treasure.png'  # real 11-04 post-patch menu frame
def frame(p):return np.asarray(Image.open(p).convert('RGB')).copy()

class Gate(unittest.TestCase):
 def test_power_rule_opens_all_three_power_routes_together(self):
  self.assertEqual(gate.allowed_points(None),['포인트_보물찾기_타바로1'])
  self.assertEqual(gate.allowed_points(127574),['포인트_보물찾기_타바로1'])
  self.assertEqual(gate.allowed_points(150236,recent_death=True),['포인트_보물찾기_타바로1'])
  self.assertEqual(gate.allowed_points(150236),['포인트_보물찾기_타바로1','포인트_보물찾기_타바로2','포인트_보물찾기_타바로3','포인트_보물찾기_타바로4'])
  self.assertEqual(set(gate.allowed_points(150236)),set(te.REGIONS['타바로지방'][2]))

class NativeRegionGate(unittest.TestCase):
 """The Adapter method itself refuses the two unmapped regions before any input."""
 def call(self,region):
  log=[];handler=logging.Handler();handler.emit=lambda r:log.append(r.getMessage())
  logger=logging.getLogger('project_gui.DKB');level=logger.level;logger.setLevel(logging.INFO);logger.addHandler(handler)
  self.addCleanup(logger.setLevel,level)
  class Fake:
   values={KEY:True,REGION:region};mode='auto_mode';project=S(app_id='DKB',code='DKB',root=bootstrap.A)
   log=logging.getLogger('project_gui.DKB')
   def __getattr__(self,n):raise AssertionError('native touched '+n+' for '+region)
  try:return Native.run_treasure_region_entry(Fake(),Mock(),Mock()),log
  finally:logging.getLogger('project_gui.DKB').removeHandler(handler)
 def test_gamori_and_suari_are_disabled_without_input(self):
  for region in ('가모리지방','수아리지방'):
   with self.subTest(region=region):
    result,log=self.call(region)
    self.assertEqual(result,{'status':'DISABLED','summary':'보물찾기 해당 지방 준비 중'})
    self.assertIn('보물찾기 %s 준비 중 · 실행 생략'%region,log)
 def test_empty_region_is_selection_required(self):
  result,log=self.call('');self.assertEqual(result,'SELECTION_REQUIRED');self.assertIn('보물찾기 지방 선택 필요',log)
 def test_only_tavaro_is_enabled_natively(self):
  self.assertEqual(te.ENABLED_REGIONS,frozenset({'타바로지방'}))

class Row(base.Dispatch):
 """Reuses the existing dispatcher harness: the real native _run_auto_features with fakes."""
 def test_treasure_row_is_its_own_kind_and_reaches_the_native_entry(self):
  self.assertEqual(c.TARGETS[KEY],('보물찾기',c.TREASURE))
  self.assertNotIn(KEY,{k for k,v in c.TARGETS.items() if v[1]==c.DISPATCH})
  from unittest.mock import patch
  for mode in ('sub_quest','auto_mode'):
   with patch('owner_quest_preflight.read_power',return_value=True) as power:
    saved={KEY:False,REGION:'타바로지방','auto_rewards.mail.enabled':True}
    order=[];adapter=base.real(saved,mode,order);ran=[]
    c.execute(adapter,base.context(ran),Mock(),KEY)
    self.assertEqual(order,['run_treasure_region_entry']);power.assert_called_once()
    self.assertNotIn('common.run_town_return',ran);self.assertIs(saved[KEY],False);self.assertEqual(adapter.mode,mode)
 def test_region_must_be_saved_before_the_test(self):
  saved={KEY:False,REGION:'','auto_rewards.mail.enabled':True};adapter=base.real(saved,'sub_quest',[])
  with self.assertRaisesRegex(RuntimeError,'지방 선택 필요'):c.execute(adapter,base.context(),Mock(),KEY)
 def test_region_value_survives_the_switch_mask(self):
  shown=c.only({KEY:False,REGION:'수아리지방','auto_rewards.mail.enabled':True},KEY)
  self.assertEqual(shown[REGION],'수아리지방');self.assertIs(shown[KEY],True);self.assertIs(shown['auto_rewards.mail.enabled'],False)

class PostPatchFrame(unittest.TestCase):
 """Real 2026-11-04 menu frame: what the native entry can still see after the patch."""
 @classmethod
 def setUpClass(cls):
  from roi_runtime import RoiDetector
  import project_adapter.treasure_tavaro as tt
  cls.d=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([*te.NAMES,*tt.NAMES])));cls.f=frame(FRAME)
 def hit(self,name,th=.95):return self.d.find(name,self.f,threshold=th)
 def test_menu_identity_and_region_tabs(self):
  for name in ('체크_보물찾기','버튼_보물찾기_타바로지방열림','버튼_보물찾기_가모리지방','버튼_보물찾기_보상모두받기','버튼_나가기'):
   with self.subTest(name=name):self.assertIsNotNone(self.hit(name))
 def test_tavaro_castle_shows_the_native_done_badge(self):
  # 12/12 on this frame: the native completion marker for point 1 is matched, so the castle is skipped.
  self.assertIsNotNone(self.hit('체크_보물찾기_타바로1_완료'))
  for name in ('체크_보물찾기_타바로2','체크_보물찾기_타바로3','체크_보물찾기_타바로4'):
   with self.subTest(name=name):self.assertIsNotNone(self.hit(name))
 def test_suari_tab_moved_below_its_roi(self):
  # Drifted ~26px (image_scope eval: elsewhere 0,+26). The native click still found it at y=223.
  self.assertIsNone(self.hit('버튼_보물찾기_수아리지방'))
 def test_future_completion_badges_are_not_registered(self):
  from roi_runtime import RoiDetector
  for name in ('체크_보물찾기_타바로2_완료','체크_보물찾기_타바로3_완료','체크_보물찾기_타바로4_완료'):
   with self.subTest(name=name),self.assertRaises(KeyError):RoiDetector(bootstrap.A/'profiles/DKB',[name])

if __name__=='__main__':unittest.main(verbosity=2)
