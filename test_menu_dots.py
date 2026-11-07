"""Full-menu red dots on the saved 1366 menu frame and fake timetable. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_growth_signals as gs

MENU=Path(__file__).resolve().parent/'image_scope_20261104/f1/menu_hd.png'   # 짱군네 11-07 08:46, not in the repo

class Tiles(unittest.TestCase):
    @unittest.skipUnless(MENU.exists(),'saved menu frame not on this PC')
    def test_dotted_tiles_on_the_real_menu(self):
        import numpy as np,owner_text
        from PIL import Image
        owner_text.set_root(bootstrap.A)
        a=np.asarray(Image.open(MENU).convert('RGB'));x,y,w,h=gs.MENU_AREA
        tiles=gs.dotted_tiles(a,owner_text.read_area(None,a[y:y+h,x:x+w],left=x,top=y,minimum=.5))
        self.assertTrue({'단봉인해제','도술','기운발현','업적','화첩'}<=tiles,tiles)
        self.assertNotIn('성장',tiles)

class Jobs(unittest.TestCase):
    def test_only_switched_on_jobs_come_forward(self):
        state={'seal_release':{'status':'done'},'growth':{'status':'done'},'album':{'status':'done'}}
        plan=S(state=state,values={},commit=lambda:None)
        with patch('owner_timetable.planner',return_value=plan),patch('owner_timetable.enabled',side_effect=lambda job,values:job.key!='album'):
            moved=gs.bring_jobs(S(),['seal_release','growth','album','growth'])
        self.assertEqual(state['seal_release']['status'],'pending');self.assertEqual(state['growth']['status'],'pending')
        self.assertEqual(state['album']['status'],'done');self.assertEqual(len(moved),2)

class Rearm(unittest.TestCase):
    """User 11-07: every dot at once. A dot that goes out and comes back is new; one that stays waits its mute."""
    def frame(self,menu=False,bag=False):
        import numpy as np
        a=np.zeros((768,1366,3),np.uint8)
        if menu:a[10:19,gs.MENU_DOT_X-4:gs.MENU_DOT_X+5]=(230,30,30)
        if bag:a[10:19,gs.DOTS['bag']-4:gs.DOTS['bag']+5]=(230,30,30)
        return a
    def test_menu_dot_rearms_when_it_goes_out(self):
        ad=S(_owner_signal_muted={'menu':1e18})
        self.assertEqual(gs.menu_dots(ad,None,None,self.frame(menu=True)),[])   # muted, still on
        gs.menu_dots(ad,None,None,self.frame(menu=False))                       # went out
        self.assertNotIn('menu',ad._owner_signal_muted)
    def test_top_dot_rearms_when_it_goes_out(self):
        ad=S(_owner_signal_muted={'bag':1e18},_owner_signal_look=-1e9)
        with patch.object(gs,'bring_bag',side_effect=AssertionError('muted')):gs.look(ad,S(hi=self.frame(bag=True)))
        ad._owner_signal_look=-1e9;gs.look(ad,S(hi=self.frame()))
        self.assertNotIn('bag',ad._owner_signal_muted)
        ad._owner_signal_look=-1e9
        with patch.object(gs,'bring_bag',return_value=['가방 작업']) as bag:gs.look(ad,S(hi=self.frame(bag=True)))
        bag.assert_called_once()

class QuestWalk(unittest.TestCase):
    def test_quest_walk_looks_every_twenty_seconds(self):
        import owner_mission_controller as mc
        ad=S();ctx=S(input_depth=0);inp=S(held=())
        with patch('owner_hunt_memory.signals',return_value=['x']) as sig:
            self.assertEqual(mc.quest_signals(ad,ctx,inp),['x'])
            self.assertEqual(mc.quest_signals(ad,ctx,inp),[])
            ad._owner_quest_signal_at-=gs.QUEST_LOOK_EVERY
            mc.quest_signals(ad,ctx,inp)
        self.assertEqual(sig.call_count,2)
    def test_no_look_during_input(self):
        import owner_mission_controller as mc
        with patch('owner_hunt_memory.signals',side_effect=AssertionError('input')):
            mc.quest_signals(S(),S(input_depth=1),S(held=()))

if __name__=='__main__':unittest.main()
