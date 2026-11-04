"""Raid entry count: real window for the count box, fakes for input. Never a game test."""
import sys,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_raid_tickets as t
import project_adapter.boss_raid as raid

F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))

class Game:
    """The real window, with the number box painted differently for each count."""
    def __init__(self,start=1,limit=10):
        self.count=start;self.limit=limit;self.presses=[];self.real=load('raid_admit')
        self.service=S(capture=self.frame,click_hit=self.hit)
    def frame(self):
        out=self.real.copy()
        if self.count!=1:
            x,y,w,h=t.COUNT_BOX;out[y:y+h,x:x+w]=(20,20,20);out[y+3:y+13,x+8:x+8+self.count*2]=(240,240,240)
        return out
    def hit(self,spot):
        x,y,_=spot;self.presses.append((x,y))
        if (x,y)==t.PLUS:self.count=min(self.limit,self.count+1)
        if (x,y)==t.MINUS:self.count=max(1,self.count-1)

def flow_for(game,value,tickets=5,root='r'):
    return S(adapter=S(values={t.COUNT_KEY:value},project=S(root=root)),context=S(checkpoint=lambda:None,wait=lambda s:None),
             service=game.service,_owner_ticket_read=(b'',tickets))

class SetCount(unittest.TestCase):
    def test_presses_up_to_the_wanted_count(self):
        game=Game();self.assertEqual(t.set_count(flow_for(game,'3회')),3);self.assertEqual(game.presses,[t.PLUS,t.PLUS]);self.assertEqual(game.count,3)
    def test_one_presses_nothing(self):
        game=Game();self.assertEqual(t.set_count(flow_for(game,'1회')),1);self.assertEqual(game.presses,[])
    def test_never_more_than_the_tickets_held(self):
        game=Game();self.assertEqual(t.set_count(flow_for(game,'10회',tickets=2)),2);self.assertEqual(game.count,2)
    def test_no_tickets_stays_one(self):
        game=Game();self.assertEqual(t.set_count(flow_for(game,'3회',tickets=0)),1);self.assertEqual(game.presses,[])
    def test_the_games_own_limit_is_what_is_reported(self):
        game=Game(limit=2);self.assertEqual(t.set_count(flow_for(game,'4회')),2);self.assertEqual(game.count,2)
    def test_a_start_that_is_not_one_spends_nothing(self):
        game=Game(start=5)
        with self.assertRaises(raid.RaidPending):t.set_count(flow_for(game,'3회'))
        self.assertEqual(game.presses,[])
    def test_the_real_window_shows_one(self):
        self.assertTrue(t.shows_one(load('raid_admit')));self.assertFalse(t.shows_one(Game(start=2).frame()))

class SelfCheck(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name);(self.root/'settings').mkdir()
    def test_without_the_marker_nothing_is_pressed(self):
        game=Game();self.assertEqual(t.set_count(flow_for(game,'1회',root=self.root)),1);self.assertEqual(game.presses,[])
    def test_the_marker_runs_once_and_ends_on_one(self):
        (self.root/t.CHECK_FILE).write_text('x');game=Game()
        self.assertEqual(t.set_count(flow_for(game,'1회',root=self.root)),1);self.assertEqual(game.count,1);self.assertEqual(len(game.presses),4)
        self.assertFalse((self.root/t.CHECK_FILE).exists())
        game=Game();t.set_count(flow_for(game,'1회',root=self.root));self.assertEqual(game.presses,[])
    def test_a_check_that_does_not_end_on_one_spends_nothing(self):
        (self.root/t.CHECK_FILE).write_text('x');game=Game();game.hit=lambda spot:setattr(game,'count',2);game.service.click_hit=game.hit
        with self.assertRaises(raid.RaidPending):t.set_count(flow_for(game,'1회',root=self.root))

class Choice(unittest.TestCase):
    def test_values(self):
        self.assertEqual(t.wanted({}),1);self.assertEqual(t.wanted({t.COUNT_KEY:'7회'}),7);self.assertEqual(t.wanted({t.COUNT_KEY:'이상'}),1)
        self.assertEqual(t.wanted({t.COUNT_KEY:'99회'}),10)
    def schema(self):
        return {'tabs':[{'groups':[{'fields':[{'id':'auto_schedule.boss_raid.reward_ticket','type':'combo','enabled_if':'x','choices':['1개씩']},{'id':'other'}]}]}]}
    def test_the_count_replaces_the_ticket_mode(self):
        fields=t.add_fields(self.schema())['tabs'][0]['groups'][0]['fields']
        self.assertEqual([f['id'] for f in fields],[t.COUNT_KEY,'other'])
        self.assertEqual(fields[0]['choices'][0],'1회');self.assertEqual(fields[0]['choices'][-1],'10회');self.assertNotIn('enabled_if',fields[0])
    def test_adding_twice_is_harmless(self):
        once=t.add_fields(self.schema());self.assertEqual(once,t.add_fields(once))

class Hook(unittest.TestCase):
    def call(self,bulk):
        t.install()
        flow=S(_owner_bulk=bulk)
        with patch.object(t,'set_count') as count:
            try:raid.RaidFlow.press(flow,raid.CONFIRM)
            except Exception:pass
        return count
    def test_the_count_is_set_before_confirm(self):self.call(False).assert_called_once()
    def test_an_old_saved_bulk_mode_is_ignored(self):
        t.install();seen=[]
        with patch.object(t,'set_count'),patch('owner_boss_range.loosen'),patch('owner_boss_range.restore'):
            flow=S(adapter=S(),context=S(stop=threading.Event()),inputs=None)
            original=raid.RaidFlow.run.__wrapped__
            try:
                raid.RaidFlow.run.__wrapped__=None
            except Exception:pass
            raid.RaidFlow.run.__wrapped__=original
            import inspect
            source=inspect.getsource(t.install)
        self.assertIn('fight(flow,stage,False)',source);self.assertIn('flow._owner_bulk=False',source)
    def test_a_test_run_enters_once_whatever_is_saved(self):
        game=Game();flow=flow_for(game,'5회');flow._owner_one_entry=True
        self.assertEqual(t.set_count(flow),1);self.assertEqual(game.presses,[])
    def test_other_buttons_are_left_alone(self):
        t.install()
        with patch.object(t,'set_count') as count:
            try:raid.RaidFlow.press(S(_owner_bulk=False),raid.MATCH)
            except Exception:pass
        count.assert_not_called()

class ResumedRaidDeath(unittest.TestCase):
    """Real death page from the 22:10 raid."""
    def adapter(self):
        return S(project=S(root=bootstrap.A,code='DKB'))
    def press(self,frame):
        import owner_startup_stage as stage
        clicks=[];service=S(click_hit=clicks.append);context=S(checkpoint=lambda:None,wait=lambda s:None)
        return stage.press_field_revive(service,context,self.adapter(),frame),clicks
    def test_the_revive_button_is_pressed(self):
        done,clicks=self.press(load('raid_dead'))
        self.assertTrue(done);self.assertEqual(len(clicks),1);self.assertEqual(clicks[0][:2],(448,453))
    def test_nothing_is_pressed_on_a_live_raid(self):
        done,clicks=self.press(load('raid_inside'))
        self.assertFalse(done);self.assertEqual(clicks,[])
    def test_the_macro_no_longer_needs_the_quest_handler_first(self):
        import inspect,owner_startup_stage as stage
        source=inspect.getsource(stage._resume_dungeon)
        self.assertLess(source.index('press_field_revive'),source.index('handle_death'))

if __name__=='__main__':unittest.main()
