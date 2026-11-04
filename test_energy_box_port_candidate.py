import unittest,tempfile,types,sys
import json
from pathlib import Path
import numpy as np
from PIL import Image
from unittest.mock import patch
sys.path.insert(0,r'C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031/owner')
sys.path.insert(0,str(Path(__file__).parent))
from owner_energy_box_runtime_candidate import Journal,run,Hold
from owner_energy_box_port_candidate import Port
BASE=Path(__file__).parent/'live_fixtures'
def image(n):return np.array(Image.open(BASE/n).convert('RGB'))
class Context:
 def checkpoint(self):pass
 def wait(self,s):pass
class Service:
 def __init__(self):self.page='inventory';self.clicks=[]
 def check(self):pass
 def capture(self):
  names={'inventory':'inventory_before_energy_trial_044834.png','detail':'energy_box_after49_native_1.png','select':'energy_counter_1_of49_native_1.png'}
  return image(names[self.page])
 def click_hit(self,hit):
  x,y,_=hit;self.clicks.append((x,y))
  if (x,y)==(839,291):self.page='detail'
  if (x,y)==(450,363):self.page='select'
  if (x,y)==(449,356):self.page='detail'

class MultiService(Service):
 def __init__(self,page='inventory'):super().__init__();self.page=page
 def capture(self):
  if self.page=='field':return np.zeros((479,897,3),dtype=np.uint8)
  names={'inventory':'inventory_before_energy_trial_044834.png','wrong':'wrong_recalibration_box_044837.png',
         'detail':'energy_box_after49_native_1.png','select':'energy_counter_1_of49_native_1.png',
         'unselected':'energy_no_selection_050424.png'}
  return image(names[self.page])
 def click_hit(self,hit):
  x,y,_=hit;self.clicks.append((x,y))
  if (x,y)==(839,291):self.page='wrong'
  if (x,y)==(728,328):self.page='detail'
  if (x,y)==(510,106):self.page='inventory'
  if (x,y)==(450,363):self.page='select'
  if (x,y)==(449,356):self.page='detail'
  if (x,y)==(534,115):self.page='inventory'
class Tests(unittest.TestCase):
 def test_saved_frame_driven_input_and_pending(self):
  with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
   fake=types.ModuleType('project_adapter');fake.market_inventory=types.SimpleNamespace(open_inventory=lambda service:True)
   previous=sys.modules.get('project_adapter');sys.modules['project_adapter']=fake
   try:
    port=Port.__new__(Port);port.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root=root));port.context=Context();port.service=Service();port.opened=False
    journal=Journal(root,'s|c');journal.note_manual_event(event_id='observed',name='생명',quantity=1,source='manual proof')
    with self.assertRaises(Hold) as caught:run(port,journal,['생명','여명','몽환'],guard=lambda:True)
    self.assertEqual(port.service.clicks,[(839,291),(450,363),(449,356)])
    self.assertEqual(journal.read()['pending']['phase'],'sent');self.assertEqual(journal.read()['confirmed']['여명'],0)
    captures=list((Path(root)/'logs'/'energy-claim-evidence').glob('*/*.png'))
    self.assertTrue(4<=len(captures)<=32)
    self.assertEqual(len(list((Path(root)/'logs'/'energy-claim-evidence').glob('*/capture-manifest.json'))),1)
    with self.assertRaises(Hold) as caught:run(port,journal,['생명','여명','몽환'],guard=lambda:True)
    self.assertEqual(len(port.service.clicks),3)
   finally:
    if previous is None:sys.modules.pop('project_adapter',None)
    else:sys.modules['project_adapter']=previous
 def test_wrong_box_closed_then_correct_box_selected(self):
  fake=types.ModuleType('project_adapter');fake.market_inventory=types.SimpleNamespace(open_inventory=lambda service:True)
  with patch.dict(sys.modules,{'project_adapter':fake}):
   p=Port.__new__(Port);p.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root='.'));p.context=Context();p.service=MultiService();p.opened=False
   final=p.prepare_one('여명',lambda:True)
   self.assertEqual(final['boxes'],49);self.assertEqual(final['name'],'여명')
   self.assertEqual(p.service.clicks,[(839,291),(510,106),(728,328),(450,363)])
 def test_wrong_box_cleanup_does_not_open_or_consume(self):
  import owner_equipment_boxes
  p=Port.__new__(Port);p.context=Context();p.service=MultiService('wrong');p.opened=True;p.view='pending_detail'
  with patch.dict(sys.modules,{'owner_movement':types.SimpleNamespace(field_hud=lambda f:True)}),patch.object(owner_equipment_boxes,'close_inventory',side_effect=lambda service:setattr(service,'page','field')):
   p.close_known()
  self.assertEqual(p.service.clicks,[(510,106)])
 def test_no_matching_icons_does_not_block_known_inventory_cleanup(self):
  import owner_equipment_boxes
  p=Port.__new__(Port);p.context=Context();p.service=MultiService('inventory');p.opened=True;p.view='inventory'
  with patch.dict(sys.modules,{'owner_movement':types.SimpleNamespace(field_hud=lambda f:True)}),patch.object(owner_equipment_boxes,'close_inventory',side_effect=lambda service:setattr(service,'page','field')):
   p.close_known()
  self.assertEqual(p.service.clicks,[])
 def test_unselected_known_layout_can_close_without_any_selection(self):
  import owner_equipment_boxes
  p=Port.__new__(Port);p.context=Context();p.service=MultiService('unselected');p.opened=True;p.view='pending_selection'
  with patch.dict(sys.modules,{'owner_movement':types.SimpleNamespace(field_hud=lambda f:True)}),patch.object(owner_equipment_boxes,'close_inventory',side_effect=lambda service:setattr(service,'page','field')):p.close_known()
  self.assertEqual(p.service.clicks,[(534,115)])
 def test_unselected_then_dawn_requires_strict_selected_frame(self):
  fake=types.ModuleType('project_adapter');fake.market_inventory=types.SimpleNamespace(open_inventory=lambda service:True)
  class UnselectedService(Service):
   def capture(self):
    if self.page=='unselected':return image('energy_no_selection_050424.png')
    return super().capture()
   def click_hit(self,hit):
    x,y,_=hit;self.clicks.append((x,y))
    if (x,y)==(839,291):self.page='detail'
    if (x,y)==(450,363):self.page='unselected'
    if (x,y)==(450,205):self.page='select'
  with patch.dict(sys.modules,{'project_adapter':fake}):
   p=Port.__new__(Port);p.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root='.'));p.context=Context();p.service=UnselectedService();p.opened=False
   state=p.prepare_one('여명',lambda:True)
   self.assertEqual((state['name'],state['quantity'],state['boxes']),('여명',1,49))
   self.assertEqual(p.service.clicks,[(839,291),(450,363),(450,205)])
 def test_pending_receipt_known_exact_inventory_recovery(self):
  import owner_equipment_boxes
  class SameScene(MultiService):
   def capture(self):
    f=super().capture() if self.page!='field' else image('inventory_before_energy_trial_044834.png')
    if self.page=='field':f[11:23,34:53]=0;f[45:68,721:751]=0
    return f
  p=Port.__new__(Port);p.context=Context();p.service=SameScene('inventory');p.opened=True;p.view='pending_receipt'
  ref=p.service.capture();p.inventory_reference=(ref.copy(),ref.copy())
  with patch.dict(sys.modules,{'owner_movement':types.SimpleNamespace(field_hud=lambda f:True)}),patch.object(owner_equipment_boxes,'close_inventory',side_effect=lambda service:setattr(service,'page','field')):p.close_known()
  self.assertEqual(p.service.clicks,[])
 def test_pending_receipt_unknown_popup_blocks(self):
  class Unknown(MultiService):
   def capture(self):
    f=super().capture();f[140:200,400:500]=0;return f
  p=Port.__new__(Port);p.context=Context();p.service=Unknown('inventory');p.opened=True;p.view='pending_receipt'
  f=image('inventory_before_energy_trial_044834.png');p.inventory_reference=(f.copy(),f.copy())
  with self.assertRaises(RuntimeError):p.close_known()
  self.assertEqual(p.service.clicks,[])
 def test_actual_saved_reward_and_48_produce_evidence_with_nonce(self):
  class Sequence(Service):
   def __init__(self):self.i=0
   def capture(self):
    names=['energy_after48_native_00.png','energy_reward_dawn_native_06.png','energy_reward_dawn_native_07.png']+['energy_after48_native_18.png']*30
    frame=image(names[min(self.i,len(names)-1)]);self.i+=1;return frame
  with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
   p=Port.__new__(Port);p.adapter=types.SimpleNamespace(project=types.SimpleNamespace(root=root));p.context=Context();p.service=Sequence()
   p.evidence_identity={'character':'256b0f6111f96bcaaf78501c','scope':'configured','receipt_key':'r'};p.operation_id='operation';p.expected_boxes_before=49
   receipt=p.receipt('여명',lambda:True)
   self.assertIsNotNone(receipt);self.assertEqual((receipt['boxes'],receipt['quantity']),(48,1));self.assertEqual(len(receipt['evidence_sha256']),4)
   manifests=list((Path(root)/'logs'/'energy-claim-evidence').glob('*/capture-manifest.json'));self.assertEqual(len(manifests),1)
   manifest=json.loads(manifests[0].read_text(encoding='utf8'));self.assertEqual(manifest['operation_id'],'operation');self.assertEqual(manifest['identity']['character'],'256b0f6111f96bcaaf78501c')
if __name__=='__main__':unittest.main()
