exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf8'))
import threading,unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import owner_startup_stage as startup,owner_quest_emote_candidate as emote
import runtime_capture
from project_adapter._entry import Adapter
from project_adapter import town_services

class StartupWiring(unittest.TestCase):
 def check_scene(self,kind):
  a=np.zeros((479,897,3),dtype=np.uint8);b=np.ones((479,897,3),dtype=np.uint8)
  frames=iter((a,b));seen=[];events=[]
  session=NS(start=lambda:None,resume=lambda:None,lock=threading.Lock(),snapshot=lambda:{'status':'stopped'})
  gui=NS(session=session);ctx=NS(checkpoint=lambda:None,wait=lambda _:None)
  adapter=NS(mode='sub_quest');inputs=NS()
  service=NS(capture=lambda:next(frames),detector=NS())
  def normalizer(_adapter,_ctx,_inputs,*,frames,field_confirmed):
   seen.append((frames,field_confirmed));return False
  def publish(g,*args):g._owner_stage_snapshot={'location_label':'test'}
  def ordinary(*args):events.append('normal');return 'normal-result'
  with patch.object(Adapter,'run',ordinary),patch.object(runtime_capture,'capture',lambda *a:None),patch.object(town_services,'TownServices',return_value=service),patch.object(startup,'scene',return_value=kind),patch.object(startup,'publish',side_effect=publish),patch.object(startup,'resume_dungeon',side_effect=lambda *a:events.append('dungeon')),patch.object(emote,'normalize_after_stop',side_effect=normalizer):
   startup.install(gui);result=Adapter.run(adapter,ctx,inputs)
  self.assertEqual(result,'normal-result');self.assertEqual(len(seen),1)
  self.assertIs(seen[0][0][0],a);self.assertIs(seen[0][0][1],b)
  self.assertTrue(all(isinstance(x,np.ndarray) and x.dtype==np.uint8 and x.shape==(479,897,3) for x in seen[0][0]))
  self.assertEqual(seen[0][1],kind=='field')
  self.assertEqual(events,['dungeon','normal'] if kind=='dungeon' else ['normal'])
 def test_field_reaches_normalizer_and_native(self):self.check_scene('field')
 def test_inventory_reaches_normalizer_and_native(self):self.check_scene('inventory')
 def test_dungeon_keeps_original_continuation(self):self.check_scene('dungeon')
 def test_bad_frame_type_reports_clear_pending(self):
  from pathlib import Path
  from tempfile import TemporaryDirectory
  with TemporaryDirectory() as d,patch('roi_runtime.RoiDetector',return_value=NS(find=lambda *args,**kwargs:None)):
   with self.assertRaisesRegex(emote.Pending,'형식'):
    emote.normalize_after_stop(NS(project=NS(root=Path(d))),NS(),None,frames=(np.zeros((479,897,3),dtype=np.uint8),'field'))

if __name__=='__main__':unittest.main()
