"""A death screen is answered before the screen recovery. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_schedule_priority as sp


class Revive(unittest.TestCase):
    def run_it(self,dead=True,verify_only=False,raises=None):
        calls=[]
        def recover(ui):
            if raises:raise raises
            calls.append('revive');return dead
        def ordinary(stall,**k):calls.append('native');return 'ok'
        stall=NS(adapter=NS(exit_sleep_mode=lambda *a:calls.append('wake')),context=NS(),inputs=NS())
        with patch('owner_death_real.recover',recover),patch('owner_mission_ui.MissionUI',lambda *a:NS(service=None)),\
             patch('owner_job_timing.after_death',lambda a:calls.append('after_death')),\
             patch('owner_worn_stats.skip_scene',lambda service,context,label:calls.append('skip')):
            got=sp.wake_before_recovery(ordinary)(stall,verify_only=verify_only)
        return got,calls
    def test_dead_is_revived_first(self):
        self.assertEqual(self.run_it(),('ok',['wake','revive','after_death','skip','native']))
    def test_alive_goes_on(self):
        self.assertEqual(self.run_it(dead=False),('ok',['wake','revive','skip','native']))
    def test_verify_only_reads_nothing(self):
        self.assertEqual(self.run_it(verify_only=True),('ok',['native']))
    def test_a_failed_read_still_recovers(self):
        self.assertEqual(self.run_it(raises=ValueError('x')),('ok',['wake','skip','native']))
    def test_a_stop_is_not_swallowed(self):
        from biol_base.session import Cancelled
        with self.assertRaises(Cancelled):self.run_it(raises=Cancelled())


if __name__=='__main__':unittest.main()
