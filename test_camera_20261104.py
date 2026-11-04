"""Camera zoom at start, with a fake mission UI. Never a game test."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_camera as c

class Zoom(unittest.TestCase):
    def run_it(self,wheel):
        ui=S(wheel=wheel)
        with patch('owner_mission_ui.MissionUI',return_value=ui):return c.zoom_out(S(),S(),S())
    def test_wheels_down_over_the_world(self):
        calls=[]
        def wheel(direction,notches,**kw):calls.append((direction,notches,kw['at'],kw['verify_cursor']))
        self.assertTrue(self.run_it(wheel));self.assertEqual(calls,[(-1,c.NOTCHES,c.AT,True)])
    def test_a_failure_never_stops_the_work(self):
        def wheel(*a,**k):raise RuntimeError('입력 대상 확인 필요')
        self.assertFalse(self.run_it(wheel))
    def test_a_stop_still_passes_through(self):
        class Stop(BaseException):pass
        def wheel(*a,**k):raise Stop()
        with self.assertRaises(Stop):self.run_it(wheel)
    def test_once_per_start(self):
        adapter=S();first,second=S(),S();done=[]
        with patch.object(c,'zoom_out',lambda *a:done.append(1) or True):
            c.zoom_once(adapter,first,None);c.zoom_once(adapter,first,None);self.assertEqual(len(done),1)
            c.zoom_once(adapter,second,None);self.assertEqual(len(done),2)
    def test_it_stays_off_an_open_panel(self):
        scenes=[]
        def wheel(direction,notches,**kw):scenes.append(kw['scene'])
        with patch('owner_boss_range.panel_open',return_value=True):self.run_it(wheel)
        self.assertFalse(scenes[0](None))
        with patch('owner_boss_range.panel_open',return_value=False):self.run_it(wheel)
        self.assertTrue(scenes[1](None))

if __name__=='__main__':unittest.main()
