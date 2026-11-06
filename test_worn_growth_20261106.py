"""Growth by way of the bag: what the details say decides what is pressed. Fake input and rows; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_worn_growth as g
from owner_gear_decision_candidate import Observation
from owner_gear_settings_candidate import Store


def row(text,x=0,y=0,score=.95,wide=40):return dict(text=text,score=score,rx=x,ry=y,x=round(x/1.6),y=round(y/1.6),bounds=(x-wide//2,y-9,x+wide//2,y+9))


def frame(gold=True):
    big=np.zeros((768,1366,3),np.uint8)
    big[700:742,560:795]=(253,230,148) if gold else (125,114,71)
    return NS(hi=big)


class Zones:
    def __init__(self,level=20,next_level=21,word='강화',cost='6,000',count='97/6',title='토끼 가호 장식2'):
        self.level,self.next,self.word,self.cost,self.count,self.title=level,next_level,word,cost,count,title
    def read(self,root,frame,box,**options):
        if box==g.BLESSING_TITLE:return [row(self.title,560,118)] if self.title else []
        if box==g.BLESSING_LEVEL:return [row(str(self.level),570,218)]
        if box==g.BLESSING_NEXT:return [row(str(self.next),625,218)] if self.next is not None else []
        if box==g.BLESSING_COUNT:return [row(self.count,594,645)] if self.count else []
        if box in (g.BLESSING_PILL,g.ACTION_PILL):return [row(self.word,730,720),row(self.cost,626,720)] if self.word else []
        raise AssertionError(box)


class FontPair(unittest.TestCase):
    def pair(self,a,b):return g.font_pair([row(a)],[row(b)])
    def test_the_right_side(self):self.assertEqual(self.pair('40','47+'),(40,41))
    def test_the_left_side(self):self.assertEqual(self.pair('47','42'),(41,42))
    def test_seven_that_are_really_seven(self):self.assertEqual(self.pair('47','48'),(47,48))
    def test_nothing_fits(self):self.assertIsNone(self.pair('40','45'))
    def test_the_plus_lowers_the_score_of_the_next_level(self):
        self.assertEqual(g.font_pair([row('41')],[row('42 +',score=.6)]),(41,42))
        self.assertIsNone(g.font_pair([row('41')],[row('42 +',score=.3)]))
    def test_two_ways_is_none(self):self.assertIsNone(g.font_pair([row('7')],[row('8'),row('2')]))
    def test_unread_is_none(self):self.assertIsNone(g.font_pair([],[row('41')]))


class Panel(unittest.TestCase):
    def read(self,zones,gold=True):
        with patch('owner_text.read',zones.read):return g.read_panel(None,frame(gold))
    def test_ready_step(self):
        panel=self.read(Zones())
        self.assertTrue(panel['active']);self.assertEqual((panel['level'],panel['next'],panel['cost']),(20,21,6000))
    def test_a_short_count_is_not_ready(self):self.assertFalse(self.read(Zones(count='3/6'))['active'])
    def test_a_dim_button_is_not_ready(self):self.assertFalse(self.read(Zones(),gold=False)['active'])
    def test_short_coins_stay_ready_so_the_message_can_answer(self):
        # The button stays lit and the price red when only coins are short (11-05).
        self.assertTrue(self.read(Zones(cost='75,000'))['active'])
    def test_opening_needs_no_count_unless_it_is_short(self):
        self.assertTrue(self.read(Zones(word='개방',count=''))['active'])
        self.assertFalse(self.read(Zones(word='개방',count='0/1'))['active'])
    def test_at_the_top_there_is_no_next_step(self):
        panel=self.read(Zones(level=50,next_level=None,word=None,cost='',count=''))
        self.assertFalse(panel['active'])
    def test_no_title_is_no_panel(self):self.assertIsNone(self.read(Zones(title='')))


class Action(unittest.TestCase):
    def read(self,zones,word,gold=True):
        with patch('owner_text.read',zones.read):return g.read_action(None,frame(gold),word)
    def test_ready(self):
        self.assertTrue(self.read(Zones(word='각성',cost='5,000',count='1/1'),'각성')['active'])
    def test_no_spare_is_not_ready_and_says_so(self):
        action=self.read(Zones(word='각성',cost='5,000',count='0/1'),'각성')
        self.assertFalse(action['active']);self.assertIs(action['enough'],False)
    def test_an_empty_panel_is_none(self):
        self.assertIsNone(self.read(Zones(title='',word='돌파',cost='20,000'),'돌파'))
    def test_another_word_on_the_button_is_none(self):
        self.assertIsNone(self.read(Zones(word='강화'),'각성'))


class WithRoute(unittest.TestCase):
    DOCUMENT={'grades':{'희귀':{'enabled':True,'enhance':50,'breakthrough':3,'awaken':1},'일반':{'enabled':True,'enhance':50,'breakthrough':3,'awaken':1},'영웅':{'enabled':False,'enhance':49,'breakthrough':0,'awaken':0}},
              'blessings':{'1번':{'enabled':True,'enhance':49,'breakthrough':0},'2번':{'enabled':False,'enhance':49,'breakthrough':0}}}
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        self.clicks=[]
        self.adapter=NS(project=NS(root=Path(self.dir.name)),values={})
        # A real wait: the guard wants two looks at two different times.
        self.context=NS(checkpoint=lambda:None,wait=lambda s:time.sleep(.02))
        self.service=NS(adapter=self.adapter,check=lambda:None,capture=lambda:frame(),click_hit=lambda hit:self.clicks.append(hit),context=self.context)
        self.route=g.Route(self.adapter,self.context,None,self.service,'identity','identity','c',self.DOCUMENT)
    def item(self,values,grade='희귀',slot='무기',blessing=False):
        item=g.Item(slot,blessing);item.values=values;item.grade=grade;return item


class Need(WithRoute):
    def test_in_order(self):
        self.assertEqual(self.route.need(self.item({'enhance':30,'breakthrough':0,'awaken':0})),g.ENHANCE)
        self.assertEqual(self.route.need(self.item({'enhance':50,'breakthrough':2,'awaken':0})),g.BREAK)
        self.assertEqual(self.route.need(self.item({'enhance':50,'breakthrough':3,'awaken':0})),g.AWAKEN)
    def test_at_goal_is_nothing(self):
        self.assertIsNone(self.route.need(self.item({'enhance':50,'breakthrough':3,'awaken':1})))
    def test_a_grade_switched_off_is_nothing(self):
        self.assertIsNone(self.route.need(self.item({'enhance':0,'awaken':0},grade='영웅')))
    def test_what_failed_this_visit_is_passed_over(self):
        item=self.item({'enhance':30,'breakthrough':0,'awaken':0});item.done.add(g.ENHANCE)
        self.assertEqual(self.route.need(item),g.BREAK)
    def test_a_row_the_item_does_not_have_is_passed_over(self):
        self.assertEqual(self.route.need(self.item({'enhance':50,'awaken':0})),g.AWAKEN)
    def test_a_blessing_only_enhances_by_its_slot(self):
        self.assertEqual(self.route.need(self.item({'enhance':39,'opening':3,'awaken':0},slot='가호1',blessing=True)),g.ENHANCE)
        self.assertIsNone(self.route.need(self.item({'enhance':49,'opening':3,'awaken':0},slot='가호1',blessing=True)))
        self.assertIsNone(self.route.need(self.item({'enhance':1,'opening':0,'awaken':0},slot='가호2',blessing=True)))
    def test_breakthrough_off_is_passed_over(self):
        with patch.object(g,'breakthrough_allowed',return_value=False):
            self.assertEqual(self.route.need(self.item({'enhance':50,'breakthrough':0,'awaken':0})),g.AWAKEN)


class Settle(WithRoute):
    def sent(self,kind,before=3,slot='worn:무기'):
        fields=dict(enhancement=None,breakthrough=None,awakening=None);fields[{'enhance':'enhancement','breakthrough':'breakthrough','awaken':'awakening'}[kind]]=before
        seen=Observation(1,time.monotonic(),'identity','worn-slot:무기',slot,'희귀',fields['enhancement'],fields['breakthrough'],fields['awakening'],None,None,None)
        self.route.intents.begin({'kind':kind,'before':seen,'second':seen,'cost':None,'balance':None,'item_icon':None});self.route.intents.mark_sent()
    def last(self):return self.route.intents._read().get('last_result')
    def test_a_rise_is_progress(self):
        self.sent('enhance');self.route.settle(self.item({'enhance':4,'awaken':0}))
        self.assertIsNone(self.route.intents.pending());self.assertEqual(self.last(),'observed_progress')
    def test_the_same_breakthrough_failed(self):
        self.sent('breakthrough',2);self.route.settle(self.item({'enhance':50,'breakthrough':2,'awaken':0}))
        self.assertEqual(self.last(),'observed_failure')
    def test_the_same_enhance_had_no_effect(self):
        self.sent('enhance');self.route.settle(self.item({'enhance':3,'awaken':0}))
        self.assertIsNone(self.route.intents.pending());self.assertEqual(self.last(),'no_effect')
    def test_another_item_waits_for_its_own_read(self):
        self.sent('enhance',slot='worn:반지');self.route.settle(self.item({'enhance':9,'awaken':0}))
        self.assertIsNotNone(self.route.intents.pending())
    def test_a_field_not_read_waits(self):
        self.sent('breakthrough',2);self.route.settle(self.item({'enhance':50,'awaken':0}))
        self.assertIsNotNone(self.route.intents.pending())


class Enhance(WithRoute):
    """The real guard and record, on a level that a fake press raises."""
    def run_press(self,item,*,cap=None,effect='rise',start=20,goal_word='강화'):
        self.zones=Zones(level=start,next_level=start+1,word=goal_word);self.short=False;self.presses=0
        def click(hit):
            self.presses+=1
            if effect=='rise':self.zones.level+=1;self.zones.next+=1
            elif effect=='short':self.short=True
        self.service.click_hit=click
        with patch('owner_text.read',self.zones.read),patch.object(g,'coins_short',side_effect=lambda f:self.short):
            self.route.press_enhance(item,cap)
    def item_at(self,level=20):return self.item({'enhance':level,'awaken':0})
    def test_it_presses_up_to_the_cap(self):
        self.run_press(self.item_at(),cap=23)
        self.assertEqual(self.presses,3);self.assertIsNone(self.route.intents.pending())
    def test_it_stops_at_the_goal(self):
        self.run_press(self.item_at(48),start=48)
        self.assertEqual(self.presses,2);self.assertEqual(self.zones.level,50)
    def test_the_message_ends_the_turn_and_closes_the_record(self):
        with self.assertRaises(g.CoinsShort):self.run_press(self.item_at(),effect='short')
        self.assertEqual(self.presses,1);self.assertIsNone(self.route.intents.pending())
    def test_nothing_changing_leaves_it_to_the_next_read(self):
        self.run_press(self.item_at(),effect='none')
        self.assertEqual(self.presses,1);self.assertIsNotNone(self.route.intents.pending())
    def test_a_dim_button_presses_nothing(self):
        item=self.item_at();self.zones=Zones(count='1/6');self.service.click_hit=lambda hit:self.fail('pressed')
        with patch('owner_text.read',self.zones.read):self.route.press_enhance(item)
        self.assertIn(g.ENHANCE,item.done)


class Once(WithRoute):
    def setUp(self):
        super().setUp()
        self.route.side_tab=lambda kind:True
    def run_once(self,item,kind,zones,after=None):
        self.presses=0
        def click(hit):self.presses+=1
        self.service.click_hit=click
        self.route.after_result=after or (lambda item,kind:None)
        with patch('owner_text.read',zones.read):self.route.press_once(item,kind)
    def test_it_presses_once_and_leaves_the_record_to_the_details(self):
        item=self.item({'enhance':50,'breakthrough':3,'awaken':0})
        self.run_once(item,g.AWAKEN,Zones(word='각성',cost='5,000',count='1/1'))
        self.assertEqual(self.presses,1);pending=self.route.intents.pending()
        self.assertEqual((pending['kind'],pending['before'].awakening,pending['before'].slot),('awaken',0,'worn:무기'))
    def test_breakthrough_too(self):
        item=self.item({'enhance':50,'breakthrough':2,'awaken':0})
        self.run_once(item,g.BREAK,Zones(word='돌파',cost='20,000',count='3/1'))
        self.assertEqual(self.presses,1);self.assertEqual(self.route.intents.pending()['before'].breakthrough,2)
    def test_no_spare_presses_nothing(self):
        item=self.item({'enhance':50,'breakthrough':3,'awaken':0})
        with patch.object(self.route,'choose_material',return_value=False):
            self.run_once(item,g.AWAKEN,Zones(word='각성',cost='5,000',count='0/1'))
        self.assertEqual(self.presses,0);self.assertIn(g.AWAKEN,item.done);self.assertIsNone(self.route.intents.pending())
    def test_an_empty_panel_is_not_a_target(self):
        item=self.item({'enhance':30,'breakthrough':0,'awaken':0})
        self.run_once(item,g.BREAK,Zones(title='',word='돌파',cost='20,000'))
        self.assertEqual(self.presses,0);self.assertIn(g.BREAK,item.done)
    def test_the_message_after_a_press_ends_the_turn(self):
        item=self.item({'enhance':50,'breakthrough':3,'awaken':0})
        zones=Zones(word='각성',cost='5,000',count='1/1')
        self.service.click_hit=lambda hit:None
        with patch('owner_text.read',zones.read),patch.object(g,'coins_short',return_value=True):
            with self.assertRaises(g.CoinsShort):self.route.press_once(item,g.AWAKEN)
        self.assertIsNone(self.route.intents.pending())


class Material(WithRoute):
    def choose(self,rows):
        with patch('owner_text.read',return_value=rows):
            return self.route.choose_material(self.item({'enhance':50,'awaken':0})),self.clicks
    def test_a_second_tile_is_the_spare(self):
        chosen,clicks=self.choose([row('2')]);self.assertTrue(chosen);self.assertEqual(clicks[0][:2],g.real_hit(*g.SECOND_TILE)[:2])
    def test_the_item_alone_has_no_spare(self):
        chosen,clicks=self.choose([row('1')]);self.assertFalse(chosen);self.assertEqual(clicks,[])
    def test_an_unread_count_presses_nothing(self):
        chosen,clicks=self.choose([]);self.assertFalse(chosen);self.assertEqual(clicks,[])


class Order(WithRoute):
    def test_the_lowest_of_a_grade_goes_first_up_to_a_little_past_the_next(self):
        reads={'무기':10,'반지':20}
        seen=[]
        def read(item):
            item.values=dict(enhance=reads.get(item.slot,50),breakthrough=3,awaken=1);item.grade='희귀';return True
        def visit(item,cap=None):
            seen.append((item.slot,cap));item.values['enhance']=min(50,cap if cap else 50);reads[item.slot]=item.values['enhance']
        self.route.read=read;self.route.visit=visit
        self.route.deadline=time.monotonic()+60
        self.route.gear()
        self.assertEqual(seen[0],('무기',23))
        self.assertEqual(reads['무기'],50);self.assertEqual(reads['반지'],50)

class Stuck(WithRoute):
    def test_a_turn_that_raises_nothing_does_not_come_round_again(self):
        seen=[]
        def read(item):
            item.values=dict(enhance=10,breakthrough=3,awaken=1);item.grade='희귀';return True
        self.route.read=read;self.route.visit=lambda item,cap=None:seen.append(item.slot)
        self.route.deadline=time.monotonic()+60
        self.route.gear()
        self.assertEqual(len(seen),len(set(seen)));self.assertEqual(len(seen),11)


class Blessings(WithRoute):
    def setUp(self):
        super().setUp()
        self.route.document=dict(self.DOCUMENT,blessings={key:{'enabled':True,'enhance':50,'breakthrough':1} for key in ('1번','2번','3번','4번','5번')})
    def test_each_slot_is_read_and_a_miss_gets_one_more_turn(self):
        seen=[]
        def read(item):
            seen.append(item.slot)
            if item.slot!='가호3' or seen.count('가호3')>1:item.values={'enhance':50,'opening':5,'awaken':1}
            return True
        self.route.read=read
        self.route.blessings()
        self.assertEqual(seen,['가호1','가호2','가호3','가호4','가호5','가호3'])
    def test_only_what_is_short_is_visited(self):
        values={'가호1':(40,0),'가호2':(50,1),'가호3':(50,0),'가호4':(50,1),'가호5':(50,1)};visited=[]
        def read(item):
            item.values={'enhance':values[item.slot][0],'opening':1,'awaken':values[item.slot][1]};return True
        self.route.read=read;self.route.visit=lambda item,cap=None:visited.append(item.slot)
        self.route.blessings()
        self.assertEqual(visited,['가호1','가호3'])
    def test_enhancing_comes_before_awakening(self):
        item=self.item({'enhance':40,'opening':4,'awaken':0},slot='가호1',blessing=True)
        self.assertEqual(self.route.need(item),g.ENHANCE)
        item.done.add(g.ENHANCE);self.assertEqual(self.route.need(item),g.AWAKEN)
    def test_the_goal_is_read_from_the_old_field(self):
        self.assertEqual(self.route.goal(self.item({},slot='가호2',blessing=True))['awaken'],1)
    def test_a_blessing_awakens_on_its_pieces_and_never_picks_a_tile(self):
        self.route.side_tab=lambda kind:True;self.route.choose_material=lambda item:self.fail('picked a tile')
        presses=[];self.service.click_hit=lambda hit:presses.append(hit)
        item=self.item({'enhance':40,'opening':4,'awaken':0},slot='가호1',blessing=True)
        zones=Zones(word='각성',cost='5,000',count='3/100')
        with patch('owner_text.read',zones.read):
            self.route.press_once(item,g.AWAKEN)
        self.assertEqual(presses,[]);self.assertIn(g.AWAKEN,item.done)
    def test_it_presses_once_with_its_pieces(self):
        self.route.side_tab=lambda kind:True;self.route.after_result=lambda item,kind:None
        presses=[];self.service.click_hit=lambda hit:presses.append(hit)
        item=self.item({'enhance':40,'opening':4,'awaken':0},slot='가호1',blessing=True)
        zones=Zones(word='각성',cost='5,000',count='101/100')
        with patch('owner_text.read',zones.read):
            self.route.press_once(item,g.AWAKEN)
        self.assertEqual(len(presses),1);self.assertEqual(self.route.intents.pending()['before'].awakening,0)
    def test_reading_a_blessing_never_opens_the_bag(self):
        self.route.leave_growth=lambda:True;self.route.open_bag=lambda:self.fail('bag')
        with patch.object(g.worn,'settle_after_popup'),patch.object(g.worn,'inspect_real',return_value=False) as read:
            self.route.read(self.item({},slot='가호1',blessing=True))
        self.assertEqual(read.call_args.args[5],'가호1')


class Visit(WithRoute):
    def setUp(self):
        super().setUp();self.route.leave_growth=lambda:True;self.reads=0;self.enters=0
        self.route.read=self.read;self.route.enter=self.enter
    def read(self,item):self.reads+=1;return True
    def enter(self,item):self.enters+=1;return True
    def test_what_cannot_run_moves_on_with_nothing_read_again(self):
        item=self.item({'enhance':50,'breakthrough':1,'awaken':0})
        seen=[]
        def once(item,kind):seen.append(kind);item.done.add(kind)
        self.route.press_once=once
        self.route.visit(item)
        self.assertEqual(seen,[g.BREAK,g.AWAKEN]);self.assertEqual((self.enters,self.reads),(1,0))
    def test_the_details_are_read_when_enhancing_did_something(self):
        item=self.item({'enhance':20,'breakthrough':3,'awaken':1})
        def press(item,cap=None):item.changed=True;item.values['enhance']=50
        self.route.press_enhance=press
        self.route.visit(item)
        self.assertEqual((self.enters,self.reads),(1,1))
    def test_the_details_are_read_after_a_stage(self):
        item=self.item({'enhance':50,'breakthrough':3,'awaken':0})
        def once(item,kind):item.changed=True;item.values['awaken']=1
        self.route.press_once=once
        self.route.visit(item)
        self.assertEqual((self.enters,self.reads),(1,1))
    def test_nothing_to_do_opens_nothing(self):
        self.route.visit(self.item({'enhance':50,'breakthrough':3,'awaken':1}))
        self.assertEqual((self.enters,self.reads),(0,0))
    def test_no_coins_on_the_first_press_reads_nothing(self):
        item=self.item({'enhance':20,'breakthrough':3,'awaken':1})
        def press(item,cap=None):raise g.CoinsShort()
        self.route.press_enhance=press
        with self.assertRaises(g.CoinsShort):self.route.visit(item)
        self.assertEqual(self.reads,0)
    def test_no_coins_after_some_steps_reads_where_it_stopped(self):
        item=self.item({'enhance':20,'breakthrough':3,'awaken':1})
        def press(item,cap=None):item.changed=True;raise g.CoinsShort()
        self.route.press_enhance=press
        with self.assertRaises(g.CoinsShort):self.route.visit(item)
        self.assertEqual(self.reads,1)
    def test_a_turn_of_the_grade_ends_at_its_cap(self):
        item=self.item({'enhance':20,'breakthrough':3,'awaken':1})
        def press(item,cap=None):item.changed=True
        self.route.press_enhance=press
        self.route.visit(item,23)
        self.assertEqual((self.enters,self.reads),(1,1))
    def test_rounds_are_bounded_when_nothing_rises(self):
        item=self.item({'enhance':50,'breakthrough':2,'awaken':1})
        presses=[]
        def once(item,kind):presses.append(kind);item.changed=True
        self.route.press_once=once
        self.route.visit(item)
        self.assertEqual(len(presses),g.ROUNDS);self.assertEqual(self.reads,g.ROUNDS)

class Enter(WithRoute):
    """성장 is pressed from the top of the details: the wheel never turns on the way in."""
    def run_enter(self,*,heading=('토끼가호장식2','일반'),growth=True):
        self.route.leave_growth=lambda:True;self.route.open_bag=lambda:True;closed=[]
        self.route.into_growth=lambda item:growth
        item=self.item(None,slot='반지');item.grade=None
        with patch.object(g.worn,'settle_after_popup'),patch.object(g.worn,'open_tile',return_value=True),patch.object(g.worn,'tile_heading',return_value=heading),\
             patch.object(g.worn,'close_details',side_effect=lambda *a:closed.append(1)),patch('owner_mission_ui.MissionUI.wheel',side_effect=AssertionError('scrolled')):
            return self.route.enter(item),closed,item
    def test_in_with_no_scroll(self):
        entered,closed,item=self.run_enter()
        self.assertTrue(entered);self.assertEqual(closed,[]);self.assertEqual(item.grade,'일반')
    def test_another_items_window_closes(self):
        entered,closed,_=self.run_enter(heading=None)
        self.assertFalse(entered);self.assertEqual(closed,[1])
    def test_no_growth_screen_closes(self):
        entered,closed,_=self.run_enter(growth=False)
        self.assertFalse(entered);self.assertEqual(closed,[1])


class Stand(unittest.TestCase):
    def test_the_native_entry_does_not_run_after_the_route(self):
        import owner_program_runtime as runtime
        native=NS(run_growth_entry=lambda *a,**k:self.fail('native entry'))
        runtime.install_identity_preflight(native,'run_growth_entry',())
        with patch.object(runtime,'fresh_growth_identity',return_value=True),patch('owner_worn_growth.run',return_value=True):
            self.assertTrue(native.run_growth_entry(NS(values={'auto_growth.equipment.enabled':True}),None,None))
    def test_the_field_name_spares_the_info_window(self):
        import owner_program_runtime as runtime
        context=object();adapter=NS(_owner_growth_identity_context=None)
        progress=NS(character='홍짱군',level=50,observed=0)
        with patch('owner_progression.state',return_value=progress),patch.object(runtime,'field_shows_name',return_value=True),patch('owner_quest_preflight.read_power',side_effect=AssertionError('opened')):
            self.assertTrue(runtime.fresh_growth_identity(adapter,context,None))
        self.assertIs(adapter._owner_growth_identity_context,context)
    def test_another_name_opens_the_info_window(self):
        import owner_program_runtime as runtime
        progress=NS(character='홍짱군',level=50,observed=0);opened=[]
        with patch('owner_progression.state',return_value=progress),patch.object(runtime,'field_shows_name',return_value=False),patch('owner_quest_preflight.read_power',side_effect=lambda *a:opened.append(1)):
            runtime.fresh_growth_identity(NS(_owner_growth_identity_context=None),NS(checkpoint=lambda:None),None)
        self.assertEqual(opened,[1])
    def test_the_old_list_route_stands_aside_after_this_route(self):
        import owner_gear_native_install_candidate as install
        context=NS(checkpoint=lambda:None)
        service=NS(context=context,check=lambda:None,adapter=NS(_owner_worn_growth_context=context))
        guarded=install.wrap(lambda *a,**k:self.fail('old route'),lambda s:self.fail('identity'),None)
        self.assertIs(guarded(service),False)
    def test_a_record_from_this_route_needs_no_old_recovery(self):
        import owner_growth_recovery as r
        from owner_progression import state
        seen=NS(slot='worn:무기',character='i')
        adapter=NS(values={'auto_growth.equipment.enabled':True},project=NS(root='x'),_owner_progression_observation=None)
        context=NS(checkpoint=lambda:None)
        progress=NS(observed=time.monotonic(),character='c',level=50)
        adapter._owner_progression_observation=(context,progress.observed,progress.character)
        with patch('owner_progression.state',return_value=progress),patch('owner_program_runtime.gear_identity',return_value='i'),patch.object(r,'pending',return_value={'phase':'sent','kind':'enhance','before':seen}):
            self.assertEqual(r.recover(adapter,context,NS(held=())),'no_pending')



class Hold(unittest.TestCase):
    """돌파 asks for 길게 터치하여 돌파: the button is held until the prompt goes."""
    def test_held_until_the_prompt_goes(self):
        import owner_worn_growth as g
        events=[];looks=iter([True,True,False])
        inputs=NS(transaction=lambda:__import__('contextlib').nullcontext(),move=lambda x,y:events.append(('move',x,y)),
                  down=lambda *a:events.append('down'),up=lambda *a:events.append('up'))
        route=g.Route.__new__(g.Route);route.inputs=inputs;route.context=NS(wait=lambda s:None);route.service=NS(capture=lambda:None)
        with patch.object(g.Route,'hold_needed',side_effect=lambda f:next(looks)):route.hold_press(NS(slot='목걸이'))
        self.assertEqual(events[1:],['down','up']);self.assertEqual(events[0][1:],g.real_hit(*g.HOLD_BUTTON)[:2])



class Idle(unittest.TestCase):
    """A pass that pressed nothing rests; the same goals keep the rest, a swap or a death ends it."""
    def test_rest_and_wake(self):
        adapter=NS();self.assertFalse(g.idle_skip(adapter,'r1'))
        adapter._owner_worn_idle=(time.monotonic()+60,'r1')
        self.assertTrue(g.idle_skip(adapter,'r1'));self.assertFalse(g.idle_skip(adapter,'r2'))
        g.wake(adapter);self.assertFalse(g.idle_skip(adapter,'r1'))
        adapter._owner_worn_idle=(time.monotonic()-1,'r1');self.assertFalse(g.idle_skip(adapter,'r1'))



class Table(unittest.TestCase):
    """A part read lately with nothing to do is not opened again; a short step rests."""
    def route(self,goal):
        r=g.Route.__new__(g.Route);r.adapter=NS();r.root='x';r.profile='p'
        r.document={'grades':{'희귀':dict(enabled=True,enhance=50,breakthrough=3,awaken=goal)}}
        return r
    def test_at_goal_is_skipped_else_read(self):
        item=g.Item('반지',False)
        with patch('owner_growth_current.recent_reading',return_value=('희귀',{'enhance':50,'breakthrough':3,'awaken':0})),patch.object(g,'breakthrough_allowed',return_value=True):
            self.assertTrue(self.route(0).from_table(item))
            item=g.Item('반지',False);self.assertFalse(self.route(1).from_table(item));self.assertIsNone(item.values)
    def test_a_short_step_rests(self):
        r=self.route(1);item=g.Item('반지',False)
        g.rest(r.adapter,'반지',g.AWAKEN)
        with patch('owner_growth_current.recent_reading',return_value=('희귀',{'enhance':50,'breakthrough':3,'awaken':0})),patch.object(g,'breakthrough_allowed',return_value=True):
            self.assertTrue(r.from_table(item))
        g.wake(r.adapter);self.assertFalse(g.resting(r.adapter,'반지',g.AWAKEN))


if __name__=='__main__':unittest.main()
