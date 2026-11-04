"""Saved list raster plus fake levels/input only; never a live game test."""
import hashlib,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import bootstrap
import numpy as np
from PIL import Image
import owner_blessing_native_candidate as b
from owner_gear_decision_candidate import Observation
from owner_gear_settings_candidate import Store
from owner_gear_intent_store_candidate import IntentStore
from project_adapter import market_inventory as native

class FakeObserver:
 def __init__(self,service,context,identity,module,pre,rows,row,slot_reader):
  self.service=service;self.context=context;self.identity=identity;self.row=row;self.sequence=0;self.last_state=None
  s=row['slot'];x,y=s['cell_x']+8,s['cell_y']+8
  self.item='blessing-icon:'+hashlib.sha256(pre[y:y+18,x:x+18].tobytes()).hexdigest()
 def read_pair(self,require_resource=True):
  index=self.row['index'];level=self.service.levels[index];active=index not in self.service.shortage
  self.last_state={'slot':index,'level':level,'active':active,'button':native.GROWTH_BLESSING_EXEC_BUTTONS[0],'opening':False}
  first=[]
  for _ in range(2):
   self.context.checkpoint();self.sequence+=1
   first.append(Observation(self.sequence,time.monotonic(),self.identity,self.item,'blessing:'+str(index),str(index)+'번',level,None,None,active,None,None))
   time.sleep(.02)
  return dict(screen_proof=True,first=first[0],second=first[1],resource_mode='native_active',active_pair_verified=active,button_name=native.GROWTH_BLESSING_EXEC_BUTTONS[0],opening=False)
 def verify_final(self,frame,latest,kind):return kind=='enhance'

class Tests(unittest.TestCase):
 def setup_runtime(self,root):
  frame=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/blessing_list_native_1.png').convert('RGB'))
  context=S(checkpoint=lambda:None,wait=lambda n:time.sleep(.02))
  class Service:
   def __init__(self):
    self.detector=object();self.adapter=S(project=S(root=Path(root)));self.actions=[];self.current=None
    self.levels={i:0 for i in range(1,6)};self.shortage=set();self.increment=True;self.after_growth=lambda:None
   def check(self):pass
   def capture(self):return frame.copy()
   def click_hit(self,hit):
    if hit[0]<100:
     self.actions.append(('enhance',self.current))
     if self.increment:self.levels[self.current]+=1
     self.after_growth()
    else:
     self.current=next(r['index'] for r in rows if native._click_xy(r['slot'])==hit[:2]);self.actions.append(('select',self.current))
  from roi_runtime import RoiDetector
  detector=RoiDetector(bootstrap.A/'profiles/DKB',list(native.GROWTH_BLESSING_NAMES))
  rows=b.worn_candidates(native,detector,frame)
  self.assertEqual(len(rows),5)
  service=Service()
  detector.find=lambda name,frame,**kw:(5,5,(1,1,10,10)) if name==native.GROWTH_BLESSING_EXEC_BUTTONS[0] else None
  return service,context,detector,rows
 def targets(self,n=2):return {str(i)+'번':{'enabled':True,'enhance':n,'breakthrough':0} for i in range(1,6)}
 def invoke(self,service,context,detector,rows,**kwargs):
  with patch('roi_runtime.RoiDetector',return_value=detector),patch.object(b,'worn_candidates',return_value=rows),patch.object(b,'BlessingObserver',FakeObserver):
   return b.run_blessing(service,context,'char',kwargs.pop('targets',self.targets()),**kwargs)
 def pending(self,root):
  path=Store(root,'char').path
  return IntentStore(path.with_name(path.stem+'-intent.json')).pending()
 def test_all_five_worn_slots_repeat_to_goal_and_confirm_each_input(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root);b._cursor.pop('char',None)
   self.assertFalse(self.invoke(s,c,d,rows))
   self.assertEqual(s.levels,{i:2 for i in range(1,6)})
   self.assertEqual([a for a in s.actions if a[0]=='enhance'],[(kind,i) for i in range(1,6) for kind in ['enhance']*2])
   out=s.adapter._owner_blessing_growth_outcome
   self.assertEqual((out['actions'],out['confirmed']),(10,10));self.assertTrue(all(v['state']=='targets_met' for v in out['slots'].values()))
   self.assertIsNone(self.pending(root))
 def test_material_shortage_on_one_slot_does_not_skip_other_slots(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root);s.shortage={1};b._cursor.pop('char',None)
   self.invoke(s,c,d,rows)
   self.assertEqual(s.levels,{1:0,2:2,3:2,4:2,5:2})
   self.assertEqual(s.adapter._owner_blessing_growth_outcome['slots']['1']['state'],'hold_material_or_button')
 def test_unknown_result_blocks_remaining_slots_and_restart_never_reclicks(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root);s.increment=False;b._cursor.pop('char',None)
   self.invoke(s,c,d,rows)
   self.assertEqual([a for a in s.actions if a[0]=='enhance'],[('enhance',1)])
   self.assertEqual(self.pending(root)['phase'],'sent')
   s.actions=[];self.assertFalse(self.invoke(s,c,d,rows,reconcile_only=True))
   self.assertFalse(any(a[0]=='enhance' for a in s.actions));self.assertIsNotNone(self.pending(root))
   s.levels[1]=1;s.actions=[]
   self.assertTrue(self.invoke(s,c,d,rows,reconcile_only=True,targets={}))
   self.assertIsNone(self.pending(root));self.assertFalse(any(a[0]=='enhance' for a in s.actions))
 def test_changed_settings_after_input_retains_sent_receipt(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root);current=[True];s.after_growth=lambda:current.__setitem__(0,False);b._cursor.pop('char',None)
   with self.assertRaisesRegex(RuntimeError,'설정'):self.invoke(s,c,d,rows,settings_check=lambda:current[0])
   self.assertEqual(self.pending(root)['phase'],'sent')
   self.assertEqual(len([a for a in s.actions if a[0]=='enhance']),1)
 def test_unverified_breakthrough_is_reported_and_never_inferred_from_enhancement(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root);s.levels={i:50 for i in range(1,6)}
   goals={str(i)+'번':{'enabled':True,'enhance':50,'breakthrough':1} for i in range(1,6)}
   self.invoke(s,c,d,rows,targets=goals)
   self.assertFalse(any(a[0]=='enhance' for a in s.actions))
   self.assertTrue(all(v['state']=='hold_breakthrough_screen_unverified' for v in s.adapter._owner_blessing_growth_outcome['slots'].values()))
 def test_reconcile_only_without_pending_never_opens_or_clicks(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   s,c,d,rows=self.setup_runtime(root)
   self.assertTrue(self.invoke(s,c,d,rows,reconcile_only=True,targets={}))
   self.assertEqual(s.actions,[])

if __name__=='__main__':unittest.main()
