"""Top-bar red dots bring growth forward. Synthetic pixels and fake stores; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_growth_signals as g


def frame(*names):
    hi=np.zeros((768,1366,3),np.uint8)
    for name in names:x=g.DOTS[name];hi[g.DOT_Y-2:g.DOT_Y+2,x-2:x+2]=(230,40,40)
    return NS(hi=hi)


class Dots(unittest.TestCase):
    def test_reads_each_icon(self):
        self.assertEqual(g.dots(frame('bag','event').hi),{'bag','event'})
        self.assertEqual(g.dots(frame().hi),set())


class Look(unittest.TestCase):
    def test_bag_dot_brings_jobs_once_then_mutes(self):
        adapter=NS(values={});calls=[]
        with patch.object(g,'bring_bag',side_effect=lambda a:calls.append('bag') or ['인벤토리 사용']),patch.object(g.time,'monotonic',side_effect=[1000,1100,1200+g.MUTE]):
            self.assertEqual(g.look(adapter,frame('bag')),['인벤토리 사용'])
            self.assertEqual(g.look(adapter,frame('bag')),[])
            self.assertEqual(g.look(adapter,frame('bag')),['인벤토리 사용'])
        self.assertEqual(calls,['bag','bag'])
    def test_looks_at_most_every_minute(self):
        adapter=NS(values={});calls=[]
        with patch.object(g,'bring_bag',side_effect=lambda a:calls.append('bag') or []),patch.object(g.time,'monotonic',side_effect=[1000,1030]):
            g.look(adapter,frame('bag'));g.look(adapter,frame('bag'))
        self.assertEqual(calls,['bag'])
    def test_reward_off_moves_nothing(self):
        self.assertEqual(g.bring_reward(NS(values={g.REWARD_KEYS['mail']:False}),'mail'),[])


if __name__=='__main__':unittest.main()
