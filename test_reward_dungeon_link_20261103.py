"""Stored frame and shared-reader contract checks. No live OCR or game input."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,tempfile,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from PIL import Image
import numpy as np
from biol_base.session import Context,Cancelled
from tools import time_ocr
import owner_dungeon_time
from owner_reward_context import read_remaining,decision
import owner_special_contexts as special
from roi_runtime import RoiDetector
from owner_startup_stage import scene,DUNGEON,EXIT,MENU

P=bootstrap.A/'logs/scene-corpus/20261103'
FIELD=np.asarray(Image.open(P/'20261103T235147-43301f95/screen.png').convert('RGB'))
DROP=np.asarray(Image.open(P/'20261103T235444-670da0bc/screen.png').convert('RGB'))


class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
  self.ctx=Context(threading.Event(),threading.Event());self.ctx.wait=lambda _:self.ctx.checkpoint()
  self.adapter=S(project=S(root=Path(self.tmp.name)))
  self.service=S(adapter=self.adapter,context=self.ctx,check=Mock(),capture=Mock(return_value=FIELD),
                 detector=S(find=Mock(return_value=(1,1,()))))
 def result(self,seconds):return time_ocr.TimeRead(True,'fixture',seconds)
 def read(self,values):
  with patch('owner_reward_context.time.monotonic',return_value=500),patch.object(time_ocr,'read_time_image',side_effect=values) as reader:
   value=read_remaining(self.service)
  return value,reader
 def test_reuses_shared_reader_on_exact_two_fresh_hud_crops(self):
  value,reader=self.read([self.result(1800),self.result(1800)])
  self.assertEqual(value,1800);self.assertEqual(reader.call_count,2)
  for call in reader.call_args_list:
   self.assertTrue(np.array_equal(call.args[0],FIELD[98:111,3:58]))
   self.assertIs(call.args[2],self.ctx);self.assertEqual(call.kwargs['deadline'],503)
  self.assertIs(self.adapter._owner_reward_dungeon_clock['context'],self.ctx)
  self.assertTrue(decision(True,value)['allowed'])
 def test_ten_minutes_and_zero_stay_blocked(self):
  for remaining in (600,0):
   value,_=self.read([self.result(remaining),self.result(remaining)])
   self.assertEqual(value,remaining);self.assertFalse(decision(True,value)['allowed'])
 def test_failed_inconsistent_and_out_of_bounds_never_mean_zero(self):
  for results in ([time_ocr.TimeRead(error='fixture')],[self.result(1800),self.result(1900)],
                  [self.result(1800),self.result(1700)],[self.result(90000)]):
   value,_=self.read(results);self.assertIsNone(value)
 def test_timeout_is_held_and_stop_propagates(self):
  value,_=self.read(time_ocr.TimeOCRTimeout('fixture'));self.assertIsNone(value)
  with self.assertRaises(Cancelled):self.read(Cancelled())
 def test_existing_ocr_job_and_changed_dungeon_block_read(self):
  self.adapter._owner_stage_ocr_job=S(is_alive=lambda:True)
  with patch.object(time_ocr,'read_time_image') as reader:self.assertIsNone(read_remaining(self.service))
  reader.assert_not_called();self.adapter._owner_stage_ocr_job=None
  self.service.detector.find.return_value=None
  # Both the independent map prefix and native portal proof are absent.
  self.service.capture.return_value=np.zeros((479,897,3),np.uint8)
  with patch.object(time_ocr,'read_time_image') as reader:self.assertIsNone(read_remaining(self.service))
  reader.assert_not_called()
 def test_time_spent_reading_is_subtracted(self):
  with patch('owner_reward_context.time.monotonic',side_effect=[500,502]),patch.object(time_ocr,'read_time_image',side_effect=[self.result(601),self.result(601)]):
   value=read_remaining(self.service)
  self.assertEqual(value,599);self.assertFalse(decision(True,value)['allowed'])
 def test_native_entry_second_look_is_reached_for_impossible_minute(self):
  page=lambda value:[{'rec_texts':[value],'rec_scores':[.99]}]
  wrapped=owner_dungeon_time.wrap(time_ocr.read_time_image,time_ocr)
  with patch('tools.ocr_support.get_paddle_engine',return_value=Mock()),patch.object(time_ocr,'_predict',side_effect=[page('03:67:51'),page('03:57:51'),page('03:57:51')]),patch.object(time_ocr,'read_time_image',wrapped),patch('owner_reward_context.time.monotonic',return_value=500):
   value=read_remaining(self.service)
  self.assertEqual(value,3*3600+57*60+51)
 def test_actual_235444_dungeon_drop_remains_dungeon(self):
  detector=RoiDetector(bootstrap.A/'profiles/DKB',list(dict.fromkeys([DUNGEON,EXIT,MENU,*special.NAMES])))
  self.assertIsNotNone(detector.find('체크_보물찾기_아이템획득',DROP,threshold=.95))
  self.assertIsNone(special.classify(detector,DROP));self.assertEqual(scene(detector,DROP),'dungeon')


if __name__=='__main__':unittest.main()
