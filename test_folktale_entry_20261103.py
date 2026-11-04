"""Nested folktale entry and the loading wait. Fake inputs and one saved screen; never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import threading,unittest
from types import SimpleNamespace as S
from unittest.mock import MagicMock,Mock,patch
import numpy as np
from PIL import Image
from biol_base.session import Context,Cancelled
import owner_schedule_priority as p
import owner_town_wait as w
from owner_timetable import LOCAL as table

FIXTURE=Path(__file__).resolve().parent/'fixtures_town_wait/loading_20261103.png'

def adapter(**values):return S(values=values,project=S(root=bootstrap.T/'test_scratch/no-test-reservations',app_id='DKB',code='DKB'),mode='sub_quest')
def context():return Context(threading.Event(),threading.Event())

class Nested(unittest.TestCase):
 def setUp(self):
  table.native_job='weekly_dungeon';self.addCleanup(setattr,table,'native_job',None)
 def test_the_exploration_step_inside_the_folktale_entry_really_runs(self):
  inner=Mock(return_value='entered');wrapped=p.service_wrapper(inner,'비경탐험')
  def native(a,c,i,**kw):return wrapped(a,c,i)
  a=adapter()
  self.assertEqual(p.service_wrapper(native,'전래동화 비경')(a,context(),Mock(),kind='5h'),'entered')
  inner.assert_called_once()
  self.assertIsNone(getattr(p.LOCAL,'combat',None))
 def test_the_real_native_entry_calls_that_step(self):
  import project_adapter.secret_folktale as ft,project_adapter.secret_exploration as ex
  inner=Mock(return_value=True)
  a=MagicMock();a.values={'auto_challenge.secret_folktale_5h.enabled':True,'auto_challenge.secret_folktale_5h.target':'원님 고개'};a.project=adapter().project
  with patch.object(ex,'run_secret_exploration',p.service_wrapper(inner,'비경탐험')):
   p.service_wrapper(ft.run_folktale_exploration,'전래동화 비경')(a,context(),Mock(),kind='5h')
  inner.assert_called_once()
 def test_other_starts_stay_held_during_a_dungeon(self):
  inner=Mock()
  with p.activity_scope('전래동화 비경'):self.assertTrue(p.service_wrapper(inner,'잡화상점 구매')(adapter(),context(),Mock()))
  inner.assert_not_called()
 def test_a_dungeon_stays_held_during_other_combat(self):
  inner=Mock()
  with p.activity_scope('낙화의 전장'):self.assertTrue(p.service_wrapper(inner,'비경탐험')(adapter(),context(),Mock()))
  inner.assert_not_called()

class Clock:
 def __init__(self):self.now=0.
 def __call__(self):return self.now

class Loading(unittest.TestCase):
 def setUp(self):
  self.clock=Clock();patcher=patch('owner_town_wait.time.monotonic',self.clock);patcher.start();self.addCleanup(patcher.stop)
  self.field=np.full((479,897,3),90,dtype='uint8');self.black=np.array(Image.open(FIXTURE).convert('RGB'))
 def service(self,frames):
  frames=iter(frames);inputs=[]
  def wait(seconds):self.clock.now+=seconds
  return S(context=S(wait=wait,checkpoint=Mock()),check=Mock(),capture=lambda:next(frames),key=inputs.append,click_hit=inputs.append),inputs
 def native(self,*outcomes):
  outcomes=list(outcomes)
  def original(service,stage=None):
   self.clock.now+=40;value=outcomes.pop(0)
   if isinstance(value,Exception):raise value
   return value
  return original
 TIMEOUT=RuntimeError('전체메뉴 복귀 확인 시간초과')
 def test_the_actual_saved_failure_screen_counts_as_loading(self):
  self.assertTrue(w.loading_frame(self.black));self.assertFalse(w.loading_frame(self.field))
 def test_a_lit_screen_is_not_loading(self):
  frame=self.black.copy();frame[200:220,400:420]=200
  self.assertFalse(w.loading_frame(frame))
 def test_normal_return_is_untouched(self):
  service,_=self.service([])
  self.assertEqual(w.wrap(self.native('ok'))(service,'stage'),'ok');self.assertEqual(self.clock.now,40)
 def test_loading_keeps_waiting_then_uses_the_native_check_again(self):
  service,inputs=self.service([self.black,self.black,self.black,self.field])
  self.assertEqual(w.wrap(self.native(self.TIMEOUT,'ok'))(service),'ok')
  self.assertEqual(inputs,[]);self.assertEqual(self.clock.now,40+3+40)
 def test_gives_up_at_two_minutes_of_loading(self):
  service,inputs=self.service([self.black]*200)
  with self.assertRaisesRegex(RuntimeError,'시간초과'):w.wrap(self.native(self.TIMEOUT))(service)
  self.assertEqual(self.clock.now,120);self.assertEqual(inputs,[])
 def test_any_other_screen_fails_as_before(self):
  service,_=self.service([self.field])
  with self.assertRaisesRegex(RuntimeError,'시간초과'):w.wrap(self.native(self.TIMEOUT))(service)
  self.assertEqual(self.clock.now,40)
 def test_other_errors_are_not_caught(self):
  service,_=self.service([])
  with self.assertRaisesRegex(RuntimeError,'다른 오류'):w.wrap(self.native(RuntimeError('다른 오류')))(service)
 def test_stop_during_loading_ends_at_once(self):
  service,_=self.service([self.black]*5)
  service.context.checkpoint=Mock(side_effect=[None,Cancelled()])
  with self.assertRaises(Cancelled):w.wrap(self.native(self.TIMEOUT))(service)
 def test_install_wraps_once(self):
  from project_adapter.town_services import TownServices
  original=TownServices.wait_menu;self.addCleanup(setattr,TownServices,'wait_menu',original)
  w.install();first=TownServices.wait_menu;w.install()
  self.assertIs(TownServices.wait_menu,first);self.assertTrue(first._owner_town_wait)

if __name__=='__main__':unittest.main()
