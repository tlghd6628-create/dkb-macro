"""Fake input/worker regressions for multi-item replacement and exact result.

None of these checks clicks the running game or represents live acceptance.
"""
import tempfile,time,json,base64,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from PIL import Image
import bootstrap
import owner_equipment_tooltip_candidate as target
from owner_equipment_upgrade_candidate import Journal,Hold


class Tests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.ctx=NS(checkpoint=lambda:None,wait=lambda n:time.sleep(.001))
 def port(self):
  f=np.zeros((479,897,3),np.uint8)
  service=NS(adapter=NS(project=NS(root=self.root)),check=lambda:None,capture=lambda:f.copy(),click_hit=lambda _:self.fail('unexpected input'))
  port=target.Port(service,self.ctx,'profile|character',None,lambda:True)
  proof={'character':port.character,'slot':'장갑','current_item':'old-normal','current_grade':'일반','candidate_item':'rare-A','candidate_grade':'희귀',
         'target_bounds':[527,351,598,376],'frame_ids':['old1','old2'],'captured_at':time.monotonic()-10}
  port.journal.prepare(proof);port.journal.mark_sent();return port,proof
 def test_wrong_rare_item_never_confirms_or_clears_sent_receipt(self):
  port,_=self.port();wrong={'slot':'장갑','grade':'희귀','item':'different-rare'}
  with patch.object(target,'worn_detail_frame',return_value=wrong),patch.object(target,'same_item',side_effect=lambda a,b:a==b):
   with self.assertRaisesRegex(Hold,'실제 선택 후보'):port.confirm_worn_detail()
  self.assertEqual(port.journal.read()['pending']['phase'],'sent')
 def test_exact_selected_item_confirms_and_requests_followup_growth(self):
  port,proof=self.port();actual={'slot':'장갑','grade':'희귀','item':'rare-A'}
  now=time.monotonic();ticks=iter(now-.1+i*.01 for i in range(4))
  port._frame=lambda:(np.zeros((479,897,3),np.uint8),next(ticks))
  with patch.object(target,'worn_detail_frame',return_value=actual),patch.object(target,'same_item',side_effect=lambda a,b:a==b),patch.object(target,'single_item_proof',return_value=True),patch.object(target,'_same_single_anchors',return_value=True),patch('owner_growth_current.invalidate_item') as invalidate:
   self.assertEqual(port.confirm_worn_detail(),'confirmed')
  record=port.journal.read();self.assertIsNone(record['pending']);self.assertEqual(record['completed'][0]['verified_as'],'same_item')
  self.assertIsNotNone(port.journal.growth_request());invalidate.assert_called_once_with(self.root,'profile','old-normal',grade='일반')
 def run_fake_inventory(self,FakePort,*,stable=True):
  from project_adapter import town_services
  from tools import ocr_support
  import owner_progression,owner_hunt_rules_candidate
  adapter=NS(project=NS(root=self.root));service=NS(check=lambda:None,detector=None)
  progress=NS(character='character',observed=time.monotonic())
  with patch.object(owner_progression,'state',return_value=progress),patch.object(owner_hunt_rules_candidate,'configured_identity',return_value='profile'),patch.object(town_services,'TownServices',return_value=service),patch.object(ocr_support,'get_paddle_engine',return_value=NS(predict=lambda _:[])),patch.object(target,'Port',FakePort),patch.object(target,'same_equipment_inventory',side_effect=stable if callable(stable) else lambda *a:stable),patch.object(target,'equipment_tab_selected',return_value=True):
   return target.run_in_open_inventory(adapter,self.ctx,None)
 def fake_base(self):
  f=np.asarray(Image.open(bootstrap.T/'live_fixtures/inventory_equip_tab_native_1.png').convert('RGB')).copy()
  class FakePort:
   def __init__(self,*a):self.journal=NS(read=lambda:{'pending':None});self.last=True
   def _frame(self):return f.copy(),time.monotonic()
   def select_equipment_tab(self):pass
   def close_comparison(self):pass
   def close_worn_detail(self):pass
   def scroll_page(self):return False
  return FakePort
 def test_three_upgrades_continue_on_fresh_inventory_in_one_visit(self):
  calls=[];Base=self.fake_base()
  class Fake(Base):
   def __init__(self,*a):super().__init__(*a);self.count=0
   def open_candidate(self,excluded):
    calls.append(('open',self.count,tuple(excluded)))
    return (710,100,(709,89,738,118)) if self.count<3 else None
   def try_comparison(self):return 'pending_confirmation'
   def confirm_worn_detail(self):self.count+=1;calls.append(('confirm',self.count));return 'confirmed'
  self.assertEqual(self.run_fake_inventory(Fake),'confirmed')
  self.assertEqual([v[1] for v in calls if v[0]=='confirm'],[1,2,3])
  self.assertTrue(all(not v[2] for v in calls if v[0]=='open'))
 def test_page_scroll_does_not_reuse_previous_page_exclusions(self):
  calls=[];Base=self.fake_base()
  class Fake(Base):
   def __init__(self,*a):super().__init__(*a);self.page=0
   def open_candidate(self,excluded):
    calls.append((self.page,tuple(excluded)))
    return (710,100,(709,89,738,118)) if self.page==1 and not excluded else None
   def try_comparison(self):raise Hold('not eligible')
   def scroll_page(self):self.page+=1;return self.page==1
  self.assertEqual(self.run_fake_inventory(Fake),'no_more_visible_candidates')
  self.assertEqual(calls[0],(0,()));self.assertEqual(calls[1],(1,()))
 def test_inventory_reordering_discards_stale_row_exclusions(self):
  calls=[];Base=self.fake_base()
  class Fake(Base):
   def __init__(self,*a):super().__init__(*a);self.count=0
   def open_candidate(self,excluded):
    calls.append(tuple(excluded));self.count+=1
    return (710,100,(709,89,738,118)) if self.count<=2 else None
   def try_comparison(self):raise Hold('not eligible')
  state=[True,False,True]
  def stable(*a):return state.pop(0) if state else True
  self.assertEqual(self.run_fake_inventory(Fake,stable=stable),'no_more_visible_candidates')
  self.assertEqual(calls[:2],[(),()])
 def token(self,mask,icon):
  return json.dumps({'title_shape':list(mask.shape),'title_mask':base64.b64encode(mask.astype(np.uint8).tobytes()).decode('ascii'),
                     'icon_rgb':base64.b64encode(icon.tobytes()).decode('ascii')})
 def test_moving_name_core_requires_the_same_icon_and_substantial_text(self):
  random=np.random.default_rng(18);mask=random.integers(0,2,(10,100),dtype=np.uint8);icon=random.integers(0,255,(20,20,3),dtype=np.uint8)
  a=self.token(mask[:,:70],icon);b=self.token(mask[:,15:85],icon)
  self.assertTrue(target.same_item(a,b))
  self.assertFalse(target.same_item(a,self.token(mask[:,15:85],255-icon)))
  self.assertFalse(target.same_item(a,self.token(mask[:,:12],icon)))
 def remember(self,port):
  random=np.random.default_rng(31);mask=random.integers(0,2,(10,40),dtype=np.uint8);icon=random.integers(0,255,(20,20,3),dtype=np.uint8)
  item=self.token(mask,icon);now=time.monotonic()
  common={'verified':True,'identity_core_verified':True,'character':port.character,'slot':'장갑',
          'current_grade':'일반','current_item':item,'candidate_grade':'희귀','candidate_item':item}
  a=dict(common,frame_id='memory1',captured_at=now-.1);b=dict(common,frame_id='memory2',captured_at=now-.05)
  self.assertTrue(port.journal.remember_pair(a,b));return icon
 def test_part_hints_persist_but_another_character_cannot_reuse_them(self):
  port,_=self.port();self.remember(port)
  # Cache writes do not clear a resource/equip sent intent.
  self.assertEqual(port.journal.read()['pending']['phase'],'sent')
  self.assertEqual(Journal(self.root,port.character).read()['observed_slots']['장갑']['grade'],'일반')
  self.assertNotIn('candidate_catalog',Journal(self.root,'profile|other-character').read())
 def test_cached_part_is_skipped_only_after_fresh_worn_grade_proof(self):
  from owner_equipment_boxes import SLOTS
  import owner_equipment_boxes,roi_runtime
  from project_adapter import market_inventory
  port,_=self.port();self.remember(port);dummy=np.zeros((479,897,3),np.uint8)
  detector=NS(entries={'체크_인벤토리_갑옷':{}})
  with patch.object(owner_equipment_boxes,'agree',return_value={'장갑':True}),patch.object(roi_runtime,'RoiDetector',return_value=detector),patch.object(market_inventory,'inspect_equipment_grades',return_value={'갑옷':{'grade':'일반'}}):
   self.assertEqual(port.cached_non_general_parts(dummy,dummy.copy()),set())
  with patch.object(owner_equipment_boxes,'agree',return_value={'장갑':True}),patch.object(roi_runtime,'RoiDetector',return_value=detector),patch.object(market_inventory,'inspect_equipment_grades',return_value={'갑옷':{'grade':'희귀 이상'}}):
   self.assertEqual(port.cached_non_general_parts(dummy,dummy.copy()),{'장갑'})
 def test_new_drop_icon_does_not_inherit_a_cached_part(self):
  port,_=self.port();icon=self.remember(port);port._candidate_catalog=port.journal.read()['candidate_catalog']
  f=np.zeros((479,897,3),np.uint8);hit=(728,108,(709,89,738,118));f[97:115,717:735]=icon[1:19,1:19]
  self.assertEqual(port.known_candidate_part(f,hit),'장갑')
  f[97:115,717:735]=255-icon[1:19,1:19]
  self.assertIsNone(port.known_candidate_part(f,hit))
 def test_blinking_green_hint_does_not_change_the_already_chosen_row(self):
  from owner_progression import inventory_parts
  import owner_progression
  f=np.zeros((479,897,3),np.uint8);hits=[]
  service=NS(adapter=NS(project=NS(root=self.root)),detector=NS(entries={'x':1}),capture=lambda:f.copy(),check=lambda:None,click_hit=hits.append)
  port=target.Port(service,self.ctx,'profile|character',None,lambda:True)
  one=(728,108,(709,89,738,118));two=(766,108,(747,89,776,118))
  with patch.object(owner_progression,'inventory_parts',return_value=(True,True)),patch.object(target,'equipment_tab_selected',return_value=True),patch.object(target,'inventory_slots',return_value=[('occupied',one),('occupied',two)]),patch.object(port,'cached_non_general_parts',return_value=set()),patch.object(target,'ready_hit',return_value=(766,101,(761,96,771,106))):
   self.assertEqual(port.open_candidate(),two)
  self.assertEqual(hits,[two])
 def test_corrupt_pending_record_is_not_treated_as_permission_for_new_equip(self):
  journal=Journal(self.root,'profile|character');journal.path.parent.mkdir(exist_ok=True)
  for pending in ({'phase':'unknown','proof':{}},{'phase':'sent','proof':None}):
   journal.path.write_text(json.dumps({'version':1,'character':journal.identity,'pending':pending,'completed':[]}),encoding='utf8')
   with self.assertRaises(Hold):journal.read()
  journal.path.write_text(json.dumps({'version':1,'character':journal.identity,'completed':[]}),encoding='utf8')
  with self.assertRaises(Hold):journal.read()


if __name__=='__main__':unittest.main()
