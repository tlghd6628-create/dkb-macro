"""Navigation allowlist checks only; never constructs a real input backend."""
import sys,unittest,threading
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from owner_feature_check_live_candidate import MenuProbe,NAV,factory

class Cases(unittest.TestCase):
 def setUp(self):
  self.events=[];self.cancel=threading.Event();self.probe=MenuProbe(NS(),NS(),self.cancel)
  self.probe.context=NS(checkpoint=lambda:None,wait=lambda n:None)
  self.probe.service=NS(check=lambda:None,capture=lambda:None,detector=NS(find=lambda *a,**k:(2,3,(1,1,4,5))),
      click_hit=self.events.append,key=lambda vk:self.events.append(vk))
 def test_actions_and_enter_are_not_available_to_probe(self):
  for name in ('버튼_성장_장비_강화버튼','버튼_성장_장비_돌파실행','버튼_성장_장비_각성실행','버튼_비경_입장','버튼_구매','버튼_업적_받기'):
   with self.assertRaises(RuntimeError):self.probe.button(name)
  for key in (0x0d,0x42,0x20):
   with self.assertRaises(RuntimeError):self.probe.key(key)
  self.assertFalse(self.events)
 def test_approved_navigation_uses_existing_service_only(self):
  self.probe.button('버튼_성장_장비_돌파');self.probe.key(0x4a)
  self.assertEqual(self.events,[(2,3,(1,1,4,5)),0x4a])
  self.assertEqual(self.probe.navigation,[{'kind':'menu','name':'버튼_성장_장비_돌파'},{'kind':'menu_key','name':'J'}])
  self.assertFalse(any('실행' in name or '입장' in name or '구매' in name or '받기' in name for name in NAV))
 def test_unimplemented_feature_does_not_initialize_input(self):
  self.probe._init=lambda:self.fail('must not create inputs')
  result=self.probe({'id':'falling','name':'낙화'},self.cancel)
  self.assertFalse(result['verified']);self.assertFalse(self.events)
 def test_no_game_connection_still_allows_basic_checks_without_input(self):
  def gate():raise RuntimeError('게임 연결 필요')
  gui=NS(session=NS(snapshot=lambda:{'worker_alive':False,'status':'stopped'}),execution_gate=gate,
   make_adapter=lambda:self.fail('unready adapter'))
  probe=factory(gui,self.cancel);result=probe({'id':'gear'},self.cancel)
  self.assertFalse(result['verified']);self.assertEqual(result['detail'],'게임 연결 필요')
 def test_menu_transition_gets_bounded_rechecks_without_reclicking(self):
  results=iter([False,False,True]);waits=[]
  self.probe.pair=lambda predicate:next(results)
  self.probe.context=NS(wait=waits.append)
  self.assertTrue(self.probe.wait_pair(lambda frame:True))
  self.assertEqual(waits,[.08,.08]);self.assertFalse(self.events)

if __name__=='__main__':unittest.main()
