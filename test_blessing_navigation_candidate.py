import os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
from project_adapter import achievement_rewards as native
from owner_blessing_navigation_candidate import select_category,wait_pair

class Context:
 def checkpoint(self):pass
 def wait(self,n):time.sleep(.02)
class Service:
 def __init__(self,frames):self.frames=frames;self.actions=[];self.detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.BLESSING_NAMES))
 def check(self):pass
 def capture(self):return self.frames[1 if self.actions else 0].copy()
 def click_hit(self,hit):self.actions.append(hit)
class Tests(unittest.TestCase):
 def setUp(self):
  path=Path(__file__).parent/'live_fixtures';self.a=np.asarray(Image.open(path/'blessing_menu_native_1.png').convert('RGB'));self.b=np.asarray(Image.open(path/'blessing_slot1_native_1.png').convert('RGB'));self.s=Service((self.a,self.b));self.c=Context()
 def test_real_filter_pair_navigation_only(self):
  self.assertTrue(select_category(self.s,self.c,1,settings_check=lambda:True));self.assertEqual(len(self.s.actions),1)
 def test_actual_menu_after_transition_needs_two_consecutive_frames(self):
  names=('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파')
  detector=RoiDetector(bootstrap.A/'profiles/DKB',list(names))
  actual=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/blessing_fullmenu_transition_native.png').convert('RGB'))
  blank=np.zeros_like(actual)
  frames=iter([blank,actual,blank,actual,actual]);seen=[]
  def capture():
   frame=next(frames);seen.append(frame);return frame
  svc=SimpleNamespace(check=lambda:None,capture=capture)
  def menu(frame):return sum(bool(detector.find(n,frame,threshold=.95)) for n in names)>=2
  self.assertTrue(wait_pair(svc,self.c,menu));self.assertEqual(len(seen),5)
 def test_transition_timeout_does_not_produce_an_input(self):
  seen=[];svc=SimpleNamespace(check=lambda:None,capture=lambda:seen.append(1))
  self.assertFalse(wait_pair(svc,self.c,lambda frame:False,timeout=.03));self.assertGreaterEqual(len(seen),2)
 def test_transition_cancellation_propagates_before_capture(self):
  class Cancelled(BaseException):pass
  def cancel():raise Cancelled()
  def capture():raise AssertionError('capture after stop')
  with self.assertRaises(Cancelled):wait_pair(SimpleNamespace(check=lambda:None,capture=capture),SimpleNamespace(checkpoint=cancel),lambda frame:True)
 def test_wrong_after_filter_is_not_confirmed(self):
  self.s.frames=(self.a,self.a);self.assertFalse(select_category(self.s,self.c,1,settings_check=lambda:True));self.assertEqual(len(self.s.actions),1)
 def test_changed_settings_blocks_all_input(self):
  self.assertFalse(select_category(self.s,self.c,1,settings_check=lambda:False));self.assertFalse(self.s.actions)
 def test_unobserved_category_never_becomes_success(self):
  self.assertFalse(select_category(self.s,self.c,2,settings_check=lambda:True));self.assertEqual(len(self.s.actions),1)
 def test_caller_closes_only_verified_comparison(self):
  from unittest.mock import patch
  from owner_blessing_navigation_candidate import scan_one
  import owner_blessing_equip_candidate as equip
  path=Path(__file__).parent/'live_fixtures'
  compare=np.asarray(Image.open(path/'blessing_compare_rare_normal_native_1.png').convert('RGB')).copy()
  # This compare was taken on the full-list filter, so the filter detector is
  # mocked: only close-hit path and input bounds are under test here.
  self.s.frames=(compare,compare)
  with patch('owner_blessing_navigation_candidate.select_category',return_value=True),patch.object(equip,'scan_filtered',return_value='hold_policy'),patch.object(equip,'selected_filter',return_value=1),patch('owner_blessing_navigation_candidate.selected_filter',return_value=1),patch.object(equip,'_paired_rows',side_effect=[None,('confirmed',)]):
   result=scan_one(self.s,self.c,'test',1,[],settings_check=lambda:True)
  self.assertEqual(result,'hold_policy');self.assertEqual(len(self.s.actions),1);self.assertGreater(self.s.actions[0][0],580)
 def test_full_worker_menu_navigation_keeps_policy_and_restores_field(self):
  from unittest.mock import patch
  from owner_blessing_navigation_candidate import run_blessing_equipment
  from owner_gear_settings_candidate import Store
  from project_adapter import achievement_rewards as native
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   class Fake:
    def __init__(self):self.state='field';self.detector=self;self.actions=[]
    def check(self):pass
    def capture(self):return self.state
    def find(self,name,frame,threshold):
     if frame=='menu' and name in ('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파',native.BLESSING_ENTRY):return (1,1,(0,0,2,2))
     if frame=='blessing' and name in (native.BLESSING_CHECK,'버튼_나가기'):return (1,1,(0,0,2,2))
     return None
    def button(self,name,**kw):
     self.actions.append(name)
     self.state={'버튼_전체매뉴':'menu',native.BLESSING_ENTRY:'blessing','버튼_나가기':'field'}[name]
    def key(self,name):self.actions.append(name);self.state='field'
   svc=Fake();adapter=SimpleNamespace(project=SimpleNamespace(root=temp));seen=[]
   def scan(service,context,identity,category,order,**kwargs):seen.append(category);return 'hold_policy'
   with patch('owner_startup_stage.scene',side_effect=lambda detector,frame:'field' if frame=='field' else 'unknown'),patch('owner_blessing_navigation_candidate.select_category',return_value=True),patch('owner_blessing_equip_candidate._paired_rows',return_value=((),[],0)),patch('owner_blessing_navigation_candidate.scan_one',side_effect=scan):
    out=run_blessing_equipment(adapter,self.c,object(),'test',[],settings_check=lambda:True,service_factory=lambda *args:svc)
   self.assertEqual(seen,[1,2,3,4,5]);self.assertEqual(out['state'],'processed_unverified')
   self.assertEqual(svc.actions,['버튼_전체매뉴',native.BLESSING_ENTRY,'버튼_나가기']);self.assertEqual(svc.state,'field')
 def test_pending_candidate_category_has_priority(self):
  from unittest.mock import patch
  from owner_blessing_navigation_candidate import run_blessing_equipment
  from owner_blessing_equip_candidate import _intent_path,_save
  from project_adapter import achievement_rewards as native
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   _save(_intent_path(temp,'test'),{'version':1,'pending':{'phase':'sent','candidate':{'slot':3}}})
   class Fake:
    def __init__(self):self.state='field';self.detector=self
    def check(self):pass
    def capture(self):return self.state
    def find(self,name,frame,threshold):
     if frame=='menu' and name in ('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파',native.BLESSING_ENTRY):return (1,1,(0,0,2,2))
     if frame=='blessing' and name in (native.BLESSING_CHECK,'버튼_나가기'):return (1,1,(0,0,2,2))
    def button(self,name,**kw):self.state={'버튼_전체매뉴':'menu',native.BLESSING_ENTRY:'blessing','버튼_나가기':'field'}[name]
   svc=Fake();adapter=SimpleNamespace(project=SimpleNamespace(root=temp));seen=[]
   def scan(service,context,identity,category,order,**kwargs):seen.append(category);return 'hold_result_unknown'
   with patch('owner_startup_stage.scene',side_effect=lambda detector,frame:'field' if frame=='field' else 'unknown'),patch('owner_blessing_navigation_candidate.select_category',return_value=True),patch('owner_blessing_equip_candidate._paired_rows',return_value=((),[],0)),patch('owner_blessing_navigation_candidate.scan_one',side_effect=scan):
    out=run_blessing_equipment(adapter,self.c,object(),'test',[],settings_check=lambda:True,service_factory=lambda *args:svc)
   self.assertEqual(seen,[3]);self.assertEqual(out['categories'],{'3':'hold_result_unknown'});self.assertEqual(svc.state,'field')
 def test_each_visible_candidate_is_examined_before_next_slot(self):
  from unittest.mock import patch
  from owner_blessing_navigation_candidate import run_blessing_equipment
  from project_adapter import achievement_rewards as native
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   class Fake:
    def __init__(self):self.state='field';self.detector=self
    def check(self):pass
    def capture(self):return self.state
    def find(self,name,frame,threshold):
     if frame=='menu' and name in ('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파',native.BLESSING_ENTRY):return (1,1,(0,0,2,2))
     if frame=='blessing' and name in (native.BLESSING_CHECK,'버튼_나가기'):return (1,1,(0,0,2,2))
    def button(self,name,**kw):self.state={'버튼_전체매뉴':'menu',native.BLESSING_ENTRY:'blessing','버튼_나가기':'field'}[name]
   svc=Fake();adapter=SimpleNamespace(project=SimpleNamespace(root=temp));seen=[]
   def scan(service,context,identity,category,order,**kwargs):seen.append(category);return 'hold_policy'
   rows=[{'equipped':False,'equipped_state':'미장착','grade':'흰'} for _ in range(3)]
   with patch('owner_startup_stage.scene',side_effect=lambda detector,frame:'field' if frame=='field' else 'unknown'),patch('owner_blessing_navigation_candidate.select_category',return_value=True),patch('owner_blessing_equip_candidate._paired_rows',return_value=((),rows,0)),patch('owner_blessing_navigation_candidate.scan_one',side_effect=scan):
    run_blessing_equipment(adapter,self.c,object(),'test',[],settings_check=lambda:True,service_factory=lambda *args:svc)
   self.assertEqual(seen,[1]*3+[2]*3+[3]*3+[4]*3+[5]*3)
 def test_unknown_detail_never_sends_menu_close(self):
  from unittest.mock import patch
  from owner_blessing_navigation_candidate import run_blessing_equipment
  from owner_blessing_equip_candidate import BlessingNavigationError
  from project_adapter import achievement_rewards as native
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   class Fake:
    def __init__(self):self.state='field';self.detector=self;self.actions=[]
    def check(self):pass
    def capture(self):return self.state
    def find(self,name,frame,threshold):
     if frame=='menu' and name in ('버튼_전체매뉴_성장','버튼_전체매뉴_임무','버튼_전체매뉴_문파',native.BLESSING_ENTRY):return (1,1,(0,0,2,2))
     if frame=='blessing' and name in (native.BLESSING_CHECK,'버튼_나가기'):return (1,1,(0,0,2,2))
    def button(self,name,**kw):self.actions.append(name);self.state={'버튼_전체매뉴':'menu',native.BLESSING_ENTRY:'blessing','버튼_나가기':'field'}[name]
   svc=Fake();adapter=SimpleNamespace(project=SimpleNamespace(root=temp))
   with patch('owner_startup_stage.scene',side_effect=lambda detector,frame:'field' if frame=='field' else 'unknown'),patch('owner_blessing_navigation_candidate.select_category',return_value=True),patch('owner_blessing_equip_candidate._paired_rows',return_value=((),[],0)),patch('owner_blessing_navigation_candidate.scan_one',side_effect=BlessingNavigationError('popup')):
    with self.assertRaises(BlessingNavigationError):run_blessing_equipment(adapter,self.c,object(),'test',[],settings_check=lambda:True,service_factory=lambda *args:svc)
   self.assertEqual(svc.actions,['버튼_전체매뉴',native.BLESSING_ENTRY]);self.assertEqual(svc.state,'blessing')
if __name__=='__main__':unittest.main()
