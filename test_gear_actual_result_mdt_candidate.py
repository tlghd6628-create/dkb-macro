"""Actual saved +41 frames; original final MDT OCR; fake selection only."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from test_gear_native_observer_candidate import Service,Context,Clock
from owner_gear_native_observer_candidate import Observer
from project_adapter import market_inventory as native
from tools.ocr_support import read_growth_number_mdt

class Tests(unittest.TestCase):
 def test_actual_result_pair_reads_41_with_no_resource_input(self):
  folder=bootstrap.A/'logs/gear-holds/20261102T044829-b2a95b80'
  pre=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/gear_list_0241_native_1.png').convert('RGB')).copy()
  frames=[np.asarray(Image.open(folder/f'{i}.png').convert('RGB')).copy() for i in (1,2)]
  service=Service(pre,frames[0]);clock=Clock();ctx=Context(clock)
  # Use the real monotonic clock and let the model warm before starting the
  # paired freshness window, as the product normally does at startup.
  ctx.wait=lambda n:time.sleep(n)
  warm=read_growth_number_mdt(bootstrap.A,frames[0][123:147,317:387].copy(),context=ctx,threshold=.85)
  self.assertEqual(warm.get('value'),41)
  observer=Observer(service,ctx,'test',native,None,None);chosen=[]
  def select(s,row):chosen.append(row['index']);s.phase='post'
  with patch.object(native,'select_growth_equipment',side_effect=select):observer.prepare_and_select(2)
  pending=iter(frames);service.capture=lambda:next(pending).copy()
  observer.minimum_level=40
  result=observer.read_result_pair()
  self.assertTrue(result['screen_proof'],observer.last_reason)
  self.assertEqual([result['first'].enhancement,result['second'].enhancement],[41,41])
  self.assertEqual(result['source'],'native_mdt_result_only');self.assertEqual(chosen,[2]);self.assertFalse(service.clicks)
 def test_actual_mdt_result_can_reconcile_copied_sent_record(self):
  from owner_gear_intent_store_candidate import IntentStore
  from owner_gear_settings_candidate import Store
  from owner_gear_execution_candidate import reconcile_configured_step
  original=bootstrap.A/'settings/owner-gear-settings-2a6715f4a2d11f31df0c102a-intent.json'
  pending=IntentStore(original).pending()
  if not pending or pending['before'].enhancement!=40:self.skipTest('이전 실제 기록 보존 상태 아님')
  identity=pending['before'].character
  pre=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/gear_list_0241_native_1.png').convert('RGB')).copy()
  folder=bootstrap.A/'logs/gear-holds/20261102T044829-b2a95b80'
  frames=[np.asarray(Image.open(folder/f'{i}.png').convert('RGB')).copy() for i in (1,2)]
  service=Service(pre,frames[0]);ctx=Context(Clock());ctx.wait=lambda n:time.sleep(n)
  self.assertEqual(read_growth_number_mdt(bootstrap.A,frames[0][123:147,317:387].copy(),context=ctx,threshold=.85).get('value'),41)
  observer=Observer(service,ctx,identity,native,None,None)
  with patch.object(native,'select_growth_equipment',side_effect=lambda s,row:setattr(s,'phase','post')):observer.prepare_and_select(2)
  observer.minimum_level=40;observer.logical_identity=pending['before'].item
  service.capture=lambda:next(images).copy()
  images=iter(frames)
  with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp:
   path=Store(temp,identity).path;path.parent.mkdir(parents=True,exist_ok=True)
   copied=path.with_name(path.stem+'-intent.json');copied.write_bytes(original.read_bytes())
   out=reconcile_configured_step(ctx,temp,identity,observer.read_result_pair,before_complete=lambda:True)
   self.assertEqual(out,'observed_progress');self.assertIsNone(IntentStore(copied).pending())
  self.assertFalse(service.clicks)
if __name__=='__main__':unittest.main()
