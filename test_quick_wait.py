"""Quick waits on fake clocks and frames. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
import numpy as np
import owner_quick_wait as q

A=np.zeros((10,10));B=np.full((10,10),40.)

class Clock:
    def __init__(self):self.t=100.
    def __call__(self):return self.t

def run(seconds,frames,clicked=True):
    clock=Clock();waited=[];seq=iter(frames)
    def ordinary(self,s):waited.append(s);clock.t+=s
    def look():
        try:return next(seq)
        except StopIteration:return frames[-1]
    wait=q.quick(ordinary,look,clock)
    q.LOCAL.before=A if clicked else None;q.LOCAL.click_at=clock.t
    wait(None,seconds)
    return clock.t-100.

class QuickWait(unittest.TestCase):
    def test_new_screen_that_holds_still_ends_the_wait(self):
        spent=run(1.,[A,B,B,B,B,B])
        self.assertLess(spent,.6)
    def test_no_change_keeps_the_full_wait(self):
        self.assertAlmostEqual(run(1.,[A]*20),1.,places=3)
    def test_moving_screen_keeps_the_full_wait(self):
        frames=[np.full((10,10),float(v)) for v in range(10,200,10)]
        self.assertAlmostEqual(run(1.,frames),1.,places=3)
    def test_short_polls_and_waits_without_a_click_are_untouched(self):
        self.assertAlmostEqual(run(.1,[A,B,B,B]),.1,places=3)
        self.assertAlmostEqual(run(1.,[A,B,B,B],clicked=False),1.,places=3)
    def test_one_quick_wait_per_click(self):
        run(1.,[A,B,B,B]);self.assertIsNone(q.LOCAL.before)
    def test_a_press_through_down_and_up_arms_the_wait(self):
        calls=[];down=lambda self,k,v:calls.append(('down',k));up=lambda self,k,v:calls.append(('up',k))
        q.LOCAL.before=None
        d,u=q.watch_press(down,up,lambda:A,lambda:5.)
        d(None,'mouse','left');self.assertIsNone(q.LOCAL.before);u(None,'mouse','left')
        self.assertIs(q.LOCAL.before,A);self.assertEqual(q.LOCAL.click_at,5.);self.assertEqual(calls,[('down','mouse'),('up','mouse')])
    def test_the_end_of_a_transaction_finishes_the_press(self):
        from contextlib import contextmanager
        @contextmanager
        def ordinary(self):yield 'inputs'
        q.LOCAL.before=None;q.LOCAL.pressing=A
        with q.watch_transaction(ordinary,lambda:7.)(None) as got:self.assertEqual(got,'inputs')
        self.assertIs(q.LOCAL.before,A);self.assertEqual(q.LOCAL.click_at,7.);self.assertIsNone(q.LOCAL.pressing)
    def test_capture_failure_keeps_the_full_wait(self):
        self.assertAlmostEqual(run(1.,[None]),1.,places=3)

if __name__=='__main__':unittest.main()
