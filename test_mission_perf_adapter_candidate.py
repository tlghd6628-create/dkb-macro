import types, unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_mission_perf_adapter_candidate import install

class Collector:
    def __init__(self):self.events=[];self.closed=False
    def mark(self):return 1.0
    def record(self,*args,**kwargs):self.events.append((args,kwargs));return True
    def close(self,timeout=0):self.closed=True

class Parent:
    def frame(self):return 'frame-object'
    def rows(self, *args, **kwargs):return []

class UI(Parent):
    def open(self, mode):return mode
    def wheel(self, direction):return direction
    def selected(self, value):
        if isinstance(value,BaseException):raise value
        return value

class MissionRowUnreadable(Exception):pass
class Pending(Exception):pass

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.module=types.SimpleNamespace(MissionUI=UI,markers=lambda image: [image])
        self.collector=Collector();self.handle=install(self.module,self.collector)
        self.addCleanup(self.handle.close)

    def test_return_values_and_stages(self):
        ui=UI();self.assertEqual(ui.frame(),'frame-object');self.assertEqual(ui.rows(),[])
        self.assertEqual(ui.open('story'),'story');self.assertEqual(ui.wheel(-1),-1)
        self.assertEqual(ui.selected(42),42);self.assertEqual(self.module.markers('x'),['x'])
        self.assertEqual([e[0][0] for e in self.collector.events],
            ['capture','ocr_workflow','mission_open','mission_scroll','mission_select','template_match'])
        self.assertEqual(self.collector.events[1][0][1],'no_match')
        self.assertTrue(all(e[1]['frame_at'] is None for e in self.collector.events))

    def test_errors_are_same_objects_and_classified(self):
        exc=MissionRowUnreadable('private detail must not be sent')
        with self.assertRaises(MissionRowUnreadable) as result:UI().selected(exc)
        self.assertIs(result.exception,exc)
        self.assertEqual(self.collector.events[-1][0][1],'unreadable')
        self.assertNotIn('private',str(self.collector.events))
        with self.assertRaises(Pending):UI().selected(Pending('조건 확인'))
        self.assertEqual(self.collector.events[-1][0][1],'blocked')

    def test_close_restores_owned_and_inherited_methods(self):
        self.handle.close()
        self.assertTrue(self.collector.closed)
        self.assertNotIn('frame',vars(UI));self.assertNotIn('rows',vars(UI))
        self.assertEqual(UI().frame(),'frame-object');self.assertEqual(UI().open('story'),'story')
        self.handle.close()

    def test_duplicate_install_rejected(self):
        with self.assertRaises(ValueError):install(self.module,Collector())

    def test_collector_failure_does_not_change_call(self):
        self.collector.record=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('queue'))
        self.assertEqual(UI().selected('same'),'same')
        exc=ValueError('actual')
        with self.assertRaises(ValueError) as result:UI().selected(exc)
        self.assertIs(result.exception,exc)
        self.collector.mark=lambda: (_ for _ in ()).throw(RuntimeError('clock'))
        self.assertEqual(UI().wheel(1),1)

    def test_optional_timestamp_callback_and_foreign_wrapper(self):
        self.handle.close();other=Collector()
        h=install(self.module,other,frame_timestamp=lambda name,args,kwargs:0.5)
        UI().rows();self.assertEqual(other.events[0][1]['frame_at'],0.5)
        wrapped=UI.open
        def foreign(self,*args,**kwargs):return wrapped(self,*args,**kwargs)
        UI.open=foreign;h.close()
        self.assertIs(UI.open,foreign)
        UI.open=wrapped.__wrapped__

if __name__=='__main__':unittest.main()
