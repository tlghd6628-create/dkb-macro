"""Fixes from the 19:00-21:06 real log. Real saved pages, fake input. Never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import json,logging,tempfile,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
import owner_boss_range as r
F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))

class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.field,cls.opened,cls.low,cls.high=load('hunt_field'),load('hunt_open'),load('hunt_low'),load('hunt_high')
    def test_the_panel_is_told_from_the_field(self):
        self.assertTrue(r.panel_open(self.low));self.assertTrue(r.panel_open(self.opened));self.assertFalse(r.panel_open(self.field))
    def test_the_cog_is_found_on_the_field_only(self):
        self.assertIsNotNone(r.cog(self.field));self.assertIsNone(r.cog(self.low))
    def test_both_switches_read_on(self):
        self.assertEqual(r.read(self.low),{'fixed':True,'range':True})
    def test_rows_are_not_guessed_before_scrolling(self):
        self.assertIsNone(r.read(self.field))
    def test_the_knob_is_found_at_each_end(self):
        self.assertLess(r.handle(self.low),740);self.assertGreater(r.handle(self.high),835)
    def test_five_and_thirty_are_told_apart(self):
        self.assertTrue(r.shows(self.low,'low'));self.assertFalse(r.shows(self.low,'high'))
        self.assertTrue(r.shows(self.high,'high'));self.assertFalse(r.shows(self.high,'low'))

def flipped(frame,key):
    """The same page with one switch on its other side."""
    out=frame.copy();left,right,y=r.locate(frame)[key]
    for a,b in ((left,right),):
        one=frame[y-5:y+5,a-13:a+13].copy();two=frame[y-5:y+5,b-13:b+13].copy()
        out[y-5:y+5,a-13:a+13]=two;out[y-5:y+5,b-13:b+13]=one
    return out

class Game:
    """Panel behaviour over real pages: the switch and slider states pick the page shown."""
    def __init__(self,fixed=True,slider='low',opened=False):
        self.fixed,self.slider,self.opened=fixed,slider,opened;self.actions=[]
        self.field,self.low,self.high=load('hunt_field'),load('hunt_low'),load('hunt_high')
        self.context=S(checkpoint=lambda:None,wait=lambda seconds:None,stop=threading.Event())
    def frame(self):
        if not self.opened:return self.field
        page=self.high if self.slider=='high' else self.low
        return page if self.fixed else flipped(page,'fixed')
    def click(self,x,y,proof):
        self.actions.append(('click',x,y))
        if not proof(self.frame()):raise AssertionError('guard refused')
        if not self.opened:self.opened=True;return
        if y>=430 or (x>870 and y<70):self.opened=False;return
        self.fixed=x>760
    def drag(self,start,end,proof):
        self.actions.append(('drag',start,end));self.slider='high' if end[0]>start[0] else 'low'
    def wheel(self,*a,**k):self.actions.append(('wheel',))

class Flow(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        (Path(self.dir.name)/'settings').mkdir()
        self.adapter=S(project=S(root=Path(self.dir.name)),exit_sleep_mode=Mock())
    def run_with(self,game,call):
        with patch.object(r,'_ui',lambda *a:game):return call(self.adapter,game.context,None)
    def test_before_the_boss_it_frees_and_widens_then_closes(self):
        game=Game()
        self.assertTrue(self.run_with(game,r.loosen))
        self.assertEqual((game.fixed,game.slider,game.opened),(False,'high',False))
        self.adapter.exit_sleep_mode.assert_called_once()
        self.assertEqual(r.pending(self.adapter.project.root)['fixed'],True)
    def test_after_the_boss_it_fixes_and_returns_to_five(self):
        game=Game();self.run_with(game,r.loosen)
        self.assertTrue(self.run_with(game,r.restore))
        self.assertEqual((game.fixed,game.slider,game.opened),(True,'low',False))
        self.assertIsNone(r.pending(self.adapter.project.root))
    def test_hunting_always_comes_back_fixed_at_five(self):
        game=Game(fixed=False);self.run_with(game,r.loosen);self.run_with(game,r.restore)
        self.assertEqual((game.fixed,game.slider),(True,'low'))
    def test_a_second_boss_call_keeps_the_original_record(self):
        game=Game();self.run_with(game,r.loosen);self.run_with(game,r.loosen)
        self.assertEqual(r.pending(self.adapter.project.root)['fixed'],True)
    def test_nothing_to_restore_sends_no_input(self):
        game=Game();self.assertFalse(self.run_with(game,r.restore));self.assertEqual(game.actions,[])
    def test_a_failure_never_stops_the_boss(self):
        game=Game()
        def bad(*a,**k):raise RuntimeError('화면 변경')
        game.click=bad
        self.assertFalse(self.run_with(game,r.loosen))
    def test_a_failed_restore_stays_recorded(self):
        game=Game();self.run_with(game,r.loosen)
        def bad(*a,**k):raise RuntimeError('화면 변경')
        game.click=bad
        self.assertFalse(self.run_with(game,r.restore));self.assertIsNotNone(r.pending(self.adapter.project.root))
    def test_a_restore_away_from_the_field_waits(self):
        game=Game();self.run_with(game,r.loosen)
        game.field=np.zeros_like(game.field);game.actions.clear()
        self.assertFalse(self.run_with(game,r.restore));self.assertEqual(game.actions,[])
        self.assertIsNotNone(r.pending(self.adapter.project.root))
    def test_a_slider_that_did_not_move_is_a_failure(self):
        game=Game();game.drag=lambda *a:None
        self.assertFalse(self.run_with(game,r.loosen));self.assertFalse(game.opened)

class Gate(unittest.TestCase):
    def entry(self,stop=False,raises=None):
        import owner_boss_gate as gate
        from project_adapter._entry import Adapter
        calls=[]
        def native(adapter,context,inputs):
            calls.append('boss')
            if raises:raise raises
            return True
        with patch.object(Adapter,'_run_field_boss_entry',native),patch.object(gate,'allowed',lambda *a:True),\
             patch('owner_boss_range.loosen',lambda *a:calls.append('loosen')),patch('owner_boss_range.restore',lambda *a:calls.append('restore')):
            gate.install();context=S(checkpoint=lambda:None,stop=threading.Event())
            if stop:context.stop.set()
            try:Adapter._run_field_boss_entry(S(),context,None)
            except BaseException as exc:calls.append(type(exc).__name__)
        return calls
    def test_order(self):self.assertEqual(self.entry(),['loosen','boss','restore'])
    def test_restored_on_the_unwind_back_to_hunting(self):
        class ResumeWork(BaseException):pass
        self.assertEqual(self.entry(raises=ResumeWork()),['loosen','boss','restore','ResumeWork'])
    def test_a_stop_leaves_it_for_the_next_start(self):self.assertEqual(self.entry(stop=True),['loosen','boss'])

class Wake(unittest.TestCase):
    def run_it(self,**kwargs):
        from owner_schedule_priority import wake_before_recovery
        native=Mock(return_value='done');stall=S(adapter=S(exit_sleep_mode=Mock()),context='c',inputs='i')
        self.assertEqual(wake_before_recovery(native)(stall,**kwargs),'done')
        return stall.adapter.exit_sleep_mode,native
    def test_an_active_recovery_wakes_first(self):
        wake,native=self.run_it();wake.assert_called_once_with('c','i');native.assert_called_once()
    def test_a_passive_check_leaves_a_sleeping_character_alone(self):
        for kwargs in (dict(verify_only=True),dict(passive_wait=True)):
            wake,_=self.run_it(**kwargs);wake.assert_not_called()
    def test_a_failed_wake_still_recovers(self):
        from owner_schedule_priority import wake_before_recovery
        native=Mock(return_value='done');stall=S(adapter=S(exit_sleep_mode=Mock(side_effect=RuntimeError('x'))),context='c',inputs='i')
        self.assertEqual(wake_before_recovery(native)(stall),'done')
    def test_it_cannot_recurse_through_itself(self):
        from owner_schedule_priority import wake_before_recovery
        calls=[]
        def native(stall,**k):calls.append('recover');return True
        wrapped=wake_before_recovery(native)
        stall=S(context='c',inputs='i');stall.adapter=S(exit_sleep_mode=lambda c,i:wrapped(stall))
        wrapped(stall);self.assertEqual(calls,['recover','recover'])

class HeldLog(unittest.TestCase):
    def line(self,log,text):
        record=logging.LogRecord('x',logging.INFO,'',0,text,None,None);log.filter(record);return record.getMessage()
    def test_a_held_job_is_not_called_complete(self):
        from owner_schedule_priority import HeldEnd
        log=HeldEnd();self.line(log,'자동 기능 시작 · 비경탐험(전래동화-5시간)')
        self.line(log,'자동 기능 보류 · 전래동화 비경 · 보스 출발 시간 충돌 · 21:22 이후 · 전투 종료 후 재확인')
        self.assertEqual(self.line(log,'자동 기능 완료 · 비경탐험(전래동화-5시간)'),'자동 기능 종료 · 비경탐험(전래동화-5시간) · 위 보류 항목은 실행 안 함')
    def test_a_job_that_ran_stays_complete(self):
        from owner_schedule_priority import HeldEnd
        log=HeldEnd();self.line(log,'자동 기능 보류 · A · x');self.line(log,'자동 기능 완료 · A')
        self.line(log,'자동 기능 시작 · B');self.assertEqual(self.line(log,'자동 기능 완료 · B'),'자동 기능 완료 · B')

class PausedSettings(unittest.TestCase):
    def setUp(self):
        import owner_timetable as t
        self.t=t;self.addCleanup(t.LIVE.update,{'adapter':None})
        class Live:pass
        self.plan=S(values={'a':False});self.adapter=Live();self.adapter.values={'a':False};self.adapter._owner_timetable=self.plan
        self.t.planner(self.adapter)
    def test_it_reaches_the_paused_run(self):
        self.assertTrue(self.t.live_settings({'a':True}))
        self.assertTrue(self.adapter.values['a']);self.assertTrue(self.plan.values['a'])
    def test_a_job_on_masked_values_gets_it_when_they_return(self):
        real=self.adapter.values;self.adapter.values={'a':False}
        self.t.live_settings({'a':True});self.assertFalse(real['a'])
        self.adapter.values=real;self.t.planner(self.adapter);self.assertTrue(real['a'])
    def test_no_run_is_a_plain_false(self):
        self.t.LIVE['adapter']=None;self.assertFalse(self.t.live_settings({'a':True}))
    def test_saving_is_refused_only_while_it_really_runs(self):
        import inspect,owner_settings_console as c
        source=next(inspect.getsource(v.save) for v in vars(c).values() if inspect.isclass(v) and hasattr(v,'save') and '일시정지' in inspect.getsource(v.save))
        self.assertIn("state.get('status')=='running'",source);self.assertIn('not paused',source)

class Mission(unittest.TestCase):
    def test_a_proved_finish_is_saved_as_done(self):
        import inspect,owner_membership as m
        from owner_timetable import LABEL_JOB
        key=LABEL_JOB['일일 임무']
        source=inspect.getsource(m.install)
        self.assertLess(source.index('전체 완료 확인'),source.index("report(adapter,'%s'"%key))
        self.assertIn("timetable,'job',None)=='%s'"%key,source)
    def test_done_keeps_it_from_reopening_at_the_next_start(self):
        from owner_outcome import DONE,FINISHED,Outcome,classify,report
        from owner_timetable import LABEL_JOB
        key=LABEL_JOB['일일 임무']
        adapter=S();report(adapter,key,Outcome(DONE,'x'))
        self.assertIn(classify(key,adapter,None).kind,FINISHED)
        self.assertIsNone(classify(key,adapter,None))

class RewardWrappers(unittest.TestCase):
    """The 20:19 and 21:23 real mail failures: native recovery re-binding what it was handed."""
    def flow(self):return S(seconds={'read':0})
    def test_rebinding_find_does_not_loop(self):
        from owner_reward_flow import FlowDetector
        class Real:
            def find(self,name):return 'hit:'+name
        real=Real();wrapper=FlowDetector(self.flow(),real)
        original=wrapper.find
        wrapper.find=lambda *a,**k:'bound:'+original(*a,**k)
        self.assertEqual(wrapper.find('x'),'bound:hit:x')
        self.assertEqual(real.find('x'),'hit:x')
    def test_a_real_settings_attribute_still_reaches_the_real_object(self):
        from owner_reward_flow import FlowDetector
        class Real:pass
        real=Real();wrapper=FlowDetector(self.flow(),real);wrapper.limit=3
        self.assertEqual(real.limit,3)
    def test_rebinding_click_stays_on_the_wrapper(self):
        from owner_reward_flow import FlowInputs
        real=S(click=Mock());wrapper=FlowInputs(self.flow(),real)
        marker=lambda *a,**k:'bound';wrapper.click=marker
        self.assertIsInstance(real.click,Mock);self.assertEqual(wrapper.click(1,2),'bound')

class ZeroDungeonRestart(unittest.TestCase):
    def test_a_read_zero_is_not_rechecked_at_every_start(self):
        import inspect,owner_timetable as t
        source=inspect.getsource(t.Planner)
        self.assertIn("status=='processed' and row.get('no_time_left_at') and not row.get('result_unverified')",source)

class EarlyF1(unittest.TestCase):
    """22:59 real run: F1 during OCR warm-up left the macro stopped with no message."""
    def gui(self,ready=False,status='stopped',worker=False):
        calls=[];later=[]
        gui=S(closed=threading.Event(),_owner_ocr_readiness=S(done=threading.Event()),calls=calls,later=later,
              session=S(snapshot=lambda:{'status':status,'worker_alive':worker},stop=lambda:None),
              root=S(after=lambda ms,fn:later.append(fn)),start_requested=lambda:calls.append('start'),action=lambda fn:fn())
        if ready:gui._owner_ocr_readiness.done.set()
        return gui
    def press(self,gui,key='F1'):
        from owner_controls import run_command
        return run_command(gui,key)
    def drain(self,gui):
        while gui.later:gui.later.pop(0)()
    def test_started_again_once_ready(self):
        gui=self.gui();self.press(gui);self.assertEqual(gui.calls,['start'])
        gui.later.pop(0)();self.assertEqual(gui.calls,['start'])
        gui._owner_ocr_readiness.done.set();self.drain(gui)
        self.assertEqual(gui.calls,['start','start'])
    def test_ready_means_one_plain_start(self):
        gui=self.gui(ready=True);self.press(gui);self.assertEqual(gui.calls,['start']);self.assertEqual(gui.later,[])
    def test_f3_cancels_the_waiting_start(self):
        gui=self.gui();self.press(gui);self.press(gui,'F3');gui._owner_ocr_readiness.done.set();self.drain(gui)
        self.assertEqual(gui.calls,['start'])
    def test_a_start_that_already_took_is_not_repeated(self):
        from owner_controls import start_when_ready
        gui=self.gui(status='running');token=object();gui._owner_start_token=token
        start_when_ready(gui,token);self.assertEqual(gui.calls,[]);self.assertEqual(gui.later,[])

class SideJob(unittest.TestCase):
    def test_only_the_side_job_stop_is_absorbed(self):
        import inspect,owner_task_flow as t
        source=inspect.getsource(t)
        self.assertIn("if '처리 중단' not in str(exc):raise",source)

if __name__=='__main__':unittest.main()
