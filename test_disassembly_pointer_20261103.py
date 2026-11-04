"""Actual retained failed frames + fake native sequence; no real input."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,unittest,threading,logging
from types import SimpleNamespace as S
from contextlib import nullcontext
from unittest.mock import patch
import numpy as np
from PIL import Image
from biol_base.session import Context,Cancelled
from test_disassembly_grades_20261103 import FakeService,FRAMES
from owner_disassembly_ui import configure,observe,Hold,park_pointer
from owner_disassembly_settings import install,MASTER,grade_key
from project_adapter import market_inventory as native,town_services

E=bootstrap.T/'disassembly_followup_20261103/evidence'
OFF=np.asarray(Image.open(E/'20261103T234814-99168470/screen.png').convert('RGB'))
ON=np.asarray(Image.open(E/'20261103T234847-2739b5ca/screen.png').convert('RGB'))


class PointerService(FakeService):
 def __init__(self,*args):
  super().__init__(*args);self.obscured=False;self.parks=[];self.inject_change=False
  self.inputs.move=self.move
 def move(self,*at):
  self.context.checkpoint();self.parks.append(at);self.obscured=False
 def capture(self):
  frame=super().capture()
  if self.obscured and self.panel:
   # The exact actual hover/cursor pixels that the old fixture omitted.
   source=ON if self.states[0] else OFF
   frame[249:267,569:611]=source[249:267,569:611]
  if self.inject_change:frame[140:175,537:705]=0
  return frame
 def click_hit(self,hit,*args,**kwargs):
  result=super().click_hit(hit,*args,**kwargs)
  if 569<=hit[0]<611 and 249<=hit[1]<267:self.obscured=True
  return result


class Tests(unittest.TestCase):
 def context(self):
  context=Context(threading.Event(),threading.Event());context.wait=lambda _:context.checkpoint()
  context.status=S(set_current_task=lambda *args:None)
  return context
 def run_native(self,initial,*,park=True):
  PointerService.initial=initial;PointerService.manual=False;PointerService.items=True;PointerService.start_panel=True
  PointerService.corrupt=False;PointerService.stop_on_select=False;PointerService.instances=[]
  context=self.context();adapter=S(values={MASTER:True,grade_key('normal'):True,grade_key('rare'):False,grade_key('hero'):False},
      project=S(root=bootstrap.A,app_id='DKB'),status=context.status,log=logging.getLogger('fake'),app_id='DKB')
  inputs=S(transaction=nullcontext,_guard_target=context.checkpoint,move=lambda *_:None)
  module=S(run_equipment_disassembly=native.run_equipment_disassembly)
  with patch.object(town_services,'TownServices',PointerService),patch.object(native,'open_inventory',return_value=True):
   install(module)
   if park:result=module.run_equipment_disassembly(adapter,context,inputs)
   else:
    with patch('owner_disassembly_ui.park_pointer'),patch('owner_disassembly_ui.time.monotonic',side_effect=range(10000)):
     result=module.run_equipment_disassembly(adapter,context,inputs)
  return result,adapter,PointerService.instances[-1]
 def test_actual_failed_frames_remain_unknown_without_lowered_threshold(self):
  self.assertIsNone(observe(OFF));self.assertIsNone(observe(ON))
 def test_all_selected_is_cleared_then_only_normal_committed(self):
  result,adapter,service=self.run_native((True,True,True))
  self.assertTrue(result);self.assertEqual(service.consumed,[(True,False,False)])
  self.assertGreaterEqual(len(service.parks),5)
  self.assertEqual(sum(c[0]=='execute' for c in service.calls),1)
 def test_all_clear_selects_normal_and_commits_once(self):
  result,adapter,service=self.run_native((False,False,False))
  self.assertTrue(result);self.assertEqual(service.consumed,[(True,False,False)])
  self.assertEqual(sum(c[0]=='execute' for c in service.calls),1)
 def test_omitting_pointer_park_reproduces_the_same_failure(self):
  result,adapter,service=self.run_native((False,False,False),park=False)
  self.assertEqual(service.consumed,[])
  self.assertEqual(adapter._owner_disassembly_outcome['state'],'not_attempted')
  self.assertIn('두 번 확인',adapter._owner_disassembly_outcome['reason'])
 def test_pointer_move_is_blocked_when_dialog_has_changed(self):
  result,adapter,service=self.run_native((False,False,False))
  service.inject_change=True;before=len(service.parks)
  with self.assertRaises(Hold):park_pointer(service,(0,0))
  self.assertEqual(len(service.parks),before)
 def test_stop_blocks_the_pointer_move(self):
  result,adapter,service=self.run_native((False,False,False))
  before=len(service.parks);service.context.stop.set()
  with self.assertRaises(Cancelled):park_pointer(service,(0,0))
  self.assertEqual(len(service.parks),before)


if __name__=='__main__':unittest.main()
