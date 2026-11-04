"""Native orchestrator + fake action bodies. No live input or installed writes."""
import sys,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_content_entry as entry
from test_challenge_test_20261104 import context,real

DAILY='auto_challenge.secret_exploration.enabled'

class Prelude(unittest.TestCase):
    def test_only_initial_town_return_is_skipped_and_later_recovery_runs(self):
        calls=[];ctx=context(calls);original=ctx.run_action;home=Mock(return_value=True)
        later=Mock(return_value=True)
        def native(a,c,i,**kw):
            self.assertTrue(c.run_action('common.run_town_return',home))
            c.run_action('auto_challenge.secret_exploration',lambda:None)
            return c.run_action('common.run_town_return',later)
        self.assertTrue(entry.invoke(native,None,ctx,None,setting=DAILY))
        home.assert_not_called();later.assert_called_once()
        self.assertEqual(calls,['auto_challenge.secret_exploration','common.run_town_return'])
        self.assertIs(ctx.run_action,original)
    def test_unknown_call_order_never_skips_a_later_return(self):
        ctx=context();home=Mock()
        def native(a,c,i):
            c.run_action('other.action',lambda:None)
            c.run_action('common.run_town_return',home)
        entry.invoke(native,None,ctx,None,setting=DAILY);home.assert_called_once()
    def test_unrelated_growth_keeps_town_return(self):
        ctx=context();home=Mock()
        def native(a,c,i):return c.run_action('common.run_town_return',home)
        entry.invoke(native,None,ctx,None,setting='auto_growth.equipment.enabled')
        home.assert_called_once()
    def test_stop_propagates_before_skipping_and_restores_action(self):
        from biol_base.session import Cancelled
        ctx=context();ctx.stop.set();original=ctx.run_action;home=Mock()
        def native(a,c,i):return c.run_action('common.run_town_return',home)
        with self.assertRaises(Cancelled):entry.invoke(native,None,ctx,None,setting=DAILY)
        home.assert_not_called();self.assertIs(ctx.run_action,original)
    def test_error_restores_the_original_action(self):
        ctx=context();original=ctx.run_action
        def native(*a,**k):raise RuntimeError('fixture')
        with self.assertRaisesRegex(RuntimeError,'fixture'):entry.invoke(native,None,ctx,None,setting=DAILY)
        self.assertIs(ctx.run_action,original)
    def test_class_method_is_not_left_shadowed(self):
        class C:
            def checkpoint(self):pass
            def run_action(self,key,op):return op()
        ctx=C()
        entry.invoke(lambda a,c,i:c.run_action('common.run_town_return',lambda:None),None,ctx,None,setting=DAILY)
        self.assertNotIn('run_action',vars(ctx))
    def test_other_threads_do_not_consume_the_worker_prelude(self):
        ctx=context();calls=[]
        def native(a,c,i):
            t=threading.Thread(target=lambda:c.run_action('other',lambda:calls.append('other')))
            t.start();t.join()
            c.run_action('common.run_town_return',lambda:calls.append('home'))
        entry.invoke(native,None,ctx,None,setting=DAILY)
        self.assertEqual(calls,['other'])

class Scheduled(unittest.TestCase):
    def test_real_scheduled_dispatch_reaches_native_entry_without_home(self):
        from owner_timetable import BY_KEY,invoke
        import project_adapter.mission_quests as mission
        import project_adapter.secret_exploration as dungeon
        import project_adapter.secret_folktale as tale
        targets=(('daily_missions',mission,'run_mission_quests',{}),
                 ('weekly_missions',mission,'run_mission_quests',{}),
                 ('daily_dungeon',dungeon,'run_secret_exploration',{}),
                 ('daily24_dungeon',dungeon,'run_secret_exploration',{'variant':'daily24h'}),
                 ('weekly_dungeon',tale,'run_folktale_exploration',{'kind':'5h'}))
        for key,module,name,want in targets:
            with self.subTest(key=key):
                job=BY_KEY[key];saved={job.setting:True};order=[];adapter=real(saved,order=order);ran=[]
                with patch.object(module,name,return_value=True) as native:
                    invoke(adapter,job,context(ran),Mock())
                native.assert_called_once();self.assertEqual(native.call_args.kwargs,want)
                self.assertNotIn('run_town_return',order);self.assertNotIn('common.run_town_return',ran)
                self.assertIs(adapter.values,saved);self.assertEqual(adapter.mode,'sub_quest')
                self.assertEqual(adapter.get_due_schedules(),['ordinary_due'])

class Preparation(unittest.TestCase):
    def test_same_f1_window_method_and_gate_are_reused_without_start(self):
        order=[];gui=S(preparation_gate=lambda:order.append('gate'),
                      game_window=S(require_ready=lambda:order.append('ready')),session=S(start=Mock()))
        entry.prepare_test_window(gui)
        self.assertEqual(order,['gate','ready']);gui.session.start.assert_not_called()
    def test_gate_failure_does_not_resize(self):
        gui=S(preparation_gate=Mock(side_effect=RuntimeError('blocked')),game_window=S(require_ready=Mock()))
        with self.assertRaisesRegex(RuntimeError,'blocked'):entry.prepare_test_window(gui)
        gui.game_window.require_ready.assert_not_called()
    def test_test_resize_failure_creates_no_worker(self):
        import owner_challenge_test as challenge
        from biol_base.session import Session
        session=Session(lambda:None,Mock(),Mock())
        gui=S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),
              game_window=S(require_ready=Mock(side_effect=RuntimeError('size failed'))))
        self.assertFalse(challenge.start(gui,DAILY,Mock()))
        session.adapter_factory.assert_not_called();self.assertFalse(gui._owner_reward_action_test.active)
    def test_reward_test_resize_failure_creates_no_worker(self):
        from owner_reward_action_test import Controller
        from biol_base.session import Session
        session=Session(lambda:None,Mock(),Mock())
        gui=S(session=session,root=S(after=Mock()),closed=threading.Event(),preparation_gate=Mock(),
              game_window=S(require_ready=Mock(side_effect=RuntimeError('size failed'))))
        runner=Controller(gui)
        self.assertFalse(runner.start('auto_rewards.mail.enabled',Mock(),None))
        session.adapter_factory.assert_not_called();self.assertFalse(runner.active)

if __name__=='__main__':unittest.main()
