"""제자리 ON·5m comes back only once the hunt is at its spot. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_hunt as h


class AtSpot(unittest.TestCase):
    def run_it(self,mode='auto_mode',pending=True,restored=True,temporary=None):
        calls=[]
        adapter=NS(mode=mode,project=NS(root='r'),_owner_temporary_work=temporary)
        def restore(*a):calls.append('restore');return restored
        def auto(*a,**k):calls.append('auto');return True
        with patch('owner_boss_range.pending',return_value={'fixed':True} if pending else None),patch('owner_boss_range.restore',restore),\
             patch('project_adapter.town_services.TownServices',lambda *a:NS(actions=None)),\
             patch('project_adapter.favorite_hunt.ensure_auto_active',auto):
            return h.at_spot(adapter,NS(),NS()),calls
    def test_restores_then_makes_sure_of_auto(self):
        self.assertEqual(self.run_it(),(True,['restore','auto']))
    def test_nothing_open_sends_nothing(self):
        self.assertEqual(self.run_it(pending=False),(False,[]))
    def test_quest_modes_and_side_work_leave_it_open(self):
        self.assertEqual(self.run_it(mode='main_quest'),(False,[]))
        self.assertEqual(self.run_it(temporary='shop'),(False,[]))
    def test_a_failed_restore_starts_nothing_more(self):
        self.assertEqual(self.run_it(restored=False),(False,['restore']))


class Sites(unittest.TestCase):
    def test_no_restore_where_the_boss_raid_or_start_left_the_character(self):
        here=Path(__file__).resolve().parent
        for name in ('owner_boss_gate.py','owner_raid_tickets.py','owner_startup_stage.py'):
            self.assertNotIn('restore(',(here/name).read_text(encoding='utf-8'),name)


class Narrow(unittest.TestCase):
    """Range 5m before the trip, the hold left off: only at_spot turns it on."""
    def run_it(self,saved,panel=True):
        import owner_boss_range as b
        applied=[];adapter=NS(project=NS(root=Path('.')),exit_sleep_mode=lambda c,i:None)
        ui=NS(frame=lambda:'F')
        with patch.object(b,'pending',return_value=saved),patch.object(b,'_ui',return_value=ui),             patch.object(b,'panel_open',return_value=panel),patch.object(b,'cog',return_value=None),             patch.object(b,'apply',side_effect=lambda u,fixed,slider,**k:applied.append((fixed,slider))),             patch.object(b,'_clear',side_effect=AssertionError('stays recorded')):
            return b.narrow(adapter,NS(checkpoint=lambda:None),NS()),applied
    def test_range_only(self):
        self.assertEqual(self.run_it({'fixed':True,'range':'low'}),(True,[(False,'low')]))
    def test_nothing_open_sends_nothing(self):
        self.assertEqual(self.run_it(None),(False,[]))
    def test_not_on_the_base_screen_waits(self):
        self.assertEqual(self.run_it({'fixed':True},panel=False),(False,[]))


if __name__=='__main__':unittest.main()
