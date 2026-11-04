import os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from owner_gear_settings_candidate import Store
from owner_gear_intent_store_candidate import IntentStore
from owner_gear_decision_candidate import Observation
from owner_gear_reconcile_entry_candidate import run

class Context:
 def checkpoint(self):pass
 def wait(self,n):pass
class Service:
 detector=object()
 def check(self):pass
 def capture(self):return 'field'
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
  self.identity='test';self.values={'auto_growth.equipment.enabled':False,'auto_growth.blessing.enabled':True,'auto_growth.taoist.enabled':True}
  self.adapter=SimpleNamespace(project=SimpleNamespace(root=self.temp.name),values=self.values);self.ctx=Context()
  p=Store(self.temp.name,self.identity).path;self.intent=IntentStore(p.with_name(p.stem+'-intent.json'))
 def pending(self):
  row=Observation(1,10.,self.identity,'item','growth-slot:2','일반',40,None,None,True,None,None)
  self.intent.begin({'kind':'enhance','before':row,'second':row});self.intent.mark_sent()
 def test_no_pending_has_no_ui_or_entry(self):
  calls=[];out=run(self.adapter,self.ctx,None,self.identity,entry=lambda *a:calls.append('entry'),service_factory=lambda *a:calls.append('service'))
  self.assertEqual(out['state'],'no_pending');self.assertEqual(calls,[])
 def test_receipt_only_flags_restore_and_no_extra_processing(self):
  self.pending();seen=[]
  def entry(adapter,ctx,inputs,*,equipment_test=False):
   seen.append((adapter._owner_growth_reconcile_only,dict(adapter.values),equipment_test))
   self.intent.complete('observed_progress')
  with patch('owner_startup_stage.scene',return_value='field'):
   out=run(self.adapter,self.ctx,None,self.identity,entry=entry,service_factory=lambda *a:Service())
  self.assertEqual(out['state'],'observed_progress');self.assertEqual(len(seen),1)
  self.assertTrue(seen[0][0]);self.assertTrue(seen[0][1]['auto_growth.equipment.enabled'])
  self.assertTrue(seen[0][2])
  self.assertFalse(seen[0][1]['auto_growth.blessing.enabled']);self.assertFalse(seen[0][1]['auto_growth.taoist.enabled'])
  self.assertIs(self.adapter.values,self.values);self.assertFalse(hasattr(self.adapter,'_owner_growth_reconcile_only'))
 def test_pending_remains_and_flags_restore_on_error(self):
  self.pending()
  def entry(*args,**kwargs):raise RuntimeError('test error')
  with patch('owner_startup_stage.scene',return_value='field'),self.assertRaises(RuntimeError):
   run(self.adapter,self.ctx,None,self.identity,entry=entry,service_factory=lambda *a:Service())
  self.assertEqual(self.intent.pending()['phase'],'sent');self.assertIs(self.adapter.values,self.values)
  self.assertFalse(hasattr(self.adapter,'_owner_growth_reconcile_only'))
 def test_compiled_native_equipment_test_calls_reconcile_and_exits(self):
  import logging
  from project_adapter import achievement_rewards as native,market_inventory as market,town_services
  self.pending();events=[];outer=self
  class NativeService:
   def __init__(self,adapter,context,inputs,names):self.adapter=adapter;self.context=context;self.actions=self;self.log=logging.getLogger('test')
   def check(self):pass
   def detect(self,name,*a,**kw):events.append(('detect',name));return (10,10,(5,5,15,15))
   def click_hit(self,hit):events.append(('navigation',hit))
   def confirm_entry(self,*a,**kw):return True
   def capture(self):return None
   def __getattr__(self,name):return lambda *a,**kw:True
  def equipment(service,**kw):
   outer.assertTrue(service.adapter._owner_growth_reconcile_only);events.append(('receipt-only',kw))
   outer.intent.complete('observed_progress');return True
  self.adapter.status=SimpleNamespace(set_current_task=lambda *a,**kw:None)
  self.adapter.project.app_id='DKB';self.ctx.status=self.adapter.status
  with patch.object(town_services,'TownServices',NativeService),patch.object(market,'run_growth_equipment',new=equipment),patch('owner_startup_stage.scene',return_value='field'):
   out=run(self.adapter,self.ctx,None,self.identity,entry=native.run_growth_entry,service_factory=lambda *a:Service())
  self.assertEqual(out['state'],'observed_progress')
  self.assertEqual(sum(e[0]=='receipt-only' for e in events),1)
  self.assertEqual(sum(e==('detect','버튼_나가기') for e in events),2)
  self.assertIs(self.adapter.values,self.values)
if __name__=='__main__':unittest.main()
