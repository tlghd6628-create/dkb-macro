"""Original selector over fake OCR, and cycle/persistence over fake actions."""
from pathlib import Path
import sys,unittest,tempfile,threading,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
from biol_base.session import Context,Cancelled
from tools.gui_settings import fields
from tools import time_ocr
import project_adapter.secret_exploration as native
import project_adapter.secret_folktale as tale
import owner_dungeon_reentry as r
import owner_timetable as t

class NoInput:
    policy=S(require_ready=lambda *a,**k:None)
    def __getattr__(self,n):
        def deny(*a,**k):raise AssertionError('No actual input: '+n)
        return deny

class NativeSelector(unittest.TestCase):
    def setUp(self):
        import logging
        logger=logging.getLogger('project_gui.DKB');old=logger.level;logger.setLevel(logging.INFO);self.addCleanup(logger.setLevel,old)
    def probe(self,cls,args,seconds):
        import numpy as np
        schema=json.loads((bootstrap.A/'profiles/DKB/config/gui-schema.json').read_text(encoding='utf8'))
        values={f['id']:f.get('default') for f in fields(schema)}
        calls=[]
        class Probe(cls):
            def check(self):pass
            def wait(self,*a):pass
            def button(self,n,*a,**k):calls.append(n);return (1,1,(0,0,2,2))
            def point(self,n):calls.append(n)
            def detect(self,*a,**k):return (1,1,(0,0,2,2))
            def select_stage(self):calls.append('select_stage')
            def selection_ready(self,*a):return True
            def leave(self):calls.append('leave')
        ctx=Context(threading.Event(),threading.Event());ctx.wait=lambda _:ctx.checkpoint()
        adapter=S(values=values,project=S(root=bootstrap.A,code='DKB',app_id='DKB'),mode='auto_mode',status=Mock())
        flow=Probe(adapter,ctx,NoInput(),*args)
        import logging
        old=flow.log.level;flow.log.setLevel(logging.INFO);self.addCleanup(flow.log.setLevel,old)
        flow.capture=lambda:np.zeros((479,897,3),np.uint8);flow.service.capture=flow.capture;flow.service.check=lambda:None
        reads=[time_ocr.TimeRead(True,'%02d:%02d:%02d'%(v//3600,(v//60)%60,v%60),v) for v in seconds]
        with patch.object(time_ocr,'read_time_region',side_effect=reads) as reader:
            result=r.wrap_select(cls.select)(flow,read_time=True)
        return result,flow,calls,reader.call_count
    def test_original_daily_base_zero_plus_extra_time_is_not_exhausted(self):
        result,f,_,n=self.probe(native.Exploration,(),[0,3600])
        self.assertTrue(result);self.assertEqual(f.total,3600);self.assertFalse(getattr(f,'_owner_quota_zero',False));self.assertEqual(n,2)
    def test_original_daily_both_zero_is_exhausted_without_entry(self):
        result,f,calls,_=self.probe(native.Exploration,(),[0,0])
        self.assertFalse(result);self.assertTrue(f._owner_quota_zero);self.assertNotIn('버튼_비경_입장',calls)
    def test_original_weekly_zero_uses_the_original_selector_and_does_not_enter(self):
        result,f,calls,n=self.probe(tale.FolktaleExploration,('5h',),[0])
        self.assertFalse(result);self.assertTrue(f._owner_quota_zero);self.assertEqual(n,1);self.assertNotIn('버튼_비경_전래동화_입장',calls)
    def test_native_enter_reports_confirmed_success_to_the_cycle(self):
        calls=[]
        class Probe(native.Exploration):
            def check(self):pass
            def wait(self,*a):pass
            def button(self,n,*a,**k):calls.append(n);return (1,1,(0,0,2,2))
            def detect(self,*a,**k):return (1,1,(0,0,2,2))
            def point(self,n):calls.append(n)
            def select(self,read_time):self.total=3600;return True
            def confirm_entry(self,*a,**k):calls.append('confirmed');return True
        adapter=S(project=S(root=bootstrap.A,code='DKB',app_id='DKB'),values={},mode='auto_mode',status=Mock(),prepare_auto_mode=Mock(return_value=True))
        ctx=Context(threading.Event(),threading.Event());ctx.wait=lambda _:ctx.checkpoint()
        f=Probe(adapter,ctx,NoInput())
        with patch.object(r,'save_record'),patch.object(native,'ensure_auto_active',return_value=True),patch('project_adapter.auto_mode.ensure_auto_active',return_value=True):
            result=r.wrap_enter(native.Exploration.enter)(f,read_time=True)
        self.assertIs(result,True);self.assertTrue(f._owner_entry_seen);self.assertIn('confirmed',calls)
        self.assertEqual(f.location,'inside')

class Cycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=bootstrap.T/'test_scratch');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'settings').mkdir()
        (self.root/'settings/manager_identity.json').write_text('{"server_name":"s","character_name":"one"}')
        self.context=Context(threading.Event(),threading.Event());self.context.wait=lambda _:self.context.checkpoint()
        self.values={prefix+'.enabled':True for prefix in r.KEYS.values()}
        self.adapter=S(project=S(root=self.root,code='DKB'),values=self.values,mode='sub_quest')
        self.events=[];self.runs=[];self.done=[]
        self.patches=[patch.object(r,'kind_of',lambda f:f.kind),patch.object(r,'field_ready',return_value=True),
                      patch('owner_timetable.character_mismatch',return_value=False),
                      patch.object(r,'completed',lambda a,k,s:self.done.append((k,s))),
                      patch.object(r,'make_flow',side_effect=lambda a,c,i,k,budget=None:self.flow(k,budget))]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        r.LOCAL.active=False
    def flow(self,kind,budget=None):
        outer=self
        class Flow:
            def __init__(self):self.adapter=outer.adapter;self.context=outer.context;self.inputs=NoInput();self.kind=kind;self.total=None;self.spent=0
            def select(self,read_time):
                self.event=outer.events.pop(0);self.total=self.event['total'];return self.total>0
            def enter(self,read_time=True):return self.select(read_time=read_time)
            def remaining(self):return max(0,self.total-self.spent)
            def native_run(self):
                outer.runs.append(kind)
                if not self.enter(read_time=True):return False
                self.spent=self.event.get('spent',0)
                if self.event.get('stop'):raise Cancelled()
                return True
        Flow.select=r.wrap_select(Flow.select);Flow.enter=r.wrap_enter(Flow.enter);Flow.run=r.wrap_run(Flow.native_run)
        f=Flow()
        if budget is not None:f._owner_goal_budget=budget
        return f
    def leaving(self,scenes):
        """The native loop only sleeps out its timer; scenes are what the watcher reads."""
        self.scenes=list(scenes);self.reads=0
        def scene(detector,frame):
            self.reads+=1
            return self.scenes.pop(0) if self.scenes else 'dungeon'
        for p in (patch.object(r,'LEAVE_READ_SECONDS',0),patch.object(r,'LEAVE_SETTLE_SECONDS',0),
                  patch.object(r,'leave_reader',return_value=S(detector=None,capture=lambda:None)),
                  patch('owner_startup_stage.scene',scene)):
            p.start();self.addCleanup(p.stop)
    def sleeping_flow(self,kind,ticks=6):
        flow=self.flow(kind);native_run=type(flow).native_run
        def run(f):
            result=native_run(f)
            for _ in range(ticks):f.context.wait(1)
            return result
        type(flow).run=r.wrap_run(run)
        return flow
    def test_being_removed_midway_is_noticed_and_reenters_at_once(self):
        # 16:55 real case: the character was back in the field, and the native
        # loop would have kept waiting out the remaining hour.
        self.leaving(['field','field','field']);self.events=[{'total':3000},{'total':0}]
        before=self.context.wait
        self.assertIs(self.sleeping_flow('daily').run(),True)
        self.assertEqual(self.runs,['daily','daily']);self.assertEqual(self.done,[('daily','exhausted')])
        self.assertIs(self.context.wait,before)
    def test_weekly_and_a_24h_goal_are_watched_too(self):
        self.leaving(['field','field','field']);self.events=[{'total':3000},{'total':0}]
        self.sleeping_flow('weekly').run();self.assertEqual(self.done,[('weekly','exhausted')])
        self.done.clear();self.runs.clear()
        self.leaving(['field','field','field']);self.events=[{'total':3600,'spent':900},{'total':3600,'spent':2700}]
        self.sleeping_flow('daily24').run();self.assertEqual(self.done,[('daily24','goal_complete')])
    def test_a_passing_field_read_is_not_an_exit(self):
        self.leaving(['field','field','dungeon','field','field','unknown']);self.events=[{'total':3000},{'total':0}]
        flow=self.sleeping_flow('daily',ticks=6);flow.run()
        self.assertEqual(self.runs,['daily','daily'])  # the native timer ended it, not the watcher
    def test_no_reading_while_the_native_flow_is_leaving_or_recovering(self):
        for busy in ({'_owner_native_busy':1},{'death_resupply_pending':True},{'_owner_entered_at':None}):
            flow=S(context=self.context,**{'_owner_entered_at':0.,**busy})
            with patch.object(r,'LEAVE_SETTLE_SECONDS',0):self.assertFalse(r.watching(flow),busy)
    def test_entry_loading_gets_time_to_settle(self):
        import time
        flow=S(context=self.context,_owner_entered_at=time.monotonic());self.assertFalse(r.watching(flow))
    def test_stop_during_watch_still_stops(self):
        self.leaving(['field']);self.events=[{'total':3000}]
        flow=self.sleeping_flow('daily');self.context.stop.set()
        with self.assertRaises(Cancelled):flow.run()
    def test_daily_exit_immediately_repeats_same_entry_until_native_zero(self):
        self.events=[{'total':300},{'total':200},{'total':0}]
        self.assertIs(self.flow('daily').run(),True)
        self.assertEqual(self.runs,['daily']*3);self.assertEqual(self.done,[('daily','exhausted')]);self.assertEqual(r.valid_record(self.adapter)['state'],'exhausted')
    def test_weekly_does_the_same_without_a_three_hour_wait(self):
        self.events=[{'total':100},{'total':0}];self.flow('weekly').run()
        self.assertEqual(self.runs,['weekly']*2);self.assertEqual(self.done,[('weekly','exhausted')])
    def test_unread_initial_time_stays_unfinished_and_does_not_start_quests(self):
        # Simulate a native run returning with no confirmed entry/zero.
        flow=self.flow('daily')
        with self.assertRaises(r.ReentryPending):r.wrap_run(lambda f:False)(flow)
        self.assertEqual(self.done,[]);self.assertEqual(r.valid_record(self.adapter)['state'],'time_unverified')
    def test_changed_or_blocked_field_cannot_reenter(self):
        self.events=[{'total':100}]
        with patch.object(r,'field_ready',return_value=False),self.assertRaises(r.ReentryPending):self.flow('daily').run()
        self.assertEqual(len(self.runs),1);self.assertEqual(self.done,[])
    def test_stop_never_reenters_or_marks_complete(self):
        self.events=[{'total':100,'stop':True}]
        with self.assertRaises(Cancelled):self.flow('daily').run()
        self.assertEqual(len(self.runs),1);self.assertEqual(self.done,[])
    def test_daily24_reentry_preserves_only_the_unspent_target(self):
        self.events=[{'total':3600,'spent':900},{'total':3600,'spent':2700}]
        self.flow('daily24').run()
        self.assertEqual(self.runs,['daily24']*2);self.assertEqual(self.done,[('daily24','goal_complete')]);self.assertEqual(r.valid_record(self.adapter)['budget'],0)
    def test_tale24_finished_goal_never_reenters(self):
        self.events=[{'total':3600,'spent':3600}];self.flow('tale24').run()
        self.assertEqual(len(self.runs),1);self.assertEqual(self.done,[('tale24','goal_complete')])
    def test_zero_saved_goal_sends_no_entry(self):
        self.flow('daily24',0).run();self.assertEqual(self.runs,[]);self.assertEqual(self.done,[('daily24','goal_complete')])
    def test_restart_record_is_character_and_setting_scoped(self):
        r.save_record(self.adapter,'daily','inside')
        self.assertIsNotNone(r.valid_record(self.adapter))
        self.adapter.values[r.KEYS['daily']+'.stage']='changed';self.assertIsNone(r.valid_record(self.adapter))
        r.save_record(self.adapter,'daily','inside')
        (self.root/'settings/manager_identity.json').write_text('{"server_name":"s","character_name":"two"}')
        self.assertIsNone(r.valid_record(self.adapter))
    def test_after_resumed_exit_immediately_uses_the_remembered_entry(self):
        r.save_record(self.adapter,'weekly','inside');self.events=[{'total':0}]
        r.after_exit(self.adapter,self.context,NoInput());self.assertEqual(self.runs,['weekly']);self.assertEqual(self.done,[('weekly','exhausted')])
    def test_unknown_kind_with_multiple_enabled_entries_is_not_guessed(self):
        with self.assertRaises(r.ReentryPending):r.after_exit(self.adapter,self.context,NoInput())
        self.assertEqual(self.runs,[])
    def test_disabling_the_content_prevents_any_new_entry(self):
        self.adapter.values[r.KEYS['daily']+'.enabled']=False
        with self.assertRaises(r.ReentryPending):self.flow('daily').run()
        self.assertEqual(self.runs,[])
    def test_goal_budget_survives_a_user_stop(self):
        self.events=[{'total':3600,'spent':900,'stop':True}]
        with self.assertRaises(Cancelled):self.flow('tale24').run()
        self.assertEqual(r.valid_record(self.adapter)['budget'],2700);self.assertEqual(self.done,[])
    def test_previous_zero_record_does_not_replace_a_new_actual_quota_check(self):
        r.save_record(self.adapter,'daily','exhausted');self.events=[{'total':0}]
        r.after_exit(self.adapter,self.context,NoInput());self.assertEqual(self.runs,['daily'])
    def test_resumed_24h_map_preserves_elapsed_target_before_reentry(self):
        r.save_record(self.adapter,'daily24','inside',budget=2700)
        with patch.object(r.time,'monotonic',return_value=100):goal=r.resume_goal(self.adapter)
        with patch.object(r.time,'monotonic',return_value=400):r.preserve_resume_goal(self.adapter,goal)
        self.assertEqual(r.valid_record(self.adapter)['budget'],2400)
    def test_completed_resumed_target_reuses_only_native_leave(self):
        goal=r.ResumeGoal('daily24',0);native_exit=Mock()
        with patch.object(r,'make_flow',return_value=S(leave=native_exit)) as factory:
            r.request_goal_leave(self.adapter,self.context,NoInput(),goal)
        native_exit.assert_called_once();self.assertTrue(goal.leave_requested);self.assertEqual(factory.call_args.args[-1],0)

class Completion(unittest.TestCase):
    def test_zero_base_alone_is_not_a_daily_quota_zero(self):
        outcome=t.RunOutcome('비경탐험')
        import logging
        outcome.emit(logging.makeLogRecord({'msg':'남은 기본시간 00:00:00','levelno':logging.INFO,'thread':threading.get_ident()}))
        self.assertFalse(outcome.no_time_left)
        outcome.emit(logging.makeLogRecord({'msg':'비경 이용 시간 0초 · 입장 생략','levelno':logging.INFO,'thread':threading.get_ident()}))
        self.assertTrue(outcome.no_time_left)

class Installation(unittest.TestCase):
    def test_original_flow_methods_are_wrapped_once_without_running_them(self):
        classes=(native.Exploration,tale.FolktaleExploration,tale.Daily24Exploration)
        before={(c,n):c.__dict__.get(n) for c in classes for n in ('select','enter','run')}
        try:
            r.install();once={(c,n):getattr(c,n) for c in classes for n in ('select','enter','run')}
            r.install()
            for (c,n),fn in once.items():
                self.assertIs(getattr(c,n),fn);self.assertTrue(getattr(fn,'_owner_dungeon_reentry_'+n))
        finally:
            for (c,n),fn in before.items():
                if fn is None:delattr(c,n)
                else:setattr(c,n,fn)

if __name__=='__main__':unittest.main()
