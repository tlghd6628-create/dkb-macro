"""가호 소환 by the 1회/10회 ticks. Fake screens and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_blessing_summon as s


class Plan(unittest.TestCase):
    def test_the_ticks(self):
        self.assertEqual(s.plan(34,True,True),(3,4))     # 10회 ×3, the 4 left one by one
        self.assertEqual(s.plan(34,False,True),(3,0))    # only 10회: 4 wait for more
        self.assertEqual(s.plan(34,True,False),(0,34))   # only 1회: all one by one
        self.assertEqual(s.plan(7,False,True),(0,0));self.assertEqual(s.plan(0,True,True),(0,0))
        self.assertEqual(s.plan(None,True,True),(0,0))


class Game:
    """A summon tab whose count falls by each press's cost, or not when told to stick."""
    def __init__(self,count,stick=False):self.count=count;self.stick=stick;self.pressed=[]
    def rows(self,box):
        if box==s.COUNT:return [dict(text=str(self.count),score=.99,rx=719,ry=674)]
        return [dict(text=w,score=.99,rx=x,ry=720) for w,x in (('1회',559),('10회',741),('나가기',865))]


def running(game,choice):
    frame=NS(hi=np.zeros((768,1366,3),np.uint8))
    clicks=[]
    def click(hit):
        x=hit[0];clicks.append(x)
        for word,place in (('1회',559),('10회',741)):
            import owner_hd as hd
            if hit[:2]==hd.real_hit(place,720)[:2] and not game.stick:game.count-=s.COSTS[word];game.pressed.append(word)
    service=NS(capture=lambda:frame,check=lambda:None,click_hit=click)
    def read_area(_,area,left=0,top=0,**k):
        for box in (s.COUNT,s.BUTTONS):
            if area.shape[:2]==(box[3],box[2]):return game.rows(box)
        return []
    context=NS(checkpoint=lambda:None,wait=lambda t:None)
    with patch('project_adapter.town_services.TownServices',lambda *a:service),patch('owner_text.read_area',read_area),\
         patch.object(s.worn,'open_blessing_screen',return_value=True),patch.object(s.worn,'leave_blessing_screen'):
        return s.run(NS(project=NS(root='x')),context,NS(),choice)


class Run(unittest.TestCase):
    def test_tens_then_ones(self):
        game=Game(23);result=running(game,{'one':True,'ten':True})
        self.assertEqual(game.pressed,['10회','10회','1회','1회','1회']);self.assertIn('남은 소환권 0',result)
    def test_only_ten_keeps_the_rest(self):
        game=Game(23);running(game,{'one':False,'ten':True})
        self.assertEqual(game.pressed,['10회','10회']);self.assertEqual(game.count,3)
    def test_a_press_that_takes_nothing_stops(self):
        game=Game(23,stick=True);result=running(game,{'one':True,'ten':True})
        self.assertIn('10회 0번',result)
    def test_nothing_ticked_does_nothing(self):
        self.assertIn('선택 없음',running(Game(23),{'one':False,'ten':False}))


class Wiring(unittest.TestCase):
    def test_settings_and_timetable(self):
        import owner_timetable as t
        from owner_gear_settings_candidate import DEFAULT,validate
        import copy
        self.assertEqual(DEFAULT['blessing_summon'],{'one':False,'ten':False})
        bad=copy.deepcopy(DEFAULT);bad['blessing_summon']['ten']='yes'
        with self.assertRaisesRegex(ValueError,'가호 소환'):validate(bad)
        job=t.BY_KEY['blessing_summon'];self.assertTrue(t.enabled(job,{s.KEY:True}));self.assertFalse(t.enabled(job,{}))
        with patch('owner_blessing_summon.run',return_value='가호 소환 10회 1번 · 1회 0번 · 남은 소환권 3') as run:
            self.assertTrue(t.invoke(NS(),job,NS(),NS()))
        run.assert_called_once()
    def test_its_test_button(self):
        import owner_challenge_test as c
        with patch('owner_blessing_summon.run',return_value='가호 소환 10회 0번 · 1회 0번 · 남은 소환권 0') as run:
            self.assertIn('가호 소환',c.execute(NS(values={}),NS(),NS(),s.KEY))
        run.assert_called_once()


if __name__=='__main__':unittest.main()
