"""Higher grade first: the step rule, the arrow, the settings and the timetable. Fake frames and inputs; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,tempfile,unittest,copy,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_upgrade_equip as up
import owner_hd as hd


class Steps(unittest.TestCase):
    def test_any_higher_grade_when_on(self):
        on={'higher':True}
        for a,b in (('일반','희귀'),('희귀','영웅'),('일반','영웅'),('영웅','전설'),('일반','전설')):self.assertTrue(up.allowed(a,b,on),(a,b))
    def test_never_off_down_sideways_or_unread(self):
        on={'higher':True}
        self.assertFalse(up.allowed('일반','희귀',{'higher':False}))
        for a,b in (('희귀','일반'),('희귀','희귀'),(None,'희귀'),('일반',None),('전설','영웅')):self.assertFalse(up.allowed(a,b,on),(a,b))


class Pattern(unittest.TestCase):
    def test_same_grade_follows_the_pattern_rank(self):
        # User 11-06: 나비 first, so every slot should end up 나비.
        on={'higher':True};order=('나비','도깨비','토끼')
        self.assertTrue(up.blessing_better('희귀','희귀','도깨비','나비',on,order))
        self.assertFalse(up.blessing_better('희귀','희귀','나비','도깨비',on,order))
        self.assertTrue(up.blessing_better('희귀','희귀','연꽃','토끼',on,order))      # unlisted stands last
        self.assertFalse(up.blessing_better('희귀','희귀','도깨비','연꽃',on,order))
        self.assertFalse(up.blessing_better('희귀','희귀','도깨비',None,on,order))
    def test_grade_comes_first(self):
        on={'higher':True};order=('나비','도깨비')
        self.assertTrue(up.blessing_better('일반','희귀','나비','도깨비',on,order))
        self.assertFalse(up.blessing_better('희귀','일반','도깨비','나비',on,order))
        self.assertFalse(up.blessing_better('희귀','희귀','도깨비','나비',{'higher':False},order))


class Colour(unittest.TestCase):
    def tile(self,real,place,corner):
        x,y=place;real[y-24:y+24,x-24:x+24]=corner;real[y-12:y+12,x-12:x+12]=(230,230,230)  # an icon in the middle
    def test_blue_and_purple_are_opened_grey_and_empty_are_not(self):
        real=np.full((768,1366,3),(52,47,45),np.uint8)                    # pc1's empty place
        places=[(up.BAG_X[i],up.BAG_Y[0]) for i in range(4)]
        for place,corner in zip(places,((51,102,139),(50,58,68),(81,76,69),(120,60,130))):self.tile(real,place,corner)
        self.assertEqual(up.candidates(real),[places[0],places[1],places[3]])


class Settings(unittest.TestCase):
    def store(self,document=None):
        from owner_gear_settings_candidate import Store
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        store=Store(directory.name,'who')
        if document is not None:
            store.path.parent.mkdir(parents=True,exist_ok=True);store.path.write_text(json.dumps(document,ensure_ascii=False),encoding='utf-8')
        return directory.name,store
    def test_an_old_document_reads_with_nothing_ticked(self):
        from owner_gear_settings_candidate import DEFAULT
        old=copy.deepcopy(DEFAULT);old.pop('gear_equip');old['blessing_equip']={'enabled':True,'priorities':[]}
        root,store=self.store(old);value=store.read()
        self.assertEqual(value['gear_equip'],{'higher':False})
        self.assertFalse(value['blessing_equip']['higher'])
        with patch('owner_hunt_rules_candidate.configured_identity',return_value='who'):
            self.assertFalse(up.enabled(root,'gear'));self.assertFalse(up.enabled(root,'blessing'))
    def test_a_tick_turns_its_kind_on_alone(self):
        from owner_gear_settings_candidate import DEFAULT
        doc=copy.deepcopy(DEFAULT);doc['gear_equip']={'normal_to_rare':True}   # an old step tick still turns it on
        root,store=self.store(doc)
        with patch('owner_hunt_rules_candidate.configured_identity',return_value='who'):
            self.assertTrue(up.enabled(root,'gear'));self.assertFalse(up.enabled(root,'blessing'))
            self.assertEqual(up.settings(root,'gear'),{'higher':True})
    def test_a_wrong_value_is_refused(self):
        from owner_gear_settings_candidate import DEFAULT,validate
        doc=copy.deepcopy(DEFAULT);doc['gear_equip']['higher']='yes'
        with self.assertRaisesRegex(ValueError,'높은 등급'):validate(doc)


class Timetable(unittest.TestCase):
    def test_two_jobs_each_with_its_own_time_and_switch(self):
        import owner_timetable as t
        gear,bless=t.BY_KEY['gear_equip'],t.BY_KEY['blessing_equip']
        self.assertNotEqual(gear.setting,bless.setting)
        self.assertTrue(t.enabled(gear,{up.GEAR_KEY:True}));self.assertFalse(t.enabled(bless,{up.GEAR_KEY:True}))
        from owner_schedule_settings import rows
        listed=[row[0] for row in rows(t.config.__wrapped__(None) if hasattr(t.config,'__wrapped__') else {'jobs':{}})]
        self.assertIn('gear_equip',listed);self.assertIn('blessing_equip',listed)
    def test_the_job_runs_the_owner_routine(self):
        import owner_timetable as t
        with patch('owner_upgrade_equip.run',return_value='장비 교체 1개') as run:
            self.assertTrue(t.invoke(NS(),t.BY_KEY['gear_equip'],NS(),NS()))
        self.assertEqual(run.call_args[0][3],'gear')
        with patch('owner_upgrade_equip.run',return_value='보류 · 1366x768 화면이 아님'):
            self.assertFalse(t.invoke(NS(),t.BY_KEY['blessing_equip'],NS(),NS()))


class Choose(unittest.TestCase):
    def test_per_part_the_highest_grade_then_the_most_power(self):
        found=[dict(slot='귀걸이',spare='희귀',power=6000,title='a'),dict(slot='귀걸이',spare='희귀',power=6334,title='b'),
               dict(slot='귀걸이',spare='영웅',power=5000,title='c'),dict(slot='목걸이',spare='희귀',power=None,title='d')]
        chosen={r['slot']:r['title'] for r in up.best(found,lambda r:(up.ORDER.index(r['spare']),r['power'] or -1))}
        self.assertEqual(chosen,{'귀걸이':'c','목걸이':'d'})
    def test_the_chosen_tile_must_open_as_the_same_spare(self):
        row=dict(place=(1,1),worn='일반',spare='희귀',title='수정장식귀걸이(귀속)')
        closed=[];pressed=[]
        with patch.object(up,'open_compare',return_value='compare'),patch.object(up,'compare',return_value=('일반','희귀','다른귀걸이(귀속)',None)),\
             patch.object(up.bound,'close_window',side_effect=lambda *a:closed.append(1)),patch.object(up,'press_equip',side_effect=lambda *a:pressed.append(1)):
            self.assertIn('다름',up.equip_chosen(NS(),NS(),row))
        self.assertEqual(pressed,[]);self.assertEqual(closed,[1])


class Grow(unittest.TestCase):
    def test_the_part_names_the_slot(self):
        self.assertEqual(up.part_slot(['귀걸이'],'수정장식 귀걸이(귀속)'),'귀걸이')
        self.assertEqual(up.part_slot(['각반'],''),'다리')
        self.assertEqual(up.part_slot(['부채'],'흑암부채'),'무기')
        self.assertIsNone(up.part_slot([],''))
    def test_a_swap_goes_straight_to_growth_for_its_slot(self):
        frame=NS(hi=np.zeros((768,1366,3),np.uint8));service=NS(capture=lambda:frame,check=lambda:None)
        context=NS(checkpoint=lambda:None,wait=lambda s:None)
        with patch('project_adapter.town_services.TownServices',lambda *a:service),\
             patch.object(up,'gear',return_value=[('목걸이','유리구슬목걸이','일반','희귀',True)]),\
             patch.object(up.bound,'window_kind',return_value=None),patch.object(up.worn,'leave_blessing_screen'),patch.object(up.worn,'close_bag'),\
             patch('owner_progression.inventory_parts',return_value=(False,False)),patch('owner_worn_growth.grow') as grow:
            result=up.run(NS(project=NS(root='x')),context,NS(),'gear',choice={'higher':True})
        self.assertEqual(result,'장비 교체 1개');self.assertEqual(grow.call_args[0][3],['목걸이'])
    def test_growth_follows_the_saved_switch(self):
        import owner_worn_growth as g
        with patch.object(g,'growth_switches',return_value={'gear':False,'blessing':True}):
            self.assertFalse(g.grow(NS(project=NS(root='x')),NS(),NS(),['목걸이']))


class Repeat(unittest.TestCase):
    def test_after_a_check_the_next_comes_at_the_recheck_interval(self):
        import owner_timetable as t
        from datetime import timedelta
        at=t.now();plan=t.Planner.__new__(t.Planner)
        plan.values={up.GEAR_KEY:True};plan.cfg={'enabled':True,'jobs':{}};plan.root=Path('.')
        plan.state={'gear_equip':{'period':t.period(t.BY_KEY['gear_equip'],at),'status':'processed'}};plan.commit=lambda:None
        with patch.object(t.Planner,'recheck_minutes',return_value=20),patch.object(t,'busy_windows',return_value=[]):
            moved=plan.repeat_equip('gear_equip',at)
        item=plan.state['gear_equip']
        if t.period(t.BY_KEY['gear_equip'],at+timedelta(minutes=20))==item['period']:
            self.assertTrue(moved);self.assertEqual(item['status'],'pending');self.assertTrue(item['equip_recheck'])
            self.assertEqual(t.parse_at(item['at']).replace(microsecond=0),(at+timedelta(minutes=20)).replace(microsecond=0))
        else:self.assertFalse(moved)


class Unchanged(unittest.TestCase):
    def test_a_full_check_with_nothing_lets_the_same_list_skip(self):
        adapter=NS()
        self.assertFalse(up.seen_before(adapter,'gear','x'))
        up.remember(adapter,'gear','x');self.assertTrue(up.seen_before(adapter,'gear','x'))
        self.assertFalse(up.seen_before(adapter,'gear','y'));self.assertFalse(up.seen_before(adapter,'blessing','x'))
        up.remember(adapter,'gear',None);self.assertFalse(up.seen_before(adapter,'gear','x'))
    def test_a_tile_looks_the_same_in_another_row(self):
        real=np.zeros((768,1366,3),np.uint8)
        for (x,y),shade in (((up.BAG_X[0],up.BAG_Y[0]),(51,102,139)),((up.BAG_X[2],up.BAG_Y[6]),(50,70,90))):
            real[y-24:y+24,x-24:x+24]=shade;real[y-12:y+12,x-12:x+12]=(230,200,40)
        self.assertEqual(up.signature(real,(up.BAG_X[0],up.BAG_Y[0])),up.signature(real,(up.BAG_X[2],up.BAG_Y[6])))


class Test(unittest.TestCase):
    def test_both_tests_reach_the_routine(self):
        import owner_challenge_test as c
        for key,kind in ((c.GEAR_EQUIP_KEY,'gear'),(c.BLESSING_EQUIP_KEY,'blessing')):
            with patch('owner_upgrade_equip.run',return_value='교체할 장비 없음') as run:
                self.assertEqual(c.execute(NS(values={}),NS(),NS(),key),'교체할 장비 없음')
            self.assertEqual(run.call_args[0][3],kind)
    def test_nothing_ticked_does_nothing(self):
        frame=NS(hi=np.zeros((768,1366,3),np.uint8))
        service=NS(capture=lambda:frame,context=None)
        with patch('project_adapter.town_services.TownServices',lambda *a:service):
            self.assertIn('꺼짐',up.run(NS(project=NS(root='x')),NS(),NS(),'gear',choice={}))
    def test_not_at_1366_does_nothing(self):
        service=NS(capture=lambda:np.zeros((479,897,3),np.uint8),context=None)
        with patch('project_adapter.town_services.TownServices',lambda *a:service):
            self.assertIn('1366',up.run(NS(project=NS(root='x')),NS(),NS(),'gear',choice={'higher':True}))


class Compare(unittest.TestCase):
    def run_compare(self,left,right,choice={'higher':True}):
        real=np.zeros((768,1366,3),np.uint8)
        def read(_,area,**k):
            read.n=getattr(read,'n',0)+1;return [dict(text=left if read.n==1 else right)]
        service=NS(capture=lambda:NS(hi=real))
        with patch('owner_text.read_area',read),patch.object(up.bound,'window_title',return_value='수정장식 목걸이(귀속)'):
            return up.compare(service,NS(),choice)
    def test_higher_grade_is_taken_whatever_its_stats(self):
        # An unenhanced 영웅 may show less 전투력 than the worn one, and no arrow (user, 11-06).
        self.assertIsNone(self.run_compare('일반','희귀')[3])
        self.assertIsNone(self.run_compare('희귀','영웅')[3]);self.assertIsNone(self.run_compare('영웅','전설')[3])
    def test_same_grade_is_left(self):
        self.assertEqual(self.run_compare('희귀','희귀')[3],'등급 조건 아님')


class Floor(unittest.TestCase):
    """Bag tiles no higher than the lowest worn grade are not opened."""
    def test_tile_shades(self):
        real=np.zeros((768,1366,3),np.uint8);places=[(up.BAG_X[i],up.BAG_Y[0]) for i in range(4)]
        for (x,y),shade in zip(places,((51,102,139),(120,60,130),(150,120,40),(70,66,60))):real[y-26:y+26,x-26:x+26]=shade
        self.assertEqual([up.tile_grade(real,p) for p in places],['희귀','영웅','전설',None])
    def test_floor_needs_every_part(self):
        with patch('owner_progression.state',return_value=NS(character='c')),patch('owner_growth_current.equipped_rows',return_value=[('무기','희귀'),('반지','영웅')]):
            self.assertEqual(up.worn_floor(NS(project=NS(root='x'))),'희귀')
        with patch('owner_progression.state',return_value=NS(character='c')),patch('owner_growth_current.equipped_rows',return_value=[('무기','희귀'),('반지','미확인')]):
            self.assertIsNone(up.worn_floor(NS(project=NS(root='x'))))
    def bag(self,tiles):
        real=np.zeros((768,1366,3),np.uint8)
        for (i,shade,arrow) in tiles:
            x,y=up.BAG_X[i],up.BAG_Y[0];real[y-26:y+26,x-26:x+26]=shade;real[y-10:y+10,x-10:x+10]=(240,240,240)
            if arrow:real[y-18:y-8,x+12:x+22]=(60,200,60)
        return real
    def test_arrow_tiles_open_only_for_an_empty_part(self):
        # pc1 13:25, earring off: a rare earring and a plain one carry the arrow; every part else wears 희귀.
        real=self.bag([(0,(51,102,139),True),(1,(70,66,60),True),(2,(51,102,139),False)])
        hint=up.empty_hint(real,'희귀');self.assertTrue(hint)
        self.assertEqual([i for i in range(3) if up.worth_opening(real,(up.BAG_X[i],up.BAG_Y[0]),'희귀',hint)],[0,1])
        real=self.bag([(0,(51,102,139),True),(2,(51,102,139),False)])
        self.assertFalse(up.empty_hint(real,'희귀'))
        self.assertEqual([i for i in (0,2) if up.worth_opening(real,(up.BAG_X[i],up.BAG_Y[0]),'희귀',False)],[])
    def test_same_grade_tiles_are_not_opened(self):
        real=np.zeros((768,1366,3),np.uint8);opened=[]
        for i,shade in enumerate(((51,102,139),(120,60,130))):
            x,y=up.BAG_X[i],up.BAG_Y[0];real[y-26:y+26,x-26:x+26]=shade;real[y-10:y+10,x-10:x+10]=(240,240,240)
        service=NS(capture=lambda:NS(hi=real),check=lambda:None)
        with patch.object(up,'open_compare',side_effect=lambda s,c,p:opened.append(p)):
            up.scan_gear(service,NS(checkpoint=lambda:None),{'higher':True},'희귀')
        self.assertEqual(opened,[(up.BAG_X[1],up.BAG_Y[0])])


class Acquire(unittest.TestCase):
    """A blessing not made yet on a slot tab: made there when it uses no tradeable piece (user 11-06), else left."""
    def run_slots(self,tradeable):
        state=dict(opened=0,made=0,closed=0)
        frame=NS(hi=np.zeros((768,1366,3),np.uint8))
        service=NS(capture=lambda:frame,check=lambda:None,click_hit=lambda hit:None)
        context=NS(checkpoint=lambda:None,wait=lambda s:None)
        def open_compare(service,context,place):
            state['opened']+=1;return 'compare' if state['made'] else None
        def press(service,context):state['made']+=1;return True
        def close(service,context):state['closed']+=1;return True
        with patch.object(up.worn,'open_blessing_screen',return_value=True),patch.object(up.bound,'tile_count',return_value=2),             patch.object(up,'seen_before',return_value=False),patch.object(up,'remember'),patch.object(up,'tile_plus',return_value=0),             patch.object(up,'open_compare',open_compare),patch.object(up.bound,'acquire_popup',side_effect=lambda f:None if state['made'] else tradeable),             patch.object(up.bound,'press_acquire',press),patch.object(up.bound,'close_acquire',close),             patch.object(up.bound,'window_kind',return_value=None),patch.object(up.bound,'close_window'),             patch.object(up,'compare',return_value=('희귀','희귀','x',None)),patch.object(up,'bound_title',return_value='나비 가호 장식1'):
            up.blessings(NS(),service,context,{'higher':True},('나비',))
        return state
    def test_made_with_no_tradeable_piece_then_compared(self):
        state=self.run_slots(0)
        self.assertEqual(state['made'],1);self.assertEqual(state['closed'],0);self.assertEqual(state['opened'],1+5)
    def test_left_when_tradeable_pieces_would_go(self):
        state=self.run_slots(3);self.assertEqual(state['made'],0);self.assertEqual(state['closed'],5)
        state=self.run_slots(-1);self.assertEqual(state['made'],0)


if __name__=='__main__':unittest.main()
