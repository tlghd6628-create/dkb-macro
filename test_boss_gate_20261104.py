"""World boss power floor with a fake reader. Never a game test."""
import sys
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import time,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_boss_gate as gate
from project_adapter._entry import Adapter

class Gate(unittest.TestCase):
    def check(self,power,observed=None,read=None):
        self.progress=S(power=power,observed=time.monotonic() if observed is None else observed)
        self.adapter=getattr(self,'adapter',None) or S()
        self.read=Mock(side_effect=read,return_value=True)
        with patch('owner_progression.state',return_value=self.progress),patch('owner_quest_preflight.read_power',self.read):
            return gate.allowed(self.adapter,S(),S())
    def test_below_the_floor_does_not_enter(self):
        self.assertFalse(self.check(149016))
        self.assertFalse(self.check(149999))
    def test_exactly_at_or_above_the_floor_enters(self):
        self.assertTrue(self.check(150000))
        self.adapter=None;self.assertTrue(self.check(182000))
    def test_an_unreadable_power_does_not_enter(self):
        self.assertFalse(self.check(None));self.read.assert_called_once()
    def test_an_old_reading_is_read_again_first(self):
        def grew(*a):self.progress.power=151000
        self.assertTrue(self.check(149000,observed=time.monotonic()-500,read=grew));self.read.assert_called_once()
    def test_a_denial_does_not_reopen_the_inventory_through_the_window(self):
        self.assertFalse(self.check(149016,observed=time.monotonic()-500))
        self.assertFalse(self.check(149016,observed=time.monotonic()-500));self.read.assert_not_called()
    def test_a_denied_power_that_has_grown_is_looked_at_again(self):
        self.assertFalse(self.check(149016))
        self.assertTrue(self.check(150500))

class Wiring(unittest.TestCase):
    def run_gated(self,permitted):
        calls=[]
        def ordinary(adapter,context,inputs):
            calls.append('native');return 'entered'
        with patch.object(Adapter,'_run_field_boss_entry',ordinary),patch.object(gate,'allowed',return_value=permitted),\
             patch('owner_boss_range.loosen'),patch('owner_boss_range.restore'):
            gate.install()
            return Adapter._run_field_boss_entry(S(),S(checkpoint=lambda:None,stop=threading.Event()),S()),calls
    def test_below_the_floor_never_reaches_the_native_entry(self):
        self.assertEqual(self.run_gated(False),(True,[]))
    def test_at_the_floor_reaches_it(self):
        self.assertEqual(self.run_gated(True),('entered',['native']))
    def test_native_outer_entry_only_goes_through_this_one(self):
        code=Adapter.run_field_boss_entry.__wrapped__ if hasattr(Adapter.run_field_boss_entry,'__wrapped__') else Adapter.run_field_boss_entry
        calls=[]
        fake=S(_run_field_boss_entry=lambda c,i:calls.append('inner') or True)
        try:result=code(fake,S(checkpoint=lambda:None),S())
        except AttributeError as exc:self.fail('outer entry needs more than the inner one: %s'%exc)
        self.assertEqual(calls,['inner'])

if __name__=='__main__':unittest.main()
