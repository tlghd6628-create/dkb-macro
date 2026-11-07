"""The hunt's own wait runs due timetable jobs (pc2 11-07: red-dot jobs pending 30 min with sleep off). Fakes only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_hunt_memory as hm

class DueJobs(unittest.TestCase):
    def test_runs_idle_once(self):
        with patch('owner_timetable.idle_once',return_value=True) as run:
            self.assertTrue(hm.due_jobs(S(),S(input_depth=0),S(held=())))
        run.assert_called_once()
    def test_not_during_input(self):
        with patch('owner_timetable.idle_once',side_effect=AssertionError('input')):
            self.assertFalse(hm.due_jobs(S(),S(input_depth=1),S(held=())))
            self.assertFalse(hm.due_jobs(S(),S(input_depth=0),S(held=('x',))))
    def test_error_is_held_not_raised(self):
        with patch('owner_timetable.idle_once',side_effect=RuntimeError('x')):
            self.assertFalse(hm.due_jobs(S(),S(input_depth=0),S(held=())))
    def test_tick_calls_it(self):
        import inspect
        self.assertIn('due_jobs(adapter,context,inputs)',inspect.getsource(hm.install))

if __name__=='__main__':unittest.main()
