"""Saved-frame and fake-input regressions for the 2026-11-03 review; no game input."""
import bootstrap
import unittest,logging
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from datetime import timedelta
import numpy as np
from PIL import Image
from test_followup14 import Startup
import owner_timetable as t
import owner_special_contexts as special
import owner_startup_stage as stage

P=Path(__file__).parent/'live_fixtures'
def frame(name):return np.asarray(Image.open(P/name).convert('RGB')).copy()

def detector():
 from roi_runtime import RoiDetector
 return RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([stage.DUNGEON,stage.EXIT,stage.MENU,*special.NAMES])))

class DungeonDrop(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.d=detector()
 def test_actual_0126_item_banner_in_dungeon_is_not_a_treasure_receipt(self):
  f=frame('dungeon-item-drop-0126.png')
  self.assertTrue(self.d.find('체크_보물찾기_아이템획득',f,threshold=.95),'banner template must still match')
  self.assertIsNone(special.classify(self.d,f))
  self.assertEqual(stage.scene(self.d,f),'dungeon')
 def test_actual_treasure_receipt_outside_dungeon_is_kept(self):
  self.assertEqual(special.classify(self.d,frame('treasure-receipt-1101.png')),'treasure_receipt')
 def test_frame_after_the_banner_stays_dungeon(self):
  self.assertEqual(stage.scene(self.d,frame('dungeon-after-drop-0126.png')),'dungeon')
 def test_detector_without_dungeon_templates_keeps_old_result(self):
  # Every shipped detector now loads them through NAMES.
  self.assertIn(stage.DUNGEON,special.NAMES);self.assertIn(stage.EXIT,special.NAMES)

class Recheck(BaseException):pass

class SpecialContinuation(unittest.TestCase):
 def run_special(self,kind,scenes,hit=True):
  clock=[0.];clicks=[]
  context=S(checkpoint=lambda:None,wait=lambda n:clock.__setitem__(0,clock[0]+n))
  service=S(detector=S(templates={'체크_보물찾기_아이템획득'},find=lambda *a,**k:hit),capture=lambda:None,
            point=lambda n:clicks.append(n),button=lambda n,**k:clicks.append(n))
  adapter=S(project=S(root=Path('.'),code='DKB'),values={})
  seq=iter(scenes)
  with patch('project_adapter.main_quest.StateROIs',return_value=S(match=lambda *a:{})),patch('project_adapter.secret_exploration.ensure_auto_active'),patch.object(special.time,'monotonic',lambda:clock[0]):
   try:
    special.continue_special(S(_owner_stage_epoch=0),adapter,context,None,service,kind,Mock(),lambda d,f:next(seq),Recheck)
   except Recheck:return 'recheck',clicks
   except RuntimeError as exc:return str(exc),clicks
  return 'returned',clicks
 def test_receipt_closing_onto_a_dungeon_rechecks_instead_of_timing_out(self):
  result,clicks=self.run_special('treasure_receipt',['treasure_receipt','dungeon','dungeon'])
  self.assertEqual(result,'recheck');self.assertEqual(clicks,['포인트_공백_인벤토리'])
 def test_receipt_closing_onto_field_still_returns(self):
  result,_=self.run_special('treasure_receipt',['treasure_receipt','field','field','field'])
  self.assertEqual(result,'returned')
 def test_unfinished_receipt_screen_still_times_out(self):
  result,_=self.run_special('treasure_receipt',['treasure_receipt']*200)
  self.assertIn('시간 초과',result)

class ResumeDungeon(unittest.TestCase):
 def run_resume(self,scenes,timers):
  clock=[0.];published=[]
  context=S(checkpoint=lambda:None,wait=lambda n:clock.__setitem__(0,clock[0]+60))
  service=S(detector=S(find=lambda *a,**k:True),capture=lambda:None,check=lambda:None)
  adapter=S(project=S(root=Path('.'),code='DKB'),mode='sub_quest')
  seq=iter(scenes);values=iter(timers)
  with patch('project_adapter.main_quest.StateROIs',return_value=S(match=lambda *a:{})),patch.object(stage,'scene',lambda d,f:next(seq)),patch.object(stage,'timer_pair',lambda s:next(values)),patch.object(stage,'publish',lambda *a,**k:published.append(a)),patch.object(stage.time,'monotonic',lambda:clock[0]),patch('owner_dungeon_reentry.after_exit',return_value=None):
   return stage.resume_dungeon(S(),adapter,context,None,service)
 def test_later_timer_reading_extends_the_first_unread_limit(self):
  # First read failed, so the old fixed limit was one hour; 90 minutes remain.
  self.assertIsNone(self.run_resume(['dungeon']*70+['field']*3,[None,5400]+[5000-i for i in range(80)]))
 def test_unread_timer_does_not_end_a_known_five_hour_map(self):
  self.assertIsNone(self.run_resume(['dungeon']*310+['field']*3,[None]*312))
 def test_other_screen_logs_its_reason_and_rechecks(self):
  with self.assertLogs('project_gui.DKB',level='INFO') as logs:
   with self.assertRaises(stage.RecheckStage):self.run_resume(['boss_combat'],[None])
  self.assertTrue(any('boss_combat' in line for line in logs.output))

class WornDetail(unittest.TestCase):
 def port(self,frames):
  import owner_equipment_tooltip_candidate as tip
  port=tip.Port.__new__(tip.Port);clicks=[];seq=iter(frames)
  port._frame=lambda:(next(seq),0.);port.context=S(wait=lambda n:None,checkpoint=lambda:None)
  port.service=S(check=lambda:None,click_hit=clicks.append)
  return port,clicks
 def test_actual_2352_worn_detail_closes_by_its_own_x(self):
  worn,bag=frame('worn-detail-2352.png'),frame('inventory-open-2351.png')
  port,clicks=self.port([worn,worn,worn,bag,bag])
  self.assertEqual(port.close_unresolved_known(),'inventory_restored')
  self.assertEqual(clicks,[(510,106,(503,99,518,113))])
 def test_detail_that_stays_open_is_still_a_hold(self):
  import owner_equipment_tooltip_candidate as tip
  worn=frame('worn-detail-2352.png')
  port,_=self.port([worn]*5)
  with self.assertRaises(tip.Hold):port.close_unresolved_known()
 def test_changed_screen_before_click_sends_nothing(self):
  import owner_equipment_tooltip_candidate as tip
  worn,bag=frame('worn-detail-2352.png'),frame('inventory-open-2351.png')
  port,clicks=self.port([worn,worn,bag])
  with self.assertRaises(tip.Hold):port.close_unresolved_known()
  self.assertEqual(clicks,[])

class StartupOnce(Startup):
 def test_second_planner_keeps_the_first_receipt(self):
  row=self.row('daily_dungeon',last_outcome='sent_unconfirmed')
  self.p.startup_recheck(self.at);first=dict(row['startup_previous']);when=row['at']
  self.assertEqual(first['status'],'processed')
  self.p.startup_recheck(self.at+timedelta(seconds=3))
  self.assertEqual(row['startup_previous'],first);self.assertEqual(row['at'],when)

if __name__=='__main__':unittest.main()
