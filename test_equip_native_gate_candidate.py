exec((__import__('pathlib').Path(__file__).parent.parent/'qa_runtime_20261101/bootstrap.py').read_text(encoding='utf8'))
import threading,unittest
import owner_equip_native_gate_candidate as gate

class Detector:
 def find(self,name,*args,**kwargs):return ('hit',name)
class Service:
 def __init__(self):self.detector=Detector()

class NativeGateTests(unittest.TestCase):
 def setUp(self):gate.LOCAL.inside_inventory=False
 def test_only_native_inventory_ready_is_blocked(self):
  calls=[];Service.__init__=gate.wrap_init(Service.__init__,'READY')
  def native():
   service=Service();calls.append(service.detector.find('READY'));calls.append(service.detector.find('BOX'))
   return True
  self.assertTrue(gate.wrap_inventory(native)())
  self.assertEqual(calls,[None,('hit','BOX')]);self.assertEqual(Service().detector.find('READY'),('hit','READY'))
 def test_stop_exception_restores_thread_state(self):
  def native():raise RuntimeError('stop')
  with self.assertRaises(RuntimeError):gate.wrap_inventory(native)()
  self.assertFalse(gate.LOCAL.inside_inventory)
 def test_unrelated_thread_not_affected(self):
  Service.__init__=gate.wrap_init(Service.__init__,'READY');seen=[]
  def native():
   thread=threading.Thread(target=lambda:seen.append(Service().detector.find('READY')))
   thread.start();thread.join();return Service().detector.find('READY')
  self.assertIsNone(gate.wrap_inventory(native)());self.assertEqual(seen,[('hit','READY')])
 def test_missing_detector_fails_closed(self):
  class Bad:
   def __init__(self):pass
  Bad.__init__=gate.wrap_init(Bad.__init__,'READY')
  with self.assertRaises(RuntimeError):gate.wrap_inventory(Bad)()

if __name__=='__main__':unittest.main(verbosity=2)
