"""Town return and the event window at 1366x768, from arrays and the words the reader gives. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,unittest,threading
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from biol_base.session import Context,Cancelled
import owner_hd as hd
hd.install_reading()
import owner_image_scope as scope
import owner_movement as m
import owner_reward_flow as flow
import owner_reward_visual_guard as guard


def word(text,x,y,score=.99,w=40):
    rx,ry=round(x*1.6-34.6),round(y*1.6)
    return dict(text=text,score=score,rx=rx,ry=ry,x=x,y=y,bounds=(rx-w,ry-10,rx+w,ry+10))


def real_frame(fill=(120,90,60)):
    return hd.make_frame(np.full((768,1366,3),fill,np.uint8),hd._PLAIN)


def window_frame():
    frame=real_frame();x,y,w,h=m.METHOD_TITLE
    frame.hi[y:y+h,x:x+w]=(38,38,40)
    return frame


TITLE=[word('자동 이동 방법 선택',448,160),word('×',538,159)]
BODY=TITLE+[word('거리 : 311m',454,209),word('목적지 근처로 축지술을 사용합니다.',448,238),word('축지술',403,306),word('축지부 사용',494,306)]


def reads(*answers):
    """owner_text.read giving the title rows first, then the body rows."""
    return patch('owner_text.read',side_effect=list(answers))


class MethodWindow(unittest.TestCase):
    def test_button_is_the_exact_word_and_not_its_sentence_or_neighbour(self):
        with reads(TITLE,BODY):hit=m.teleport_word(window_frame())
        self.assertEqual(hit[:2],(403,306));self.assertTrue(hit[2][0]<403<hit[2][2] and hit[2][1]<306<hit[2][3])
    def test_close_spelling_presses_nothing(self):
        rows=[r if r['text']!='축지술' else word('축지슬',403,306) for r in BODY]
        with reads(TITLE,rows):self.assertIsNone(m.teleport_word(window_frame()))
    def test_only_the_item_button_presses_nothing(self):
        rows=[r for r in BODY if r['text']!='축지술']
        with reads(TITLE,rows):self.assertIsNone(m.teleport_word(window_frame()))
    def test_two_of_the_button_press_nothing(self):
        with reads(TITLE,BODY+[word('축지술',450,306)]):self.assertIsNone(m.teleport_word(window_frame()))
    def test_another_window_is_not_this_one(self):
        with reads([word('이벤트',448,160)]):self.assertIsNone(m.teleport_word(window_frame()))
    def test_a_bright_bar_is_not_read_at_all(self):
        with patch('owner_text.read',side_effect=AssertionError('no reading')):self.assertIsNone(m.method_rows(real_frame((200,180,160))))
    def test_brown_ground_is_not_read_at_all(self):
        with patch('owner_text.read',side_effect=AssertionError('no reading')):self.assertIsNone(m.method_rows(real_frame((60,40,20))))
    def test_window_has_the_places_the_old_code_uses(self):
        with reads(TITLE,BODY):w=m.method_window(window_frame())
        self.assertEqual(w['title'],(399,152));self.assertEqual(w['close'],(538,159));self.assertEqual(w['button'],(387,301))
    def test_close_falls_back_to_its_place_when_the_x_does_not_read(self):
        rows=[r for r in BODY if r['text']!='×']
        with reads(TITLE,rows):self.assertEqual(m.method_window(window_frame())['close'],(538,159))
    def test_distance_comes_from_the_words_read(self):
        w={'title':(399,152),'rows':BODY}
        self.assertEqual(m.method_distance(None,w),311.0)
    def test_a_doubtful_distance_stays_unknown(self):
        self.assertIsNone(m.method_distance(None,{'rows':[word('거리 : 311m',454,209,score=.9)]}))
    def test_frame_without_real_pixels_keeps_the_pictures(self):
        frame=np.zeros((479,897,3),np.uint8)
        with patch('owner_text.read',side_effect=AssertionError('no reading')):self.assertIsNone(m.method_window(frame))


class Detector(unittest.TestCase):
    def detector(self):
        e=dict(type='template',x=433,y=299,w=32,h=11)
        return S(profile=Path('unused'),entries={'버튼_축지술_가운데':e,'버튼_귀환':e},templates={'버튼_축지술_가운데':np.zeros((11,32,3),np.uint8),'버튼_귀환':np.zeros((11,32,3),np.uint8)},masks={})
    def test_the_native_name_answers_from_the_words(self):
        with patch.object(m,'teleport_word',return_value=(403,306,(387,300,420,312))),patch.object(scope,'note'):
            self.assertEqual(scope.recover(self.detector(),'버튼_축지술_가운데',real_frame(),None,.9,None)[:2],(403,306))
    def test_the_native_filter_still_decides(self):
        with patch.object(m,'teleport_word',return_value=(403,306,(387,300,420,312))),patch.object(scope,'note'):
            self.assertIsNone(scope.recover(self.detector(),'버튼_축지술_가운데',real_frame(),None,.9,lambda f,h:False))
    def test_nothing_read_is_no_hit_and_no_softer_look(self):
        with patch.object(m,'teleport_word',return_value=None),patch.object(scope,'unique_peak',side_effect=AssertionError('no picture')):
            self.assertIsNone(scope.recover(self.detector(),'버튼_축지술_가운데',real_frame(),None,.9,None))
    def test_home_word_clicks_the_icon_above_it(self):
        row=dict(text='Home',score=.99,rx=1012,ry=739,x=676,y=462,bounds=(995,732,1030,746))
        with patch('owner_text.read',return_value=[row]):hit=m.home_word(real_frame())
        self.assertTrue(abs(hd.to_real_point(hit[0],hit[1],hd._PLAIN)[1]-719)<=1)
    def test_home_needs_exactly_that_word(self):
        with patch('owner_text.read',return_value=[word('H',640,462)]):self.assertIsNone(m.home_word(real_frame()))


class EventLayout(unittest.TestCase):
    def marks(self):
        return {row['label']:(row,hd._load(key,row,False)) for key,row in hd.index().items() if row.get('label') in hd.WINDOW_MARKS['event']}
    def scene(self,seed=3):
        return np.random.default_rng(seed).integers(0,255,(768,1366,3),np.uint8)
    def paint(self,real,label):
        row,cut=self.marks()[label];h,w=cut.shape[:2];real[row['y']:row['y']+h,row['x']:row['x']+w]=cut
    def test_the_title_names_the_window_on_any_tab(self):
        real=self.scene();self.paint(real,'native:체크_이벤트')
        self.assertEqual(hd.classify(real).name,'event')
    def test_the_x_names_it_when_a_card_covers_the_title(self):
        real=self.scene();self.paint(real,'native:버튼_X_이벤트창')
        self.assertEqual(hd.classify(real).name,'event')
    def test_no_mark_is_no_event_window(self):
        real=self.scene();self.assertIsNone(hd.marked_window(real));self.assertNotEqual(hd.classify(real).name,'event')
    def test_the_whole_inside_holds_the_middle_anchor(self):
        layout=next(l for l in hd.layouts() if l.name=='event')
        for x,y in ((724,100),(650,340),(700,380),(290,246),(170,390)):self.assertEqual(layout.rule(x,y),'center',(x,y))
        self.assertEqual(layout.rule(860,20),'right');self.assertEqual(layout.rule(20,20),'left')
    def test_the_field_map_is_what_tore_it(self):
        field=hd.default_layout()
        self.assertEqual(field.rule(724,100),'right');self.assertEqual(field.rule(680,345),'right')
    def test_a_click_on_the_x_lands_on_it(self):
        layout=next(l for l in hd.layouts() if l.name=='event')
        self.assertEqual(hd.to_real_point(724,101,layout),(1124,162))


def dot(real,cx,cy):
    """A dot of the size and shape measured on the real event screen: a red diamond, nine pixels across."""
    for dy in range(-4,5):
        for dx in range(-4,5):
            if abs(dx)+abs(dy)<=4:real[cy+dy,cx+dx]=(235,60,50)


class Dots(unittest.TestCase):
    def frame(self,*dots,fill=(70,66,60)):
        real=np.full((768,1366,3),fill,np.uint8)
        for at in dots:dot(real,*at)
        return hd.make_frame(real,next(l for l in hd.layouts() if l.name=='event'))
    def test_a_tab_dot_is_not_a_reward_dot(self):
        # (428,393) is the 도사 성장 미션 tab: (289,246), left of the reward area.
        self.assertEqual(guard.notice_dots(self.frame((428,393))),[])
    def test_a_row_dot_still_is(self):
        found=guard.notice_dots(self.frame((428,393),(914,456)))
        self.assertEqual(len(found),1);self.assertTrue(abs(found[0][0]-593)<=1 and abs(found[0][1]-285)<=1,found)
    def test_right_of_the_window_is_not_a_reward_dot(self):
        self.assertEqual(guard.notice_dots(self.frame((1145,456))),[])
    def test_a_red_block_of_that_size_is_not_a_dot(self):
        frame=self.frame();frame.hi[450:460,900:910]=(235,60,50)
        self.assertEqual(guard.notice_dots(frame),[])


class Points(unittest.TestCase):
    def answer(self,title,total,need,box=(635,325,666,355)):
        def read_area(root,area,*,left=0,top=0,**k):
            if (left,top)==guard.POINT_TITLE[:2]:return [dict(text=title)]
            if (left,top)==guard.POINT_TOTAL[:2]:return [dict(text=t) for t in total]
            return [dict(text=t) for t in need]
        with patch('owner_text.read_area',read_area):return guard.short_of_points(real_frame(),box)
    def test_six_of_four_is_short(self):self.assertTrue(self.answer('누적 포인트',['4'],['6']))
    def test_two_of_four_is_not(self):self.assertFalse(self.answer('누적 포인트',['4'],['2']))
    def test_equal_is_not(self):self.assertFalse(self.answer('누적 포인트',['4'],['4']))
    def test_a_misread_number_decides_nothing(self):
        self.assertFalse(self.answer('누적 포인트',['4'],['O']));self.assertFalse(self.answer('누적 포인트',[],['6']))
    def test_another_tab_decides_nothing(self):self.assertFalse(self.answer('21일차',['4'],['6']))
    def test_left_of_the_panel_decides_nothing(self):
        with patch('owner_text.read_area',side_effect=AssertionError('no reading')):
            self.assertFalse(guard.short_of_points(real_frame(),(379,244,414,278)))
    def test_small_frame_decides_nothing(self):
        self.assertFalse(guard.short_of_points(np.zeros((479,897,3),np.uint8),(635,325,666,355)))


class Receipt(unittest.TestCase):
    def test_the_words_are_a_receipt(self):
        with patch('owner_text.read_area',return_value=[dict(text='보상 받기')]):self.assertTrue(flow.receipt_words(real_frame()))
    def test_the_window_title_is_not(self):
        with patch('owner_text.read_area',return_value=[dict(text='이벤트')]):self.assertFalse(flow.receipt_words(real_frame()))
    def test_a_reader_failure_is_not_a_receipt(self):
        with patch('owner_text.read_area',side_effect=RuntimeError('x')):self.assertFalse(flow.receipt_words(real_frame()))
    def test_a_small_frame_is_not_read(self):
        with patch('owner_text.read_area',side_effect=AssertionError('no reading')):self.assertFalse(flow.receipt_words(np.zeros((479,897,3),np.uint8)))


class Inputs:
    def __init__(self):self.sent=[];self.guards=True
    def click(self,x,y,*,bounds=None,before_down=None):
        if self.guards and before_down:before_down()
        self.sent.append((x,y))


def context():
    c=Context(threading.Event(),threading.Event());c.wait=lambda s:None;return c


class Leaving(unittest.TestCase):
    """The window by its words, wherever the reward flow gave up."""
    def run_close(self,shown,**k):
        inputs=Inputs();frame=real_frame()
        with patch('owner_start_menu.word_window',side_effect=shown):
            result=flow.close_left_window(lambda:frame,inputs,context(),**k)
        return result,inputs.sent
    def test_an_open_window_is_closed_by_its_x(self):
        seen=[('이벤트',(724,101)),('이벤트',(724,101)),None]
        result,sent=self.run_close(seen)
        self.assertTrue(result);self.assertEqual(sent,[(724,101)])
    def test_nothing_open_sends_nothing(self):
        result,sent=self.run_close([None]);self.assertTrue(result);self.assertEqual(sent,[])
    def test_a_window_that_will_not_close_stops_trying(self):
        result,sent=self.run_close(lambda f:('이벤트',(724,101)));self.assertFalse(result);self.assertEqual(sent,[(724,101)]*3)
    def test_a_window_gone_at_the_press_sends_nothing(self):
        result,sent=self.run_close([('이벤트',(724,101)),None]);self.assertFalse(result);self.assertEqual(sent,[])
    def test_a_card_over_the_title_goes_with_the_window_margin(self):
        event=next(l for l in hd.layouts() if l.name=='event')
        frame=hd.make_frame(np.full((768,1366,3),(70,66,60),np.uint8),event);field=real_frame();now=[frame,frame,field]
        inputs=Inputs()
        with patch('owner_start_menu.word_window',return_value=None):
            self.assertTrue(flow.close_left_window(lambda:now.pop(0),inputs,context()))
        self.assertEqual(inputs.sent,[flow.BLANKS[0]])
    def test_a_small_frame_is_left_to_the_native_close(self):
        inputs=Inputs()
        with patch('owner_start_menu.word_window',side_effect=AssertionError('no reading')):
            self.assertTrue(flow.close_left_window(lambda:np.zeros((479,897,3),np.uint8),inputs,context()))
        self.assertEqual(inputs.sent,[])


class Tracked(unittest.TestCase):
    def run_flow(self,function,key='event'):
        closed=[];kwargs=dict(detector=S(profile=Path('unused/profiles/DKB')),capture=lambda:np.zeros((479,897,3),np.uint8),inputs=Inputs(),context=context())
        with patch.object(flow,'close_left_window',lambda *a:closed.append(a)),patch.object(flow.Flow,'finish',return_value='failed'):
            try:result=flow.tracked(key,function,None,(),kwargs)
            except Exception as exc:result=exc
        return result,closed
    def test_a_flow_that_gave_up_closes_and_still_reports(self):
        def native(**k):raise RuntimeError('이벤트 단계 진행 불가 · 재탐색 한도 초과')
        result,closed=self.run_flow(native)
        self.assertIsInstance(result,RuntimeError);self.assertEqual(len(closed),1)
    def test_a_flow_that_finished_also_looks(self):
        result,closed=self.run_flow(lambda **k:True);self.assertTrue(result);self.assertEqual(len(closed),1)
    def test_a_stop_sends_nothing_more(self):
        def native(**k):raise Cancelled()
        result,closed=self.run_flow(native);self.assertIsInstance(result,Cancelled);self.assertEqual(closed,[])
    def test_other_rewards_are_not_touched(self):
        result,closed=self.run_flow(lambda **k:True,'mail');self.assertEqual(closed,[])


if __name__=='__main__':unittest.main()
