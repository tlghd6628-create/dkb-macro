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
    def test_a_small_moving_part_does_not_keep_the_wait(self):
        frames=[]
        for i in range(20):
            f=B.copy();f[0,0]=(i%2)*200.;frames.append(f)
        self.assertLess(run(1.,[A]+frames),.6)
    def test_a_window_over_a_moving_field_ends_the_wait(self):
        rng=np.random.default_rng(1);frames=[]
        for i in range(20):
            f=np.zeros((20,20));f[:10,:10]=150.          # the window the click opened, still
            f[15:,:]=rng.integers(0,255,(5,20))          # a quarter of the screen: the fight behind it
            frames.append(f)
        before=np.zeros((20,20));before[15:,:]=rng.integers(0,255,(5,20))
        clock=Clock();waited=[];seq=iter(frames)
        def ordinary(self,s):waited.append(s);clock.t+=s
        wait=q.quick(ordinary,lambda:next(seq,frames[-1]),clock)
        q.LOCAL.before=before;q.LOCAL.click_at=clock.t;wait(None,1.)
        self.assertLess(clock.t-100.,.7)
    def test_only_a_moving_field_keeps_the_wait(self):
        rng=np.random.default_rng(2);frames=[]
        for i in range(20):
            f=np.zeros((20,20));f[15:,:]=rng.integers(0,255,(5,20));frames.append(f)
        clock=Clock();seq=iter(frames)
        def ordinary(self,s):clock.t+=s
        wait=q.quick(ordinary,lambda:next(seq,frames[-1]),clock)
        q.LOCAL.before=np.zeros((20,20));q.LOCAL.click_at=clock.t;wait(None,1.)
        self.assertAlmostEqual(clock.t-100.,1.,places=3)
    def test_a_fade_keeps_the_wait(self):
        frames=[np.full((10,10),float(v)) for v in range(0,200,10)]
        self.assertAlmostEqual(run(1.,frames),1.,places=3)
    def test_a_wait_that_ran_out_says_why(self):
        q.STATS.update(same=0,moving=0,motion=[])
        run(1.,[A]*20)
        frames=[np.full((10,10),float(v)) for v in range(10,200,10)]
        run(1.,frames)
        self.assertEqual((q.STATS['same'],q.STATS['moving']),(1,1));self.assertEqual(q.STATS['motion'],[1.0])
    def test_short_polls_and_waits_without_a_click_are_untouched(self):
        self.assertAlmostEqual(run(.1,[A,B,B,B]),.1,places=3)
        self.assertAlmostEqual(run(1.,[A,B,B,B],clicked=False),1.,places=3)
    def test_later_waits_after_the_same_press_may_end_early_too(self):
        run(1.,[A,B,B,B]);self.assertIs(q.LOCAL.before,A)
    def test_a_press_through_down_and_up_arms_the_wait(self):
        calls=[];down=lambda self,k,v:calls.append(('down',k));up=lambda self,k,v:calls.append(('up',k))
        q.LOCAL.before=None
        d,u=q.watch_press(down,up,lambda:A,lambda:5.)
        d(None,'mouse','left');self.assertIs(q.LOCAL.before,A);u(None,'mouse','left')
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
