"""Any blessing without 귀속 stops 일괄 획득. Fake input and rows, and saved screens where kept; never a game test."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import numpy as np
import owner_blessing_bound as b
import owner_hd as hd
import owner_worn_stats as worn


def real(colour=None):
    return np.zeros((768,1366,3),np.uint8)


class Sweep(unittest.TestCase):
    def setUp(self):
        self.clicks=[];self.open=False;self.titles=[];self.opens=True
        self.frame=NS(hi=real((110,190,80)))
        def click(hit):
            self.clicks.append(hit[:2]);self.open=self.opens and hit[:2] in self.tiles
        self.service=NS(context=NS(checkpoint=lambda:None,wait=lambda s:None),check=lambda:None,capture=lambda:self.frame,click_hit=click)
        self.tiles=[hd.real_hit(*place)[:2] for place in b.places(16)]
    def run_it(self,count,titles,acquire=None,**options):
        names=iter(titles)
        self.acquire=acquire
        def closing(service,context,kind):self.open=False
        with patch.object(b,'tile_count',return_value=count),patch.object(b,'window_kind',side_effect=lambda f:'compare' if self.open else None),\
             patch.object(b,'close_window',side_effect=closing),patch.object(b,'window_title',side_effect=lambda f,kind:next(names)),\
             patch.object(b,'acquire_popup',side_effect=lambda f:None if self.open or self.acquire is None else self.acquire),patch.object(b,'close_acquire'):
            return b.skip_reason(self.service,**options)
    def test_a_blessing_made_from_bound_pieces_passes(self):
        # pc1 11-06: unclaimed tiles open 가호를 획득하시겠습니까? (거래 가능 소모 조각 : 0개).
        self.opens=False
        self.assertIsNone(self.run_it(2,[],acquire=0))
    def test_one_that_would_use_tradeable_pieces_stops(self):
        self.opens=False
        self.assertIn('거래 가능 조각',self.run_it(2,[],acquire=3))
    def tile_clicks(self):return [c for c in self.clicks if c in self.tiles]
    def test_all_bound_may_press(self):
        self.assertIsNone(self.run_it(3,['가호1(귀속)','가호2(귀속)','가호3(귀속)']))
        self.assertEqual(len(self.tile_clicks()),3)
    def test_one_without_stops_at_once(self):
        reason=self.run_it(3,['가호1(귀속)','연꽃 가호 장식1','가호3(귀속)'])
        self.assertIn('귀속 없는 가호',reason);self.assertEqual(len(self.tile_clicks()),2)
    def test_an_unread_title_stops(self):self.assertIn('제목 미확인',self.run_it(2,['']))
    def test_no_tile_is_clicked_twice(self):
        self.run_it(13,['x(귀속)']*13)
        self.assertEqual(len(self.tile_clicks()),len(set(self.tile_clicks())))
    def test_no_tiles_seen_stops_and_clicks_no_tile(self):
        self.assertIn('미확인',self.run_it(0,[]));self.assertEqual(self.tile_clicks(),[])
    def test_a_full_screen_stops(self):
        self.assertIn('한 화면',self.run_it(16,[]));self.assertEqual(self.tile_clicks(),[])
    def test_a_window_that_does_not_open_stops(self):
        self.opens=False
        self.assertIn('안 열림',self.run_it(2,[]));self.assertEqual(len(self.tile_clicks()),1)


class Count(unittest.TestCase):
    def frame(self,count):
        big=np.full((768,1366,3),15,np.uint8);rng=np.random.default_rng(1)
        for x,y in b.places(count):big[y-22:y+22,x-22:x+22]=rng.integers(20,220,(44,44,3),dtype=np.uint8)
        return NS(hi=big)
    def test_tiles_in_order(self):
        self.assertEqual(b.tile_count(self.frame(13)),13);self.assertEqual(b.tile_count(self.frame(0)),0)
        self.assertEqual(b.tile_count(self.frame(16)),16)


class Window(unittest.TestCase):
    def test_the_kinds(self):
        frame=NS(hi=np.zeros((768,1366,3),np.uint8))
        with patch.object(worn,'real_popup',return_value=True):self.assertEqual(b.window_kind(frame),'worn')
        with patch.object(worn,'real_popup',return_value=False):
            with patch('owner_text.read_area',return_value=[dict(text='정보')]):self.assertEqual(b.window_kind(frame),'compare')
            with patch('owner_text.read_area',return_value=[]):self.assertIsNone(b.window_kind(frame))
    def test_a_comparison_closes_at_its_own_x(self):
        clicks=[];service=NS(click_hit=lambda hit:clicks.append(hit[:2]),check=lambda:None,capture=lambda:None)
        context=NS(checkpoint=lambda:None,wait=lambda s:None)
        with patch.object(b,'window_kind',return_value=None):b.close_window(service,context,'compare')
        self.assertEqual(clicks,[hd.real_hit(*b.COMPARE_CLOSE)[:2]])


class Places(unittest.TestCase):
    def test_row_by_row(self):
        self.assertEqual(b.places(5),[(1092,152),(1152,152),(1212,152),(1272,152),(1092,212)])


class Hook(unittest.TestCase):
    def test_a_real_frame_answers_by_the_owner_rule(self):
        from owner_blessing_original_fence_candidate import _bound
        wrapped=_bound(lambda *a:self.fail('tile colours'))
        with patch('owner_blessing_bound.skip_reason',return_value='귀속 없는 가호') as rule:
            self.assertEqual(wrapped(NS(capture=lambda:NS(hi=1))),'귀속 없는 가호')
        rule.assert_called_once()
    def test_an_old_frame_keeps_the_old_answer(self):
        from owner_blessing_original_fence_candidate import _bound
        self.assertEqual(_bound(lambda *a:'old')(NS(capture=lambda:np.zeros((2,2)))),'old')
    def test_no_service_keeps_the_old_answer(self):
        from owner_blessing_original_fence_candidate import _bound
        self.assertEqual(_bound(lambda *a:'old')(),'old')


class Claim(unittest.TestCase):
    """The claim alone, on the 전체 tab, by its own confirmation window. Equip and summon are never reached."""
    def run_claim(self,button=True):
        clicks=[];left=[]
        service=NS(capture=lambda:NS(hi=np.zeros((768,1366,3),np.uint8)),check=lambda:None,click_hit=lambda hit:clicks.append(hit[:2]))
        context=NS(checkpoint=lambda:None,wait=lambda s:None)
        def read(root,frame,box,**k):
            if box==b.CLAIM_BUTTON:return [dict(text='일괄 획득',rx=1182,ry=717)] if button else []
            return []
        with patch('project_adapter.town_services.TownServices',lambda *a:service),patch.object(worn,'open_blessing_screen',return_value=True),             patch('owner_text.read',read),patch.object(b,'window_kind',return_value=None),             patch.object(worn,'leave_blessing_screen',side_effect=lambda *a:left.append(1)),patch.object(b,'watch',return_value=[]),             patch.object(b,'skip_reason',side_effect=AssertionError('no tile sweep')):
            result=b.claim(NS(),context,None)
        return result,clicks,left
    def test_pressed_on_the_all_tab(self):
        result,clicks,left=self.run_claim()
        self.assertTrue(result);self.assertEqual(clicks,[hd.real_hit(*b.ALL_TAB)[:2],hd.real_hit(1182,717)[:2]]);self.assertEqual(left,[1])
    def test_no_button_word_presses_nothing(self):
        result,clicks,_=self.run_claim(button=False);self.assertEqual(clicks,[hd.real_hit(*b.ALL_TAB)[:2]])


class Watch(unittest.TestCase):
    def run_watch(self,dialog,tradeable=0,grades=None):
        clicks=[];keys=[];service=NS(capture=lambda:None,check=lambda:None,click_hit=lambda hit:clicks.append(hit[:2]),key=keys.append)
        context=NS(checkpoint=lambda:None,wait=lambda s:None)
        def read(root,frame,box,**k):
            return [dict(text=w,rx=760 if w!='취소' else 700,ry=480) for w in dialog] if box==b.DIALOG else []
        with patch('owner_text.read',read),patch.object(b,'acquire_popup',return_value=tradeable),patch.object(b,'popup_grades',return_value=grades):
            b.watch(service,context,seconds=.05)
        return clicks,keys
    def test_a_claim_using_only_bound_pieces_is_confirmed(self):
        clicks,keys=self.run_watch(['가호를 획득하시겠습니까','확인']);self.assertTrue(clicks);self.assertEqual(set(clicks),{hd.real_hit(760,480)[:2]})
    def test_tradeable_pieces_are_kept(self):
        # The user's rule: anything tradeable stops the claim. 취소, not 확인.
        clicks,keys=self.run_watch(['가호를 획득하시겠습니까','확인','취소'],tradeable=3);self.assertEqual(clicks,[hd.real_hit(700,480)[:2]])
        clicks,keys=self.run_watch(['가호를 획득하시겠습니까','확인'],tradeable=None);self.assertEqual(clicks,[]);self.assertEqual(keys,[0x1b])
    def test_tradeable_pieces_may_go_for_common_and_rare_only(self):
        # User 11-06: 일반·희귀 are claimed even with tradeable pieces; any 영웅 or higher, or an unread grade, is not.
        dialog=['가호를 획득하시겠습니까','확인','취소']
        self.assertEqual(set(self.run_watch(dialog,53,['희귀','일반'])[0]),{hd.real_hit(760,480)[:2]})
        self.assertEqual(self.run_watch(dialog,53,['희귀','영웅'])[0],[hd.real_hit(700,480)[:2]])
        self.assertEqual(self.run_watch(dialog,53,['일반',None])[0],[hd.real_hit(700,480)[:2]])
        self.assertEqual(self.run_watch(dialog,53,None)[0],[hd.real_hit(700,480)[:2]])
    def test_a_sale_window_is_left(self):self.assertEqual(self.run_watch(['판매 후 획득','확인'])[0],[])
    def test_no_window_presses_nothing(self):self.assertEqual(self.run_watch([])[0],[])


class Grades(unittest.TestCase):
    """The 일괄 획득 window's slots drawn as pc1 11-06 showed them: plain ground (50,50,50), slots 56 wide, 73 apart."""
    def frame(self,frames):
        real=np.full((768,1366,3),50,np.uint8)
        for k,colour in enumerate(frames):
            x=540+73*k;real[350:406,x:x+56]=colour;real[362:396,x+12:x+44]=(200,150,90)
        return NS(hi=real)
    def test_grey_is_common_blue_rare_else_high(self):
        self.assertEqual(b.popup_grades(self.frame([(59,56,52),(24,35,66),(120,60,130),(150,110,30)])),['일반','희귀',None,None])
    def test_no_slot_is_unread(self):self.assertIsNone(b.popup_grades(self.frame([])))
    def test_the_saved_window(self):
        import os
        path=os.environ.get('DKB_CLAIM_FRAME')
        if not path:self.skipTest('local frame only')
        from PIL import Image
        self.assertEqual(b.popup_grades(NS(hi=np.asarray(Image.open(path).convert('RGB')))),['일반']*4)


class PolicyAtRealSize(unittest.TestCase):
    """The priority equip still finds its screens by old pictures: at 1366 it is passed over, and the job does not fail."""
    def run_policy(self,real_screen):
        import tempfile,owner_blessing_original_fence_candidate as fence
        from owner_gear_settings_candidate import Store,DEFAULT
        import copy,json
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        document=copy.deepcopy(DEFAULT);document['blessing_equip']={'enabled':True,'priorities':['도깨비']}
        store=Store(directory.name,'who');store.path.parent.mkdir(parents=True,exist_ok=True);store.path.write_text(json.dumps(document,ensure_ascii=False),encoding='utf-8')
        module=NS(run_blessing_rewards=lambda *a:True,_blessing_bulk_skip_reason=lambda *a:None,_blessing_tradeable_candidates=lambda *a:None)
        ran=[]
        fence.install_runtime(module,NS(inspect_growth_equipment=lambda *a,**k:[]),lambda adapter:'who',runner=lambda *a,**k:ran.append(1) or {'state':'ran'})
        adapter=NS(project=NS(root=directory.name))
        with patch.object(fence,'real_screen',return_value=real_screen):
            result=module.run_blessing_rewards(adapter,NS(checkpoint=lambda:None),None)
        return result,ran,adapter._owner_blessing_policy_outcome
    def test_passed_over_at_real_size(self):
        with patch('owner_blessing_bound.claim',return_value=False):
            result,ran,outcome=self.run_policy(True)
        self.assertIs(result,True);self.assertEqual(ran,[]);self.assertEqual(outcome['state'],'skipped_real_screen')
    def test_at_real_size_the_job_is_the_claim_alone(self):
        with patch('owner_blessing_bound.claim',return_value=True) as claim:
            result,ran,outcome=self.run_policy(True)
        claim.assert_called_once();self.assertIs(result,True);self.assertEqual(ran,[]);self.assertEqual(outcome['state'],'bulk_claim_only')
    def test_runs_as_before_at_the_old_size(self):
        result,ran,outcome=self.run_policy(False)
        self.assertEqual(ran,[1]);self.assertEqual(outcome['state'],'ran')


if __name__=='__main__':unittest.main()
