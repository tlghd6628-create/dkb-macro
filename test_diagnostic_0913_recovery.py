"""Saved native frames and simulated calls only; never controls the game."""
import unittest,time,contextlib,tempfile,json
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
import owner_quest_position_recovery as recovery
import owner_equipment_tooltip_candidate as gear
from owner_skill_goal import Pending

REASON='중앙 노란 장판 위 캐릭터 제자리 유효 관측 30초'
P=Path(__file__).parent/'diagnostic_review_0913'

class RecoveryTests(unittest.TestCase):
 def setup_case(self):
  self.calls=[];self.row={'mode':'sub_quest','group':True,'title':'동굴에서 들린 소리','deaths':1,'completed':False}
  self.book=S(item={'active':'q','quests':{'q':self.row}},commit=lambda:self.calls.append('persist'))
  self.ctx=S(checkpoint=lambda:None,input_depth=0,wait=lambda _:None)
  self.adapter=S(project=S(root=Path('unused')),run_town_return=lambda *a:self.calls.append('home'))
  self.ui=S(context=self.ctx,inputs=S(held=()),adapter=self.adapter,normal=lambda:True,normal_frame=lambda f:True,
   open=lambda mode:self.calls.append('open-current'),start_selected=lambda:self.calls.append('auto'))
  return self.ui,self.book
 def bindings(self,*,town=True,select=True):
  s=contextlib.ExitStack()
  s.enter_context(patch('owner_progression.state',return_value=S(character='char',power=104055)))
  s.enter_context(patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'))
  s.enter_context(patch.object(recovery,'paired',return_value=True))
  s.enter_context(patch('owner_town_return.town_pair',return_value=town))
  s.enter_context(patch('owner_story_groups.Groups',return_value=S(locate=lambda key:{'y':150,'open':False},select=lambda key:self.calls.append('same-q:'+key) or select)))
  return s
 def test_native_exact_stall_only(self):
  self.assertTrue(recovery.is_position_stall(REASON))
  self.assertFalse(recovery.is_position_stall('진행 중'))
  ui,b=self.setup_case();self.assertFalse(recovery.recover(ui,b,'q','완료'))
  self.assertEqual(self.calls,[])
 def test_native_general_stationary_stall_also_returns_home_without_yellow_ring(self):
  ui,b=self.setup_case()
  with self.bindings():self.assertTrue(recovery.recover(ui,b,'q','서사 진행 정체 180초'))
  self.assertEqual(self.calls,['persist','home','persist','persist','open-current','same-q:q','persist','auto','persist'])
  self.assertFalse(self.row['completed'])
 def test_same_quest_home_then_same_visible_root_no_catalog_scan(self):
  ui,b=self.setup_case()
  with self.bindings():self.assertTrue(recovery.recover(ui,b,'q',REASON))
  self.assertEqual(self.calls,['persist','home','persist','persist','open-current','same-q:q','persist','auto','persist'])
  self.assertEqual(b.item['active'],'q');self.assertFalse(self.row['completed']);self.assertEqual(self.row['deaths'],1)
  self.assertEqual(self.row['position_recovery']['phase'],'restarted_unverified')
 def test_intent_written_before_failed_home_and_no_second_attempt_after_restart(self):
  ui,b=self.setup_case()
  def home(*a):
   self.assertEqual(self.row['position_recovery']['phase'],'intent')
   raise Pending('home not verified')
  self.adapter.run_town_return=home
  with self.bindings():
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
   self.adapter.run_town_return=lambda *a:self.fail('repeat home')
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
  self.assertNotIn('auto',self.calls)
 def test_cooldown_waits_without_home(self):
  ui,b=self.setup_case();self.row['emote_attempt']={'at':time.time()-20}
  with self.bindings():self.assertEqual(recovery.recover(ui,b,'q',REASON),'waiting_emote')
  self.assertEqual(self.calls,[])
 def test_bad_home_proof_never_opens_mission(self):
  ui,b=self.setup_case()
  with self.bindings(town=False):
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
  self.assertEqual(self.calls,['persist','home'])
 def test_missing_current_root_never_chooses_other_quest(self):
  ui,b=self.setup_case()
  with self.bindings(select=False):
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
  self.assertNotIn('auto',self.calls)
 def test_busy_input_and_changed_identity_do_not_return_home(self):
  ui,b=self.setup_case();self.ctx.input_depth=1
  with self.bindings():
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
  self.assertEqual(self.calls,[])
 def test_stop_cancels_before_any_input(self):
  ui,b=self.setup_case()
  class Stop(BaseException):pass
  self.ctx.checkpoint=lambda:(_ for _ in ()).throw(Stop())
  with self.bindings():
   with self.assertRaises(Stop):recovery.recover(ui,b,'q',REASON)
  self.assertEqual(self.calls,[])
 def test_budget_shared_across_quests(self):
  ui,b=self.setup_case();b.item['position_recovery_events']=[time.time()-40,time.time()-10]
  with self.bindings():
   with self.assertRaises(Pending):recovery.recover(ui,b,'q',REASON)
  self.assertEqual(self.calls,[])

class InventoryTests(unittest.TestCase):
 def test_changing_inventory_holds_before_any_item_input_and_does_not_raise_session_error(self):
  import owner_equipment_upgrade_candidate as upgrade
  clock=[100.];ctx=S(checkpoint=lambda:None,wait=lambda n:clock.__setitem__(0,clock[0]+n))
  f=np.zeros((479,897,3),dtype='uint8')
  port=S(select_equipment_tab=lambda:None,_frame=lambda:(f.copy(),clock[0]),open_candidate=lambda *a:self.fail('unstable inventory must not select an item'))
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as temp:
   adapter=S(project=S(root=Path(temp)))
   with patch('owner_progression.state',return_value=S(character='char',observed=100.)),patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'),patch('project_adapter.town_services.TownServices',return_value=S(detector=S())),patch.object(gear,'Journal',return_value=S(read=lambda:{'pending':None})),patch('tools.ocr_support.get_paddle_engine',return_value=S(predict=lambda f:[])),patch.object(gear,'Port',return_value=port),patch.object(gear.time,'monotonic',side_effect=lambda:clock[0]),patch('owner_progression.inventory_parts',return_value=(True,True)),patch.object(gear,'same_equipment_inventory',return_value=False),patch.object(gear,'equipment_tab_selected',return_value=True):
    self.assertEqual(gear.run_in_open_inventory(adapter,ctx,S()),'preinput_inventory_unstable_skip')
   from owner_gear_hold_capture_candidate import _queue
   _queue.join()
  self.assertGreaterEqual(clock[0],102.)
 def test_actual_native_unknown_cell_is_preserved_not_reported_as_change(self):
  from roi_runtime import RoiDetector
  from project_adapter import market_inventory as n
  d=RoiDetector(bootstrap.A/'profiles/DKB',list(n.INVENTORY_USE_NAMES)+[n.EMPTY])
  f=np.asarray(Image.open(P/'20261102T091305-c17b8060.png').convert('RGB'))
  slots=gear.inventory_slots(d,f)
  self.assertEqual(sum(s=='unknown' for s,h in slots),1)
  self.assertTrue(gear.same_equipment_inventory(d,f,f.copy()))
  changed=f.copy();x,y,r,b=slots[0][1][2];changed[y:b,x:r]=0
  self.assertFalse(gear.same_equipment_inventory(d,f,changed))
 def test_unknown_cells_never_clicked_but_next_known_occupied_cell_is(self):
  from project_adapter import market_inventory as n
  f=np.zeros((479,897,3),dtype='uint8');calls=[]
  port=gear.Port.__new__(gear.Port)
  port.journal=S(read=lambda:{'candidate_catalog':{}})
  port.context=S(checkpoint=lambda:None,wait=lambda _:None)
  port.service=S(check=lambda:None,detector=S(),click_hit=lambda h:calls.append(h))
  port.identity_guard=lambda:True;port._frame=lambda:(f.copy(),time.monotonic())
  unknown=(10,10,(0,0,20,20));known=(40,10,(30,0,50,20))
  with patch('owner_progression.inventory_parts',return_value=(True,True)),patch.object(gear,'equipment_tab_selected',return_value=True),patch.object(gear,'inventory_slots',return_value=[('unknown',unknown),('occupied',known)]):
   self.assertEqual(port.open_candidate(),known)
  self.assertEqual(calls,[known]);self.assertTrue(port.unknown_cells_held)

if __name__=='__main__':unittest.main()

