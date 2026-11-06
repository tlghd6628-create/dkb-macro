"""Short jobs on the way, long ones at a quest's boundary or in the hunt. Fake jobs and plans; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_job_timing as t


def job(key):return NS(key=key,label=key)


class Pick(unittest.TestCase):
    def test_on_the_way_only_short_jobs(self):
        quest=NS(mode='main_quest')
        self.assertEqual(t.pick(quest,[job('gear'),job('mail')]).key,'mail')
        self.assertIsNone(t.pick(quest,[job('gear_equip'),job('clan_request')]))
    def test_at_the_boundary_or_in_the_hunt_anything(self):
        quest=NS(mode='sub_quest')
        with t.boundary():self.assertEqual(t.pick(quest,[job('gear'),job('mail')]).key,'gear')
        self.assertFalse(t.long_ok(quest))
        self.assertEqual(t.pick(NS(mode='auto_mode'),[job('gear')]).key,'gear')


class Special(unittest.TestCase):
    def test_in_a_dungeon_raid_or_world_boss_only_short_jobs(self):
        import owner_schedule_priority as priority
        previous=getattr(priority.LOCAL,'combat',None);priority.LOCAL.combat='비경탐험'
        try:
            hunt=NS(mode='auto_mode')
            self.assertFalse(t.long_ok(hunt));self.assertEqual(t.pick(hunt,[job('gear'),job('mail')]).key,'mail')
            with t.boundary():self.assertFalse(t.long_ok(hunt))
        finally:priority.LOCAL.combat=previous
        self.assertTrue(t.long_ok(NS(mode='auto_mode')))


class Death(unittest.TestCase):
    def test_equip_and_growth_brought_forward(self):
        state={'gear_equip':{'status':'done'},'blessing_equip':{'status':'done'},'gear':{'status':'done'}}
        plan=NS(state=state,values={},commit=lambda:None)
        with patch('owner_timetable.planner',return_value=plan),patch('owner_timetable.enabled',return_value=True):
            moved=t.after_death(NS())
        self.assertEqual(len(moved),3)
        self.assertTrue(state['gear_equip']['equip_recheck']);self.assertTrue(state['gear']['growth_recheck'])
        self.assertEqual({v['status'] for v in state.values()},{'pending'})


class Arrows(unittest.TestCase):
    def test_green_arrow_pixels(self):
        real=np.zeros((768,1366,3),np.uint8);self.assertEqual(t.green_arrows(real),0)
        real[230:240,1170:1180]=(60,200,60);self.assertEqual(t.green_arrows(real),100)


class Rewards(unittest.TestCase):
    def test_disassembly_waits_on_the_way(self):
        self.assertIn('auto_register.equipment_disassembly.enabled',t.LONG_REWARDS)
        self.assertNotIn('auto_rewards.mail.enabled',t.LONG_REWARDS)



class Growing(unittest.TestCase):
    """Below level 40 only signalled bag and growth jobs run (user 11-06: like a person)."""
    def run_it(self,level,key,item):
        import owner_job_timing as t
        from types import SimpleNamespace as N
        with patch('owner_progression.state',return_value=N(level=level)):
            return t.allowed(N(),N(key=key),item)
    def test_growing_holds_timed_content(self):
        import time
        self.assertFalse(self.run_it(1,'daily_missions',{}))
        self.assertFalse(self.run_it(1,'gear',{}))
        self.assertTrue(self.run_it(1,'gear',{'signal_at':time.time()}))
        self.assertFalse(self.run_it(1,'gear',{'signal_at':time.time()-4000}))
    def test_grown_runs_as_before(self):
        self.assertTrue(self.run_it(40,'daily_missions',{}))
        self.assertTrue(self.run_it(None,'daily_missions',{}))


if __name__=='__main__':unittest.main()
