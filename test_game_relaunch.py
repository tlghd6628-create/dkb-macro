"""Game relaunch on fake windows, words and clocks. Not a live claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import threading,unittest
from types import SimpleNamespace as S
import owner_game_relaunch as gr

def row(text,x=100,y=100):return dict(text=text,score=.99,rx=x,ry=y,bounds=(x-20,y-8,x+20,y+8))

class Words(unittest.TestCase):
    def test_launcher_states(self):
        self.assertEqual(gr.launcher_words([row('게임 실행')])[0],'ready')
        kind,r=gr.launcher_words([row('업데이트',1400,765)]);self.assertEqual((kind,r['rx']),('update',1400))
        self.assertEqual(gr.launcher_words([row('다운로드 중 42%')])[0],'busy')
        self.assertEqual(gr.launcher_words([row('파일 검사하기')])[0],None)
    def test_title_states(self):
        self.assertEqual(gr.title_words([row('36%'),row('도깨비의세계로 가는 길을 점검하는 중')])[0],'loading')
        self.assertEqual(gr.title_words([row('36%',684,699)])[0],'loading')
        self.assertEqual(gr.title_words([row('성공 확률 36%',400,620)])[0],None)
        self.assertEqual(gr.title_words([row('화면을 눌러주세요.')])[0],'touch')
        self.assertEqual(gr.title_words([row('화면을 놀러주세요'),row('Kakao Games Corp.')])[0],'touch')
        kind,r=gr.title_words([row('게임 시작',682,580),row('무이2'),row('짱군네')]);self.assertEqual((kind,r['ry']),('start',580))
        self.assertEqual(gr.title_words([row('짱군네')])[0],None)

class Launcher(unittest.TestCase):
    def run_it(self,screens,games_after=None):
        clock=[0.];pressed=[];seen=iter(screens)
        class Win:
            hwnd=1
            def candidates(self):return [dict(hwnd=1)]
        game=S(candidates=lambda:[] if games_after is None or clock[0]<games_after else [1])
        gui=S(official_launcher=S(window=Win()),game_window=game)
        ctx=S(checkpoint=lambda:None,wait=lambda s:clock.__setitem__(0,clock[0]+s))
        got=gr.wait_launcher_ready(gui,ctx,clock=lambda:clock[0],rows=lambda:next(seen),press=pressed.append)
        return got,pressed,clock[0]
    def test_waits_through_an_update_then_ready(self):
        got,pressed,spent=self.run_it([[row('업데이트')],[row('12%')],[row('80%')],[row('게임 실행')]])
        self.assertEqual(got,'ready');self.assertEqual(len(pressed),1);self.assertGreater(spent,10)
    def test_gives_up_after_the_limit(self):
        import itertools
        clock=[0.]
        class Win:
            hwnd=1
            def candidates(self):return [dict(hwnd=1)]
        gui=S(official_launcher=S(window=Win()),game_window=S(candidates=lambda:[]))
        ctx=S(checkpoint=lambda:None,wait=lambda s:clock.__setitem__(0,clock[0]+s))
        with self.assertRaises(RuntimeError):
            gr.wait_launcher_ready(gui,ctx,clock=lambda:clock[0],rows=lambda:[row('50%')],press=lambda r:None)

class Watching(unittest.TestCase):
    def gui(self,games=(),status='stopped'):
        calls=[]
        return S(session=S(snapshot=lambda:dict(status=status,worker_alive=False)),game_window=S(candidates=lambda:list(games)),
                 official_launcher=S(configured=True),input_preparation=S(before_start=lambda cb:calls.append('start')),
                 action=lambda cb:None,closed=threading.Event()),calls
    def record(self,w,text):
        import logging;w.emit(logging.makeLogRecord(dict(msg=text,args=())))
    def test_error_end_without_a_game_relaunches_spaced_and_capped(self):
        gui,calls=self.gui();w=gr.Watch(gui)
        self.record(w,"자동 동작 종료: (1400, 'ClientToScreen', '잘못된 창 핸들입니다.')")
        self.assertTrue(w.check(now=1000));self.assertFalse(w.check(now=1100))
        for t in (1400,1800,2200):self.assertTrue(w.check(now=t))
        self.assertFalse(w.check(now=2600));self.assertEqual(len(calls),4)
    def test_user_stop_and_present_game_never_relaunch(self):
        gui,calls=self.gui();w=gr.Watch(gui)
        self.record(w,'자동 동작 종료: x');self.record(w,'단축키 F3 · stop');self.assertFalse(w.check(now=1))
        gui,calls=self.gui(games=[1]);w=gr.Watch(gui);self.record(w,'자동 동작 종료: x')
        self.assertFalse(w.check(now=1));self.assertIsNone(w.ended)
    def test_game_gone_under_a_run_relaunches_after_a_plain_stop(self):
        """07:46 test: closing the game logged only 사용자 정지."""
        state={'status':'running'};games=[[1]]
        calls=[];gui=S(session=S(snapshot=lambda:dict(status=state['status'],worker_alive=False)),game_window=S(candidates=lambda:games[0]),
            official_launcher=S(configured=True),input_preparation=S(before_start=lambda cb:calls.append('start')),action=lambda cb:None,closed=threading.Event())
        w=gr.Watch(gui);self.assertFalse(w.check(now=100))
        state['status']='stopped';games[0]=[];self.record(w,'사용자 정지')
        self.assertTrue(w.check(now=115));self.assertEqual(calls,['start'])
    def test_stopped_long_ago_without_a_game_is_left_alone(self):
        gui,calls=self.gui();w=gr.Watch(gui);w.live=0
        self.assertFalse(w.check(now=500));self.assertEqual(calls,[])
    def test_running_session_is_left_alone(self):
        gui,calls=self.gui(status='running');w=gr.Watch(gui);self.record(w,'자동 동작 종료: x')
        self.assertFalse(w.check(now=1));self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
