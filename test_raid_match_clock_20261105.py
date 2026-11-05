"""The raid module's slower match clock, with a fake time module. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,unittest
from types import SimpleNamespace as S
from owner_raid_preset import MatchClock,MATCH_SCALE,slow_matching


class Real:
 def __init__(self):self.now=100.
 def monotonic(self):return self.now
 def sleep(self,_):return 'slept'


class Clock(unittest.TestCase):
 def test_normal_speed_outside_matching(self):
  real=Real();clock=MatchClock(real);start=clock.monotonic();real.now+=60
  self.assertEqual(clock.monotonic()-start,60)
 def test_slow_while_matching_so_five_minutes_last_longer(self):
  real=Real();clock=MatchClock(real);start=clock.monotonic();clock.scale=MATCH_SCALE;real.now+=749
  self.assertLess(clock.monotonic()-start,300);real.now+=2
  self.assertGreater(clock.monotonic()-start,300)
 def test_other_names_pass_through(self):
  self.assertEqual(MatchClock(Real()).sleep(1),'slept')
 def test_never_runs_backwards_when_the_speed_changes(self):
  real=Real();clock=MatchClock(real);a=clock.monotonic();clock.scale=MATCH_SCALE;real.now+=10;b=clock.monotonic();clock.scale=1;real.now+=10;c=clock.monotonic()
  self.assertLess(a,b);self.assertLess(b,c)


class Wrapped(unittest.TestCase):
 def test_matching_runs_slow_and_is_restored_even_on_error(self):
  seen=[]
  module=S(time=Real(),_run=lambda *a,**k:None)
  class Flow:
   def matching(self,stage,bulk):
    seen.append(module.time.scale)
    if stage==9:raise ValueError('stop')
    return 'entered'
  slow_matching(Flow,module);slow_matching(Flow,module)
  self.assertEqual(Flow().matching(2,False),'entered');self.assertEqual(seen,[MATCH_SCALE]);self.assertEqual(module.time.scale,1)
  with self.assertRaises(ValueError):Flow().matching(9,False)
  self.assertEqual(module.time.scale,1)


if __name__=='__main__':unittest.main()
