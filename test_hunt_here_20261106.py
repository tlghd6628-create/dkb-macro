"""No teleport when already at the saved hunting spot. Fake reads and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_hunt_here as h


class Distance(unittest.TestCase):
    def run_it(self,shown):
        clicks=[];keys=[];state={'map':False}
        def key(k):keys.append(k);state['map']=True
        def click(hit):
            clicks.append(hit[:2])
            if hit[:2]==h.hd.real_hit(*h.CLOSE)[:2]:state['map']=False
        service=NS(check=lambda:None,key=key,click_hit=click,capture=lambda:NS(hi=1))
        with patch.object(h,'map_open',side_effect=lambda f:state['map']),patch.object(h,'words',return_value=shown):
            got=h.distance(service,NS(wait=lambda s:None),2)
        return got,clicks,state
    def test_reads_metres_and_closes_the_map(self):
        got,clicks,state=self.run_it(['Om'])
        self.assertEqual(got,0);self.assertFalse(state['map'])
        self.assertIn(h.hd.real_hit(h.ROW_X,h.ROW_Y0+h.ROW_STEP)[:2],clicks)
        self.assertEqual(self.run_it(['64m'])[0],64)
        self.assertIsNone(self.run_it([])[0])
    def test_drifted_spot_is_walked_back(self):
        """pc2 홍짱군 slot 3, 11-07 07:17: 9m off against the cave wall, accepted as already there."""
        clicks=[];state={'map':False}
        def key(k):state['map']=True
        def click(hit):
            clicks.append(hit[:2])
            if hit[:2]==h.hd.real_hit(*h.CLOSE)[:2]:state['map']=False
        service=NS(check=lambda:None,key=key,click_hit=click,capture=lambda:NS(hi=1))
        walk=[{'text':'걸어가기','rx':1250,'ry':685,'score':.99}]
        with patch.object(h,'map_open',side_effect=lambda f:state['map']),patch.object(h,'words',return_value=['9m']),             patch.object(h.text,'read',return_value=walk):
            self.assertEqual(h.distance(service,NS(wait=lambda s:None),3,walk=True),9)
            self.assertIn(h.hd.real_hit(1250,685)[:2],clicks)
            clicks.clear();h.distance(service,NS(wait=lambda s:None),3,walk=False)
            self.assertNotIn(h.hd.real_hit(1250,685)[:2],clicks)
        with patch.object(h,'map_open',side_effect=lambda f:state['map']),patch.object(h,'words',return_value=['4m']),             patch.object(h.text,'read',return_value=walk):
            clicks.clear();h.distance(service,NS(wait=lambda s:None),3,walk=True)
            self.assertNotIn(h.hd.real_hit(1250,685)[:2],clicks)
    def test_slot_from_the_route(self):
        self.assertEqual(h.slot_number(NS(values={'common.potion_and_favorite.slot':'2번','common.potion_and_favorite.source':'저장위치'})),2)
        self.assertIsNone(h.slot_number(NS(values={'common.potion_and_favorite.slot':'2번','common.potion_and_favorite.source':'즐겨찾기'})))


class Here(unittest.TestCase):
    def run_it(self,metres,auto=True):
        adapter=NS(values={'common.potion_and_favorite.slot':'2번','common.potion_and_favorite.source':'저장위치'})
        service=NS(capture=lambda:NS(hi=1),actions=None)
        with patch('project_adapter.town_services.TownServices',lambda *a:service),patch('owner_town_return.town_pair',return_value=False),\
             patch.object(h,'distance',return_value=metres),patch('project_adapter.favorite_hunt.ensure_auto_active',return_value=auto):
            return h.already_there(adapter,NS(),NS())
    def test_near_skips_far_or_unread_moves(self):
        self.assertTrue(self.run_it(0));self.assertTrue(self.run_it(5))
        # pc2 11-07 08:58: 10m off is moved back by 축지술, not walked.
        self.assertFalse(self.run_it(10));self.assertFalse(self.run_it(15))
        self.assertFalse(self.run_it(40));self.assertFalse(self.run_it(None));self.assertFalse(self.run_it(0,auto=False))



class StillHunting(unittest.TestCase):
    def run_it(self,age,pending=None,lit=(True,True)):
        import time
        adapter=NS(project=NS(root='r'),_owner_at_spot=time.monotonic()-age);looks=list(lit)
        service=NS(capture=lambda:NS(hi=1))
        with patch('owner_boss_range.pending',return_value=pending),patch.object(h,'auto_lit',side_effect=lambda f:looks.pop(0)):
            return h.still_hunting(adapter,NS(wait=lambda s:None),service)
    def test_recent_spot_with_auto_lit_skips_the_map(self):
        self.assertTrue(self.run_it(60))
    def test_old_proof_open_boss_range_or_auto_off_reads_the_map(self):
        self.assertFalse(self.run_it(601))
        self.assertFalse(self.run_it(60,pending={'fixed':True}))
        self.assertFalse(self.run_it(60,lit=(True,False)))
        self.assertFalse(self.run_it(60,lit=(False,)))
    def test_never_seen(self):
        self.assertFalse(h.still_hunting(NS(project=NS(root='r')),NS(wait=lambda s:None),NS(capture=lambda:NS(hi=1))))

if __name__=='__main__':unittest.main()
