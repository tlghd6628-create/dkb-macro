"""Saved PNG + original compiled sequence over fake services. No game inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
import copy,logging,threading,unittest
from contextlib import nullcontext
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
from biol_base.session import Context,Cancelled
from roi_runtime import RoiDetector
from project_adapter import market_inventory as native,town_services
from owner_disassembly_ui import observe,assets,Hold
from owner_disassembly_settings import install,MASTER,grade_key,EXEC,CONFIRM

E=bootstrap.T/'reward_ui_20261103/evidence'
FRAMES=[np.asarray(Image.open(E/f'grade-state-{i}.png').convert('RGB')) for i in range(3)]


class Stored(unittest.TestCase):
 def test_all_three_user_photos_and_blank_reward_preview(self):
  for frame,states,empty in zip(FRAMES,((False,False,False),(True,True,False),(True,True,True)),(True,False,False)):
   actual=observe(frame);self.assertIsNotNone(actual);self.assertEqual(actual.states,states);self.assertIs(actual.empty,empty)
 def test_uses_panel_relative_controls_on_another_background(self):
  frame=np.zeros_like(FRAMES[2]);frame[140:335,537:705]=FRAMES[2][140:335,537:705]
  actual=observe(frame);self.assertEqual(actual.states,(True,True,True))
  shifted=np.zeros_like(frame);shifted[3:,2:]=frame[:-3,:-2]
  actual=observe(shifted);self.assertEqual(actual.states,(True,True,True));self.assertEqual(actual.origin,(2,3))
 def test_unknown_missing_and_ambiguous_controls_are_not_guessed(self):
  self.assertIsNone(observe(np.zeros_like(FRAMES[0])))
  frame=FRAMES[0].copy();frame[249:267,611:652]=0
  self.assertIsNone(observe(frame));self.assertIsNone(observe(frame[:400]))
 def test_original_execution_template_matches_all_user_photos(self):
  detector=RoiDetector(bootstrap.A/'profiles/DKB',[EXEC])
  for frame in FRAMES:self.assertIsNotNone(detector.find(EXEC,frame,threshold=.9))


class Detector:
 def __init__(self,service,names):
  self.service=service;self.original=RoiDetector(bootstrap.A/'profiles/DKB',names);self.entries=self.original.entries
 def find(self,name,frame,**kwargs):
  if name==CONFIRM:
   if not self.service.modal:return None
   row=self.entries[name];x,y,w,h=(row[k] for k in ('x','y','w','h'))
   return (x+w//2,y+h//2,(x,y,x+w,y+h))
  return self.original.find(name,frame,**kwargs)


class FakeService:
 initial=(True,True,True);manual=False;items=True;corrupt=False;stop_on_select=False;instances=[];start_panel=True
 def __init__(self,adapter,context,inputs,names):
  self.adapter,self.context,self.inputs=adapter,context,inputs;self.states=list(self.initial)
  self.manual_selected=self.manual;self.modal=False;self.closed=False;self.panel=self.start_panel;self.calls=[];self.consumed=[];self.checks=0
  self.detector=Detector(self,names)
  self.actions=S(detect=lambda name,**kw:self.detector.find(name,self.capture(),threshold=.9))
  self.log=logging.getLogger('fake-disassembly');self.instances.append(self)
 def check(self):
  self.context.checkpoint();self.checks+=1
  if self.checks>200:raise RuntimeError('fake bounded stop')
 def capture(self):
  if self.closed or self.modal:return np.zeros_like(FRAMES[0])
  frame=FRAMES[0].copy();layout,images=assets()
  if not self.panel:frame[140:335,537:705]=0;return frame
  for index,code in enumerate(('normal','rare','hero')):
   x1,y1,x2,y2=layout['boxes'][code];frame[y1:y2,x1:x2]=images[code+('-on' if self.states[index] else '-off')]
  if self.items and (any(self.states) or self.manual_selected):
   x1,y1,x2,y2=layout['boxes']['empty'];frame[y1:y2,x1:x2]=FRAMES[1][y1:y2,x1:x2]
  if self.corrupt:frame[249:267,611:652]=0
  return frame
 def click_hit(self,hit,*args,**kwargs):
  self.context.checkpoint();x,y=hit[:2];layout,_=assets()
  for index,code in enumerate(('normal','rare','hero')):
   x1,y1,x2,y2=layout['boxes'][code]
   if x1<=x<x2 and y1<=y<y2:
    self.states[index]=not self.states[index];self.calls.append(('grade',code,self.states[index]))
    if index==1 and self.states[index] is False:self.manual_selected=False
    if self.stop_on_select and index==0 and self.states[index]:self.context.stop.set()
    return True
  if 645<=x<671 and 301<=y<316:
   self.calls.append(('execute',tuple(self.states)));self.modal=True;return True
  if 473<=x<511 and 318<=y<327:
   self.calls.append(('confirm',tuple(self.states)));self.consumed.append(tuple(self.states));self.modal=False;self.panel=False;return True
  if 873<=x<886 and 453<=y<465:self.panel=not self.panel;self.calls.append(('entry',self.panel));return True
  if x>865 and y<75:self.closed=True
  self.calls.append(('native',x,y));return True
 def point(self,*args,**kwargs):return True


class NativeSequence(unittest.TestCase):
 def setUp(self):
  FakeService.initial=(True,True,True);FakeService.manual=False;FakeService.items=True
  FakeService.corrupt=False;FakeService.stop_on_select=False;FakeService.instances=[]
  FakeService.start_panel=True
 def run_original(self,*,function=None):
  context=Context(threading.Event(),threading.Event());context.wait=lambda seconds:context.checkpoint()
  context.status=S(set_current_task=lambda *args:None)
  adapter=S(values={MASTER:True,grade_key('normal'):True,grade_key('rare'):False,grade_key('hero'):False},
            project=S(root=bootstrap.A,app_id='DKB'),status=context.status,log=logging.getLogger('fake'),app_id='DKB')
  module=S(run_equipment_disassembly=function or native.run_equipment_disassembly)
  with patch.object(town_services,'TownServices',FakeService),patch.object(native,'open_inventory',return_value=True):
   install(module)
   fake_inputs=S(transaction=nullcontext,_guard_target=context.checkpoint,move=lambda *args:context.checkpoint())
   try:result=module.run_equipment_disassembly(adapter,context,fake_inputs)
   except Cancelled:result='cancelled'
  return result,adapter,FakeService.instances[-1]
 def test_original_native_sequence_only_commits_the_configured_normal_grade(self):
  result,adapter,service=self.run_original()
  self.assertIs(result,True);self.assertEqual(service.consumed,[(True,False,False)])
  self.assertEqual([row for row in service.calls if row[0]=='execute'],[('execute',(True,False,False))])
  self.assertEqual(adapter._owner_disassembly_outcome['state'],'processed_unverified')
  self.assertFalse(adapter._owner_disassembly_outcome['verified'])
  self.assertFalse(any(row[0]=='entry' for row in service.calls))
 def test_original_entry_still_opens_a_closed_disassembly_dialog(self):
  FakeService.start_panel=False
  result,adapter,service=self.run_original()
  self.assertIs(result,True);self.assertEqual([c for c in service.calls if c[0]=='entry'],[('entry',True)])
  self.assertEqual(service.consumed,[(True,False,False)])
 def test_manual_subset_is_cleared_before_selecting_normal(self):
  FakeService.initial=(False,False,False);FakeService.manual=True
  result,adapter,service=self.run_original()
  self.assertIs(result,True);self.assertFalse(service.manual_selected)
  self.assertEqual(service.consumed,[(True,False,False)])
 def test_no_eligible_items_does_not_press_execute(self):
  FakeService.items=False
  result,adapter,service=self.run_original()
  self.assertEqual(service.consumed,[]);self.assertFalse(any(c[0]=='execute' for c in service.calls))
  self.assertEqual(adapter._owner_disassembly_outcome['state'],'not_attempted')
 def test_unknown_toggle_prevents_the_original_commit(self):
  FakeService.corrupt=True
  result,adapter,service=self.run_original()
  self.assertEqual(service.consumed,[]);self.assertFalse(any(c[0]=='execute' for c in service.calls))
  self.assertEqual(adapter._owner_disassembly_outcome['state'],'not_attempted')
 def test_stop_between_select_and_commit_propagates_no_resource_input(self):
  FakeService.stop_on_select=True
  result,adapter,service=self.run_original()
  self.assertEqual(result,'cancelled');self.assertEqual(service.consumed,[])
  self.assertFalse(any(c[0]=='execute' for c in service.calls))
 def test_confirmation_without_grade_proof_is_blocked(self):
  def bad(adapter,context,inputs):
   service=town_services.TownServices(adapter,context,inputs,[EXEC,CONFIRM]);service.modal=True
   hit=service.detector.find(CONFIRM,service.capture(),threshold=.9);service.click_hit(hit)
  result,adapter,service=self.run_original(function=bad)
  self.assertEqual(service.consumed,[]);self.assertEqual(adapter._owner_disassembly_outcome['state'],'not_attempted')
 def test_second_execute_is_not_repeated_while_result_is_pending(self):
  def twice(adapter,context,inputs):
   service=town_services.TownServices(adapter,context,inputs,[EXEC,CONFIRM])
   hit=service.detector.find(EXEC,service.capture(),threshold=.9);service.click_hit(hit);service.modal=False
   service.click_hit(hit)
  result,adapter,service=self.run_original(function=twice)
  self.assertEqual(len([c for c in service.calls if c[0]=='execute']),1)
  self.assertEqual(adapter._owner_disassembly_outcome['state'],'sent_unconfirmed')


if __name__=='__main__':unittest.main()
