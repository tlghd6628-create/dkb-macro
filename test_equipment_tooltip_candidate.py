import bootstrap
from bootstrap import R,O,A,B,RT,T
C=T
import tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_equipment_tooltip_candidate as r
from owner_equipment_upgrade_candidate import Hold

class Engine:
 def __init__(self,rows):self.rows=iter(rows)
 def predict(self,_):
  text=next(self.rows)
  return [{'rec_texts':text.split('|'),'rec_scores':[.99]*len(text.split('|'))}]
def engine_comparisons(n=1):return Engine(['희귀','일반','부채','부채','장착|해제','장착']*n)
def engine_details(n=1):return Engine(['희귀','부채','장착|해제']*n)

class TooltipTests(unittest.TestCase):
 def setUp(self):
  self.compare=[np.asarray(Image.open(C/'live_fixtures'/f'gear_compare_worn_rare_candidate_normal_native_{i}.png').convert('RGB')) for i in (1,2)]
  self.worn=[np.asarray(Image.open(C/'live_fixtures'/f'gear_rare_fan_worn_detail_native_{i}.png').convert('RGB')) for i in (1,2)]
 def test_actual_frames_rare_to_normal_read_and_hold(self):
  result=[r.compare_frame(f,engine_comparisons()) for f in self.compare]
  self.assertEqual(result[0],result[1]);self.assertEqual((result[0]['current_grade'],result[0]['candidate_grade']),('희귀','일반'))
  from owner_equipment_upgrade_candidate import paired
  a,b=[dict(row,verified=True,character='fake',frame_id=str(i),captured_at=99.6+i*.1) for i,row in enumerate(result)]
  with self.assertRaises(Hold):paired(a,b,clock=lambda:100)
 def test_actual_worn_single_detail_matches_same_item_not_other(self):
  comparison=r.compare_frame(self.compare[0],engine_comparisons())
  for frame in self.worn:
   row=r.worn_detail_frame(frame,engine_details())
   self.assertTrue(r.same_item(row['item'],comparison['current_item']))
   self.assertFalse(r.same_item(row['item'],comparison['candidate_item']))
 def test_grade_text_is_authority_not_badge_background_colour(self):
  # Change the grade panel background, preserving the separately proved E.
  f=self.compare[0].copy();f[138:151,311:340]=[120,10,120]
  row=r.compare_frame(f,engine_comparisons())
  self.assertEqual((row['current_grade'],row['candidate_grade']),('희귀','일반'))
  row=r.compare_frame(self.compare[0],Engine(['일반','희귀','부채','부채','장착|해제','장착']))
  self.assertEqual((row['current_grade'],row['candidate_grade']),('일반','희귀'))
  with self.assertRaises(Hold):r.compare_frame(self.compare[0],Engine(['미확인','희귀','부채','부채','장착|해제','장착']))
  with self.assertRaises(Hold):r.compare_frame(self.compare[0],Engine(['희귀','일반','장갑','부채','장착|해제','장착']))
 def test_final_grade_text_must_match_prior_pair(self):
  proof={'current_grade':'일반','candidate_grade':'희귀'}
  self.assertTrue(r.grade_text_matches(proof,self.compare[0],Engine(['일반','희귀'])))
  self.assertFalse(r.grade_text_matches(proof,self.compare[0],Engine(['희귀','일반'])))
  self.assertFalse(r.grade_text_matches(proof,self.compare[0],Engine(['미확인','희귀'])))
 def test_close_navigation_ignores_glow_but_rejects_changed_close_or_button(self):
  a=self.compare[0];b=a.copy();b[120:122,380:382]=255
  self.assertFalse(r._same_anchors(a,b))
  self.assertTrue(r.same_comparison_for_close(a,b))
  changed=b.copy();changed[99:112,580:596]=0
  self.assertFalse(r.same_comparison_for_close(a,changed))
  changed=b.copy();changed[350:377,526:599]=0
  self.assertFalse(r.same_comparison_for_close(a,changed))
 def test_synthetic_same_canonical_part_maps_and_mismatch_holds(self):
  # Actual screenshots only show 부채; other displayed labels are synthetic.
  for label in ('반지','팔찌','갑옷','다리','귀걸이','목걸이','신발','장갑','투구','허리띠'):
   with self.subTest(label=label):
    result=r.compare_frame(self.compare[0],Engine(['희귀','일반',label,label,'장착|해제','장착']))
    self.assertEqual(result['slot'],label)
  with self.assertRaises(Hold):r.compare_frame(self.compare[0],Engine(['희귀','일반','정체불명','정체불명','장착|해제','장착']))
 def test_actual_reverse_never_sends_an_input(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  inputs=[];frames=iter([f.copy() for f in self.compare]);ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:next(frames),click_hit=lambda hit:inputs.append(hit))
  port=r.Port(service,ctx,'fake-character',engine_comparisons(2),lambda:True)
  with self.assertRaises(Hold):port.try_comparison()
  self.assertEqual(inputs,[]);self.assertFalse(port.journal.path.exists())
 def test_native_candidate_open_uses_three_matching_frames_no_equip_input(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  frame=np.asarray(Image.open(C/'live_fixtures'/'inventory_equip_tab_native_1.png').convert('RGB'))
  hits=[];ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  detector=NS(find=lambda *a,**k:(725,110,(713,98,738,123)))
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:frame.copy(),detector=detector,click_hit=lambda hit:hits.append(hit))
  port=r.Port(service,ctx,'fake-character',Engine(['일반','희귀']),lambda:True)
  with patch.object(r,'inventory_slots',return_value=[('occupied',(725,110,(713,98,738,123)))]):
   self.assertEqual(port.open_candidate(),(725,110,(713,98,738,123)))
  self.assertEqual(hits,[(725,110,(713,98,738,123))])
  hits.clear();sequence=iter([(725,110,(713,98,738,123)),(735,110,(723,98,748,123))])
  with patch.object(r,'inventory_slots',side_effect=lambda *a:[('occupied',next(sequence))]),self.assertRaises(Hold):port.open_candidate()
  self.assertEqual(hits,[])
 def test_actual_gear_tab_twenty_one_occupied_and_nineteen_blank(self):
  from project_adapter import market_inventory
  from roi_runtime import RoiDetector
  d=RoiDetector(A/'profiles/DKB',['범위_인벤토리',market_inventory.EMPTY])
  for number in (1,2):
   f=np.asarray(Image.open(C/'live_fixtures'/f'inventory_equip_tab_native_{number}.png').convert('RGB'))
   self.assertTrue(r.equipment_tab_selected(f))
   cells=r.inventory_slots(d,f)
   self.assertEqual([s for s,_ in cells],['occupied']*21+['empty']*19)
  a=np.asarray(Image.open(C/'live_fixtures'/'inventory_equip_tab_native_1.png').convert('RGB'))
  b=np.asarray(Image.open(C/'live_fixtures'/'inventory_equip_tab_native_2.png').convert('RGB'))
  self.assertTrue(r.same_equipment_inventory(d,a,b))
  changed=b.copy();changed[95:120,713:738]=0
  self.assertFalse(r.same_equipment_inventory(d,a,changed))
  old=np.asarray(Image.open(C/'live_fixtures'/'inventory_worn_native_1.png').convert('RGB'))
  self.assertFalse(r.equipment_tab_selected(old))
 def test_unread_grade_known_compare_closes_without_equipping(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);f=self.compare[0]
  inv=np.asarray(Image.open(C/'live_fixtures'/'inventory_equip_tab_native_1.png').convert('RGB'))
  frames=iter([f.copy(),f.copy(),f.copy(),inv.copy(),inv.copy()]);hits=[]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:next(frames),click_hit=hits.append)
  port=r.Port(service,ctx,'fake-character',Engine(['장착|해제','장착']*2),lambda:True)
  self.assertEqual(port.close_unresolved_known(),'inventory_restored')
  self.assertEqual(hits,[(588,106,(581,99,595,113))])
 def test_native_marker_filter_does_not_repeat_first_item(self):
  from project_adapter import market_inventory
  from roi_runtime import RoiDetector
  d=RoiDetector(A/'profiles/DKB',[market_inventory.EQUIP_READY,'범위_인벤토리'])
  needle=d.templates[market_inventory.EQUIP_READY][:,:,::-1]
  f=np.zeros((479,897,3),np.uint8);h,w=needle.shape[:2]
  f[120:120+h,730:730+w]=needle;f[180:180+h,770:770+w]=needle
  first=r.ready_hit(d,f,());self.assertIsNotNone(first)
  second=r.ready_hit(d,f,(first[2],));self.assertIsNotNone(second)
  self.assertNotEqual(first[2],second[2]);self.assertIsNone(r.ready_hit(d,f,(first[2],second[2])))
 def test_grid_uses_normal_inventory_coordinates_without_green_marker(self):
  from project_adapter import market_inventory
  from roi_runtime import RoiDetector
  d=RoiDetector(A/'profiles/DKB',['범위_인벤토리',market_inventory.EMPTY])
  f=np.asarray(Image.open(C/'live_fixtures/inventory_worn_native_1.png').convert('RGB'))
  slots=r.inventory_slots(d,f)
  self.assertEqual([hit[:2] for _,hit in slots[:4]],[(728,108),(766,108),(804,108),(842,108)])
  self.assertTrue(all(state=='occupied' for state,_ in slots[:20]))
  # Native empty artwork placed in a cell is a negative synthetic control.
  fake=f.copy();needle=d.templates[market_inventory.EMPTY][:,:,::-1];fake[94:123,713:742]=needle
  self.assertEqual(r.inventory_slots(d,fake)[0][0],'empty')
 def test_only_known_right_close_and_two_inventory_frames(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  inv=[np.asarray(Image.open(C/'live_fixtures'/f'inventory_worn_native_{i}.png').convert('RGB')) for i in (1,2)]
  frames=iter([self.compare[0].copy(),inv[0].copy(),inv[1].copy()]);hits=[]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:next(frames),click_hit=lambda hit:hits.append(hit))
  port=r.Port(service,ctx,'fake-character',None,lambda:True);port.last=(self.compare[0],time.monotonic(),{})
  self.assertEqual(port.close_comparison(),'inventory_restored')
  self.assertEqual(hits,[(588,106,(581,99,595,113))])
 def test_synthetic_positive_port_issues_one_guarded_fake_click(self):
  # No positive game image exists: policy and input wiring test only.
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);f=self.compare[0]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:time.sleep(.025));hits=[]
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:f.copy(),click_hit=lambda hit:hits.append(hit))
  def fake_pair(a,b,engine,character,ticks,**kwargs):
   values=dict(slot='무기',current_grade='일반',candidate_grade='희귀',current_item='old',candidate_item='new',target_bounds=[527,351,598,376],verified=True,character=character)
   return tuple(dict(values,captured_at=t,frame_id=str(i)) for i,t in enumerate(ticks))
  port=r.Port(service,ctx,'fake-character',Engine(['일반','희귀']),lambda:True)
  with patch.object(r,'compare_pair',side_effect=fake_pair),patch.object(r,'comparison_item_proof',return_value=True):self.assertEqual(port.try_comparison(),'pending_confirmation')
  self.assertEqual(hits,[(562,363,(527,351,598,376))]);self.assertEqual(port.journal.read()['pending']['phase'],'sent')
 def test_identity_change_in_final_proof_sends_no_input(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);f=self.compare[0];hits=[];calls=[]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:time.sleep(.025))
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:f.copy(),click_hit=lambda hit:hits.append(hit))
  def guard():calls.append(1);return len(calls)<3
  def fake_pair(a,b,engine,character,ticks,**kwargs):
   v=dict(slot='무기',current_grade='일반',candidate_grade='희귀',current_item='old',candidate_item='new',target_bounds=[527,351,598,376],verified=True,character=character)
   return tuple(dict(v,captured_at=t,frame_id=str(i)) for i,t in enumerate(ticks))
  port=r.Port(service,ctx,'fake-character',None,guard)
  with patch.object(r,'compare_pair',side_effect=fake_pair),patch.object(r,'comparison_item_proof',return_value=True),self.assertRaises(Hold):port.try_comparison()
  self.assertEqual(hits,[]);self.assertIsNone(port.journal.read()['pending'])
 def test_synthetic_single_candidate_only_when_both_inventory_frames_prove_blank(self):
  import owner_equipment_boxes
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);f=self.compare[0];hits=[]
  ctx=NS(checkpoint=lambda:None,wait=lambda _:time.sleep(.025))
  service=NS(adapter=NS(project=NS(root=Path(tmp.name))),check=lambda:None,capture=lambda:f.copy(),click_hit=lambda hit:hits.append(hit))
  port=r.Port(service,ctx,'fake-character',Engine(['일반']),lambda:True);port.before_inventory=(f.copy(),f.copy())
  single=dict(slot='반지',candidate_grade='일반',candidate_item='synthetic-item',target_bounds=[449,351,519,376])
  with patch.object(r,'comparison_shell',return_value=False),patch.object(r,'compare_pair',side_effect=Hold('single')),patch.object(r,'initial_candidate_frame',return_value=single),patch.object(r,'same_item',return_value=True),patch.object(r,'single_item_proof',return_value=True),patch.object(owner_equipment_boxes,'agree',return_value={'반지':False}):
   self.assertEqual(port.try_comparison(),'pending_confirmation')
  self.assertEqual(hits,[(484,363,(449,351,519,376))])
  other=r.Port(service,ctx,'other-character',None,lambda:True);other.before_inventory=(f.copy(),f.copy());hits.clear()
  with patch.object(r,'compare_pair',side_effect=Hold('single')),patch.object(r,'initial_candidate_frame',return_value=single),patch.object(owner_equipment_boxes,'agree',return_value={'반지':None}),self.assertRaises(Hold):other.try_comparison()
  self.assertEqual(hits,[])
 def test_fake_candidate_scan_skips_already_checked_until_no_more_visible(self):
  from owner_progression import state
  from project_adapter import town_services
  from tools import ocr_support
  import owner_progression,owner_hunt_rules_candidate
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  inv=np.asarray(Image.open(C/'live_fixtures/inventory_worn_native_1.png').convert('RGB'))
  seen=[];ctx=NS(checkpoint=lambda:None,wait=lambda _:time.sleep(.003));adapter=NS(project=NS(root=Path(tmp.name)))
  progress=NS(character='fingerprint',observed=time.monotonic())
  class FakePort:
   def __init__(self,service,context,character,engine,guard):self.journal=NS(read=lambda:{'pending':None});self.last=True
   def select_equipment_tab(self):return 'already_selected'
   def _frame(self):return inv.copy(),time.monotonic()
   def open_candidate(self,excluded):
    seen.append(tuple(excluded))
    if len(excluded)==0:return (1,1,(1,1,2,2))
    if len(excluded)==1:return (3,3,(3,3,4,4))
    return None
   def try_comparison(self):raise Hold('not eligible')
   def close_comparison(self):return 'inventory_restored'
  service=NS(check=lambda:None,detector=None)
  with patch.object(owner_progression,'state',return_value=progress),patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='profile'),patch.object(town_services,'TownServices',return_value=service),patch.object(ocr_support,'get_paddle_engine',return_value=NS(predict=lambda _:[])),patch.object(r,'Port',FakePort),patch.object(r,'same_equipment_inventory',return_value=True):
   self.assertEqual(r.run_in_open_inventory(adapter,ctx,None),'no_more_visible_candidates')
  self.assertEqual(seen,[(),((1,1,2,2),),((1,1,2,2),(3,3,4,4))])

if __name__=='__main__':unittest.main(verbosity=2)
