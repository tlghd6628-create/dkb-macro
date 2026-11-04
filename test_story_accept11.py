"""Story acceptance results. Fake UI and one saved game frame; no game input."""
import bootstrap
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
import owner_story_groups as story
from owner_skill_goal import Pending


class Fake:
    def __init__(self):
        self.clicks=[];self.opened=[]
        self.context=S(wait=lambda n:None,checkpoint=lambda:None)
    def frame(self):return np.zeros((479,897,3),np.uint8)
    def click(self,x,y,proof):self.clicks.append((x,y))
    def open(self,name):self.opened.append(name)
    def rows(self,*a,**k):return []


class Accept(unittest.TestCase):
    def groups(self):
        book=S(item={'quests':{'k':{'title':'[외전] 시험'}}},commit=lambda:None)
        ui=Fake();return story.Groups(ui,book,100),ui,book
    def run_accept(self,counts,*,button):
        """`button` is whether the accept button remains after the click."""
        g,ui,book=self.groups();seen=iter(counts);finds=iter([True,True]+[button]*20)
        def find(frame,name,box,threshold=.94,bright=True):
            return (790,450,(700,430,880,474),.99) if name=='accept-button' and next(finds) else None
        with patch.object(story,'find',find),patch.object(story,'quest_screen',return_value=True),patch.object(story,'selected_quest_box',return_value=(1,1,1,1)),\
             patch.object(story,'quota',side_effect=lambda ui:next(seen)),patch.object(g,'select',return_value=True),patch.object(g,'locate',return_value=None),patch.object(g,'compact'):
            return g.accept('k',12),ui,book
    def test_counter_rise_is_accepted_even_if_row_marks_lag(self):
        result,ui,book=self.run_accept([13],button=False)
        self.assertTrue(result);self.assertTrue(book.item['quests']['k']['accepted']);self.assertEqual(len(ui.clicks),1)
    def test_stale_footer_reopens_the_tab_once_and_never_clicks_again(self):
        result,ui,book=self.run_accept([12]*5+[13],button=False)
        self.assertTrue(result);self.assertEqual(ui.opened,['main_quest','sub_quest']);self.assertEqual(len(ui.clicks),1)
    def test_unread_footer_also_reopens(self):
        result,ui,_=self.run_accept([None]*5+[13],button=False)
        self.assertTrue(result);self.assertEqual(len(ui.clicks),1)
    def test_click_that_did_not_land_is_not_an_error(self):
        result,ui,book=self.run_accept([12]*5,button=True)
        self.assertFalse(result);self.assertNotIn('accepted',book.item['quests']['k']);self.assertEqual(len(ui.clicks),1);self.assertEqual(ui.opened,[])
    def test_count_still_unchanged_after_reopen_stays_pending(self):
        with self.assertRaises(Pending):self.run_accept([12]*6,button=False)
    def test_unexpected_jump_is_not_counted_as_this_acceptance(self):
        with self.assertRaises(Pending):self.run_accept([15],button=False)


class Scan(unittest.TestCase):
    def test_footer_covered_for_a_moment_is_retried(self):
        book=S(item={'quests':{},'batch':{'keys':[]}},commit=lambda:None);g=story.Groups(Fake(),book,100)
        with patch.object(story,'quota',side_effect=[None,None,20]),patch.object(g,'compact'),patch.object(story,'group_rows',return_value=[]):
            self.assertEqual(g.scan(fill=True)[1],20)
    def test_footer_never_readable_stays_pending(self):
        g=story.Groups(Fake(),S(item={'quests':{},'batch':{}},commit=lambda:None),100)
        with patch.object(story,'quota',return_value=None),patch.object(g,'compact'),self.assertRaises(Pending):g.scan()
    def test_unreadable_title_is_skipped_and_marks_scan_incomplete(self):
        book=S(item={'quests':{},'batch':{}},commit=lambda:None);g=story.Groups(Fake(),book,100)
        calls=iter([[{'y':150,'open':False}]])
        with patch.object(story,'quota',return_value=3),patch.object(g,'compact'),patch.object(g,'top'),patch.object(g,'identify',side_effect=Pending('제목')),\
             patch.object(story,'group_rows',side_effect=lambda f:next(calls,[])),patch.object(story,'completed_root',return_value=False),patch.object(g.ui,'wheel',create=True),patch.object(g.ui,'drag',create=True):
            g.scan(fill=True)
        self.assertFalse(book.item['batch']['scan_complete'])
    def test_choose_treats_unreadable_title_as_uncertain_not_finished(self):
        g=story.Groups(Fake(),S(item={'quests':{}},commit=lambda:None),100)
        with patch.object(g,'compact'),patch.object(story,'group_rows',return_value=[{'y':150,'open':False}]),patch.object(story,'completed_root',return_value=False),\
             patch.object(story,'dots',return_value=True),patch.object(story,'suitable',return_value=True),patch.object(g,'identify',side_effect=Pending('제목')),self.assertRaises(story.StorySelectionPending):
            g.choose([])


class TopFirst(unittest.TestCase):
    """Rows are (key, suitable, accepted, blocked) from top to bottom."""
    def run_choose(self,rows,actual,*,accept=None):
        state={key:{'suitable':s,'accepted':a,'blocked':b} for key,s,a,b in rows}
        order=[key for key,*_ in rows];log=[]
        ys={key:120+40*i for i,key in enumerate(order)};by_y={y:key for key,y in ys.items()}
        book=S(item={'quests':{key:{'title':key} for key in order}},commit=lambda:None,blocked=lambda key,power:state[key]['blocked'])
        g=story.Groups(Fake(),book,100);g.actual=actual
        g.ui.wheel=lambda *a:log.append('wheel')
        def do_accept(key,before):
            log.append(('accept',key,before))
            result=True if accept is None else accept(key)
            if result:state[key]['accepted']=True
            return result
        with patch.object(story,'group_rows',return_value=[{'y':y,'open':False} for y in by_y]),patch.object(story,'completed_root',return_value=False),\
             patch.object(story,'suitable',side_effect=lambda f,y:state[by_y[y]]['suitable']),patch.object(story,'dots',side_effect=lambda f,y:state[by_y[y]]['accepted']),\
             patch.object(story,'group_eligible',side_effect=lambda b,key,p:not state[key]['blocked']),patch.object(story,'same_verified_root_blocked',return_value=False),\
             patch.object(story,'locate_backoff',return_value=False),patch.object(g,'identify',side_effect=lambda f,row:by_y[row['y']]),patch.object(g,'compact'),\
             patch.object(g,'accept',side_effect=do_accept),patch.object(g,'select',side_effect=lambda key:log.append(('select',key)) or True),\
             patch.object(g,'activate',side_effect=lambda key:log.append(('activate',key))):
            return g.choose(order),log,g
    def test_top_suitable_is_accepted_and_started_before_older_accepted(self):
        result,log,g=self.run_choose([('new',True,False,False),('old',True,True,False)],13)
        self.assertEqual(result,'new');self.assertEqual(log[0],('accept','new',13));self.assertEqual(g.actual,14)
        self.assertNotIn(('select','old'),log)
    def test_top_accepted_runs_without_new_accept(self):
        result,log,_=self.run_choose([('old',True,True,False),('new',True,False,False)],13)
        self.assertEqual(result,'old');self.assertFalse([x for x in log if x[0]=='accept'])
    def test_unsuitable_top_is_never_accepted(self):
        result,log,_=self.run_choose([('hard',False,False,False),('next',True,False,False)],13)
        self.assertEqual(result,'next');self.assertNotIn(('accept','hard',13),log)
    def test_blocked_top_is_skipped(self):
        result,log,_=self.run_choose([('dead',True,False,True),('next',True,True,False)],13)
        self.assertEqual(result,'next');self.assertFalse([x for x in log if x[0]=='accept'])
    def test_at_the_limit_only_accepted_quests_can_start(self):
        result,log,_=self.run_choose([('new',True,False,False),('old',True,True,False)],20)
        self.assertEqual(result,'old');self.assertFalse([x for x in log if x[0]=='accept'])
    def test_failed_acceptance_moves_on_without_repeating(self):
        result,log,_=self.run_choose([('bad',True,False,False),('next',True,True,False)],13,accept=lambda key:False)
        self.assertEqual(result,'next');self.assertEqual(log.count(('accept','bad',13)),1)
    def test_uncertain_click_still_stops_without_second_click(self):
        def boom(key):raise Pending('개수')
        g_result=None
        with self.assertRaises(Pending):
            # accept_clicked stays True for this fake through its class default.
            with patch.object(story.Groups,'accept_clicked',True,create=True):
                self.run_choose([('new',True,False,False)],13,accept=boom)
    def test_pick_always_starts_selection_at_the_top(self):
        book=S(item={'story_catalog_version':'groups-v2','batch':{'keys':['k']},'quests':{}},commit=lambda:None,batch_needs_fill=lambda power:False)
        ui=Fake();calls=[]
        with patch.object(story.Groups,'scan',lambda self,fill=True:(['k'],13)),patch.object(story.Groups,'top',lambda self:calls.append('top')),patch.object(story.Groups,'choose',lambda self,keys,prefer_saved=False:calls.append(('choose',self.actual)) or 'k'):
            self.assertEqual(story.pick(ui,book,100),'k')
        self.assertEqual(calls,['top',('choose',13)])


class SavedFrame(unittest.TestCase):
    def test_actual_stale_footer_screen_shows_button_gone(self):
        path=bootstrap.A/'logs/quest-incidents/20261101T213248Z-b3d66a66/screen.png'
        frame=np.asarray(Image.open(path).convert('RGB')).copy()
        self.assertIsNone(story.find(frame,'accept-button',(700,430,180,44),.94))


if __name__=='__main__':unittest.main()
