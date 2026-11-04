"""Real11/02 before/after pixels, with fake service/input and identity scope.

These are reader/flow checks, not claims that the product performed the root's
manual game actions. Sky-derived references retain their strict thresholds.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import itertools,time,unittest
import numpy as np
from PIL import Image
import bootstrap
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native,growth_equipment_extra as extra
from owner_gear_awaken_reader_candidate import read_explicit_stage,read_success_overlay
from owner_gear_extra_runtime_candidate import ExtraObserver,ensure_enhance_tab
from owner_gear_step_guard_candidate import Guard


ROOT=bootstrap.T/'live_growth_20261102'
def frame(name):return np.asarray(Image.open(ROOT/(name+'.png')).convert('RGB')).copy()

class Context:
 def checkpoint(self):pass
 def wait(self,n):time.sleep(min(n,.002))

class Tests(unittest.TestCase):
 def setUp(self):
  self.context=Context()
  names=list(dict.fromkeys([*native.GROWTH_ENHANCE_NAMES,extra.AWAKE_TAB,extra.AWAKE_BUTTON,extra.BREAK_TAB,extra.BREAK_BUTTON,extra.BREAK_RANGE]))
  self.detector=RoiDetector(bootstrap.A/'profiles/DKB',names)
 def test_same_glove_zero_ready_and_maximum_result(self):
  for name in ('before','ready1','ready2'):
   self.assertEqual(read_explicit_stage(bootstrap.A,frame('gear_awaken_glove_'+name),'awaken')['current'],0)
  for name in ('after1','after2'):
   result=read_explicit_stage(bootstrap.A,frame('gear_awaken_glove_'+name),'awaken')
   self.assertEqual(result['current'],1);self.assertTrue(result['maximum'])
 def test_actual_breakthrough_two_to_three_and_success_stage(self):
  for suffix in ('1','2'):
   result=read_explicit_stage(bootstrap.A,frame('gear_break_weapon_2to3_before'+suffix),'breakthrough')
   self.assertEqual((result['current'],result['next']),(2,3))
   self.assertEqual(read_success_overlay(bootstrap.A,frame('gear_break_weapon_success'+suffix))['current'],3)
  result=read_explicit_stage(bootstrap.A,frame('gear_break_weapon_max1'),'breakthrough')
  self.assertEqual(result['current'],3);self.assertTrue(result['maximum'])
 def test_other_view_never_becomes_result_or_maximum(self):
  self.assertIsNone(read_success_overlay(bootstrap.A,frame('gear_awaken_glove_after1')))
  self.assertIsNone(read_success_overlay(bootstrap.A,frame('gear_break_weapon_2to3_before1')))
 def source(self,kind,images):
  first=images[0];rows=native.inspect_growth_equipment(self.detector,first)
  # Fake source/identity, explicit in test scope. No actual worn-item claim.
  source=NS(context=self.context,native=native,character='fake-display',sequence=0,last_levels=[12,12],last_frames=[first],
    ticket={'index':2,'grade':'일반','identity':'fake','captured_at':time.monotonic()},
    identity_reader=NS(pre=first,pre_rows=rows))
  seq=itertools.chain(images,itertools.repeat(images[-1]));service=NS(adapter=NS(project=NS(root=bootstrap.A)),detector=self.detector,
    capture=lambda:next(seq).copy(),check=lambda:None)
  source.service=service;observer=ExtraObserver(source,kind)
  return source,service,observer
 def test_ready_awaken_reader_proves_material_then_reads_maximum(self):
  before=[frame('gear_awaken_glove_ready1'),frame('gear_awaken_glove_ready2')]
  _,service,observer=self.source('awaken',before)
  with patch.object(observer,'_same_item',return_value=True),patch('owner_growth_current.observe'):
   pair=observer.read_pair();self.assertTrue(pair['screen_proof'],observer.last_reason)
   self.assertEqual(pair['first'].awakening,0);self.assertTrue(pair['first'].awaken_available)
   images=[frame('gear_awaken_glove_after1'),frame('gear_awaken_glove_after2')]
   seq=itertools.chain(images,itertools.repeat(images[-1]));service.capture=lambda:next(seq).copy()
   result=observer.read_result_pair();self.assertTrue(result['screen_proof'],observer.last_reason)
   self.assertEqual(result['first'].awakening,1);self.assertFalse(result['first'].awaken_available)
 def test_breakthrough_after_first_does_not_demand_enhancement_fifty(self):
  images=[frame('gear_break_weapon_2to3_before1'),frame('gear_break_weapon_2to3_before2')]
  source,service,observer=self.source('breakthrough',images)
  with patch.object(observer,'_same_item',return_value=True),patch('owner_growth_current.observe'):
   pair=observer.read_pair();self.assertTrue(pair['screen_proof'],observer.last_reason)
  self.assertEqual(pair['first'].breakthrough,2);self.assertIsNone(pair['first'].enhancement)
  guard=Guard(self.context,NS(),lambda:None)
  self.assertTrue(guard._eligible(pair['first'],pair['second'],{'enabled':True,'breakthrough':3},'breakthrough'))
 def test_success_overlay_reader_is_result_only(self):
  images=[frame('gear_break_weapon_success1'),frame('gear_break_weapon_success2')]
  _,_,observer=self.source('breakthrough',images)
  with patch.object(observer,'_overlay_same_item',return_value=True),patch('owner_growth_current.observe'):
   out=observer.read_result_pair();self.assertTrue(out['screen_proof'],observer.last_reason)
  self.assertEqual(out['first'].breakthrough,3);self.assertFalse(out['first'].breakthrough_available)
  self.assertFalse(observer.verify_final(images[-1],out,'breakthrough'))
 def test_material_selection_chooses_one_matching_unworn_card(self):
  before=frame('gear_awaken_glove_before');_,service,observer=self.source('awaken',[before])
  clicks=[];ready=frame('gear_awaken_glove_ready2')
  def click(hit):clicks.append(hit);service.capture=lambda:ready.copy()
  service.click_hit=click
  with patch.object(observer,'_same_item',return_value=True),patch('owner_growth_current.observe'):
   observer.prepare_material();pair=observer.read_pair()
  self.assertEqual(len(clicks),1);self.assertTrue(pair['screen_proof']);self.assertTrue(pair['first'].awaken_available)
  self.assertGreater(clicks[0][0],700) # list material card, never resource button
 def test_unknown_material_icon_is_not_selected(self):
  before=frame('gear_awaken_glove_before');_,service,observer=self.source('awaken',[before])
  changed=before.copy();row=observer.source.identity_reader.pre_rows[1];s=row['slot'];x=s['cell_x']+8;y=s['cell_y']+8
  changed[y:y+18,x:x+18]=0;service.capture=lambda:changed.copy();clicks=[];service.click_hit=clicks.append
  with patch.object(observer,'_same_item',return_value=True):observer.prepare_material()
  self.assertFalse(clicks)
 def test_only_verified_success_overlay_is_closed_once(self):
  images=[frame('gear_break_weapon_success1'),frame('gear_break_weapon_success2')]
  _,service,observer=self.source('breakthrough',images)
  clicks=[];normal=frame('gear_break_weapon_max1')
  def close(hit):clicks.append(hit);service.capture=lambda:normal.copy()
  service.click_hit=close
  with patch.object(observer,'_overlay_same_item',return_value=True),patch('owner_growth_current.observe'):
   self.assertTrue(observer.read_result_pair()['screen_proof']);observer.finish_result();observer.finish_result()
  self.assertEqual(len(clicks),1);self.assertEqual(clicks[0][0:2],(448,452))
 def test_known_extra_tab_normalizes_before_enhancement_list_recovery(self):
  before=frame('gear_break_weapon_max1');after=before.copy();after[67:87,14:73]=240;after[101:121,14:73]=20
  clicks=[];service=NS(adapter=NS(project=NS(root=bootstrap.A)),capture=lambda:before.copy(),check=lambda:None)
  def click(hit):clicks.append(hit);service.capture=lambda:after.copy()
  service.click_hit=click
  ensure_enhance_tab(service,self.context,identity_check=lambda:True)
  self.assertEqual(clicks,[(43,77,(14,67,73,87))])
 def test_unknown_menu_never_uses_growth_tab_coordinate(self):
  from owner_gear_native_observer_candidate import Hold
  clicks=[];service=NS(adapter=NS(project=NS(root=bootstrap.A)),capture=lambda:np.zeros((479,897,3),np.uint8),check=lambda:None,click_hit=clicks.append)
  with self.assertRaises(Hold):ensure_enhance_tab(service,self.context)
  self.assertFalse(clicks)


if __name__=='__main__':unittest.main()
