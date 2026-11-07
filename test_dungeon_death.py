"""A death inside a 비경 ends the visit and holds the 비경 jobs until +15% power. Fake frames and flows; not a live claim."""
import sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_dungeon_death as d
import owner_dungeon_reentry as r


def adapter(root,power):
    a=S(project=S(root=Path(root)),values={},_owner_progression=S(power=power))
    return a


class Hold(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();(Path(self.tmp.name)/'settings').mkdir()
        self.who=patch('owner_timetable.identity',return_value='me');self.who.start()
    def tearDown(self):self.who.stop();self.tmp.cleanup()
    def test_no_death_runs(self):
        self.assertIsNone(d.held(adapter(self.tmp.name,92148)))
    def test_death_holds_until_fifteen_percent(self):
        a=adapter(self.tmp.name,92148);d.died(a)
        self.assertIn('105,971',d.held(a))
        a._owner_progression.power=105970;self.assertIsNotNone(d.held(a))
        a._owner_progression.power=105971;self.assertIsNone(d.held(a))
    def test_unknown_power_holds_six_hours(self):
        a=adapter(self.tmp.name,None);d.died(a,now=1000.)
        self.assertIsNotNone(d.held(a,now=1000.+3600))
        self.assertIsNone(d.held(a,now=1000.+6*3600))
    def test_gate_only_for_dungeons(self):
        a=adapter(self.tmp.name,92148);d.died(a)
        self.assertTrue(d.gate(a,S(key='daily_dungeon',label='비경탐험')))
        self.assertIsNone(d.gate(a,S(key='raid',label='레이드')))


class Loop(unittest.TestCase):
    def flow(self):
        ctx=S(input_depth=0,checkpoint=lambda:None);ctx.wait=lambda s:None
        return S(context=ctx,adapter=S(),_owner_entered_at=time.monotonic()-60,_owner_native_busy=0)
    def test_death_screen_in_native_sleep_raises(self):
        f=self.flow()
        def native():
            for _ in range(10):f.context.wait(1)
        with patch.object(r,'leave_reader',return_value=S(capture=lambda:'frame')),\
             patch.object(r,'LEAVE_READ_SECONDS',0),patch('owner_dungeon_death.dead_now',return_value=True):
            with self.assertRaises(d.DungeonDied):r.watch_leaving(f,native)
    def test_busy_native_step_is_not_looked_at(self):
        f=self.flow();f._owner_native_busy=1
        with patch.object(r,'leave_reader',side_effect=AssertionError('no look')),patch.object(r,'LEAVE_READ_SECONDS',0):
            r.watch_leaving(f,lambda:[f.context.wait(1) for _ in range(3)])
    def test_run_ends_the_visit_on_death(self):
        calls=[]
        def original(flow):raise d.DungeonDied()
        run=r.wrap_run(original)
        f=self.flow();f.inputs=None
        with patch.object(r,'kind_of',return_value='daily'),patch.object(r,'check_owner'),\
             patch('owner_dungeon_death.recover',side_effect=lambda fl:calls.append('recover')),\
             patch.object(r,'save_record',side_effect=lambda a,k,s,**kw:calls.append(s)),\
             patch.object(r,'completed',side_effect=lambda a,k,s:calls.append('done:'+s)):
            self.assertTrue(run(f))
        self.assertEqual(calls,['recover','death','done:death'])


if __name__=='__main__':unittest.main()
