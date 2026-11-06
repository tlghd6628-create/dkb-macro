"""F1 goes straight to the hunt when a full check just found nothing at this power. Fake book; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
import sys,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_mission_controller as m


class Recent(unittest.TestCase):
    def book(self,ago,power):return NS(item={'nothing_runnable':{'at':time.time()-ago,'power':power}})
    def start(self):adapter=NS(_owner_nothing_run=object());return adapter
    def test_once_per_start_within_the_window_at_no_more_power(self):
        adapter=self.start()
        self.assertTrue(m.recent_nothing(adapter,self.book(60,168043),168043))
        self.assertFalse(m.recent_nothing(adapter,self.book(60,168043),168043))   # the hunt's later rechecks read the lists
        adapter._owner_nothing_run=object()
        self.assertTrue(m.recent_nothing(adapter,self.book(60,168043),168043))
    def test_old_more_power_or_no_record_reads_the_lists(self):
        self.assertFalse(m.recent_nothing(self.start(),self.book(m.NOTHING_SECONDS+5,168043),168043))
        self.assertFalse(m.recent_nothing(self.start(),self.book(60,168043),170000))
        self.assertFalse(m.recent_nothing(self.start(),NS(item={}),168043))


if __name__=='__main__':unittest.main()
