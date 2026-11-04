"""Persistent planner, blocked OCR and saved frames; no live game input."""
import bootstrap
import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace as S
from unittest.mock import Mock,patch
import owner_timetable as t
from owner_ocr_readiness import Warmup


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.at=datetime(2026,11,2,16,tzinfo=t.KST)
        self.job=t.BY_KEY['inventory']
        self.values={self.job.setting:True}
        self.patches=[patch.object(t,'identity',return_value='fixture'),
                      patch.object(t,'busy_windows',return_value=[])]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.plan=t.Planner(self.root,self.values,self.at)
        self.row=self.plan.state['inventory']
        self.row.update(status='failed',attempts=2,at=self.at.isoformat())

    def incomplete(self,mode='recheck'):
        return {'retryable':True,'retry_mode':mode,'reason':'상자 후보 확인 필요'}

    def test_failure_is_pending_not_complete_and_attempts_retained(self):
        self.assertTrue(self.plan.retry_incomplete('inventory',self.incomplete(),self.at))
        self.assertEqual(self.row['status'],'pending')
        self.assertEqual(self.row['attempts'],2)
        self.assertTrue(self.row['result_unverified'])
        self.assertEqual(t.parse_at(self.row['at']),self.at+timedelta(minutes=20))

    def test_after_two_attempts_it_is_still_due_at_persisted_time(self):
        self.plan.retry_incomplete('inventory',self.incomplete(),self.at)
        self.assertEqual(self.plan.due(self.at+timedelta(minutes=19)),[])
        self.assertEqual([j.key for j in self.plan.due(self.at+timedelta(minutes=20))],['inventory'])

    def test_cold_restart_preserves_reason_time_and_mode(self):
        self.plan.retry_incomplete('inventory',self.incomplete('reconcile'),self.at)
        restarted=t.Planner(self.root,self.values,self.at+timedelta(minutes=1))
        self.assertEqual(restarted.state['inventory'],self.row)
        self.assertIn('결과 확인만',restarted.reason('inventory',self.at))

    def test_old_exhausted_inventory_failure_is_requeued_without_receipt_deletion(self):
        self.plan.commit()
        sentinel=self.root/'settings/untouched-resource-intent.json'
        sentinel.write_text('{"phase":"sent"}',encoding='utf8')
        restarted=t.Planner(self.root,self.values,self.at)
        # The start's own recheck now requeues it, with a fresh attempt count.
        self.assertEqual(restarted.state['inventory']['status'],'pending')
        self.assertEqual(restarted.state['inventory']['attempts'],0)
        self.assertTrue(restarted.state['inventory']['startup_recheck'])
        self.assertEqual(sentinel.read_text('utf8'),'{"phase":"sent"}')

    def test_successful_occurrence_not_migrated(self):
        # A proved result stays done; one without proof is what a start rechecks.
        from owner_outcome import DONE
        self.row.update(status='processed',last_outcome=DONE);self.row.pop('result_unverified',None);self.plan.commit()
        restarted=t.Planner(self.root,self.values,self.at)
        self.assertEqual(restarted.state['inventory']['status'],'processed')

    def test_selected_weekday_and_master_off_win(self):
        self.plan.values[self.job.setting]=False
        self.assertFalse(self.plan.retry_incomplete('inventory',self.incomplete(),self.at))
        self.plan.values[self.job.setting]=True
        self.plan.cfg['jobs']['inventory']={'weekdays':[1]}
        self.assertFalse(self.plan.retry_incomplete('inventory',self.incomplete(),self.at))

    def test_unknown_outcome_and_other_jobs_not_blanket_retried(self):
        self.assertFalse(self.plan.retry_incomplete('inventory',{'state':'held'},self.at))
        self.assertFalse(self.plan.retry_incomplete('treasure',self.incomplete(),self.at))

    def test_boss_departure_is_avoided(self):
        end=self.at+timedelta(hours=1)
        with patch.object(t,'busy_windows',return_value=[(self.at,end)]):
            self.plan.retry_incomplete('inventory',self.incomplete(),self.at)
        self.assertGreaterEqual(t.parse_at(self.row['at']),end)

    def test_does_not_move_occurrence_across_reset(self):
        edge=datetime(2026,11,3,4,50,tzinfo=t.KST)
        self.assertFalse(self.plan.retry_incomplete('inventory',self.incomplete(),edge))

    def test_new_success_clears_retry_marker(self):
        self.plan.retry_incomplete('inventory',self.incomplete(),self.at)
        self.plan.begin('inventory',self.at)
        self.plan.finish('inventory',True,self.at)
        self.assertEqual(self.row['status'],'processed')
        self.assertNotIn('incomplete_retry',self.row)

    def test_shop_partial_is_persisted_as_incomplete(self):
        self.plan.values['owner_shop.enabled']=True
        self.plan.state['shop']={'period':t.period(t.BY_KEY['shop'],self.at),
            'status':'failed','attempts':2,'at':self.at.isoformat()}
        self.assertTrue(self.plan.retry_incomplete('shop',self.incomplete(),self.at))
        row=self.plan.state['shop']
        self.assertEqual(row['status'],'pending');self.assertEqual(row['attempts'],2)
        saved=json.loads(self.plan.path.read_text('utf8'))['characters']['fixture']['shop']
        self.assertEqual(saved['retry_reason'],'상자 후보 확인 필요')

    def test_slow_confirmation_follows_two_fast_checks_without_new_claim(self):
        out={'retryable':True,'retry_mode':'reconcile','reason':'수령 결과 미확인',
             'needs_recheck':True,'reconcile_only':True,'pending_operation':'a'*32}
        self.row.update(energy_confirm_operation='a'*32,energy_confirm_retries=2)
        self.assertFalse(self.plan.repeat_energy(out,self.at))
        self.assertTrue(self.plan.retry_incomplete('inventory',out,self.at))
        self.assertEqual(self.row['energy_followup']['mode'],'reconcile')
        self.assertEqual(t.parse_at(self.row['at']),self.at+timedelta(minutes=20))


class ReadinessTests(unittest.TestCase):
    def test_stop_is_prompt_while_native_model_loader_is_blocked(self):
        release=threading.Event();entered=threading.Event()
        def load(root):entered.set();release.wait(3)
        job=Warmup('unused',load=load);self.assertTrue(entered.wait(1))
        stopped=threading.Event();done=threading.Event();calls=[]
        class Stopped(BaseException):pass
        def checkpoint():
            calls.append('checkpoint')
            if stopped.is_set():raise Stopped()
        context=S(checkpoint=checkpoint,wait=Mock(side_effect=AssertionError('idle input callback')))
        def worker():
            try:job.wait(context)
            except Stopped:pass
            finally:done.set()
        thread=threading.Thread(target=worker);thread.start();stopped.set()
        self.assertTrue(done.wait(.6));self.assertFalse(job.done.is_set())
        context.wait.assert_not_called();release.set();job.thread.join(1);thread.join(1)

    def test_loading_error_never_authorizes_input(self):
        def load(root):raise ValueError('fixture missing model')
        job=Warmup('unused',load);self.assertTrue(job.done.wait(1))
        with self.assertRaisesRegex(RuntimeError,'인식 준비 실패'):
            job.wait(S(checkpoint=lambda:None))

    def test_repeated_start_uses_same_prepared_clients(self):
        load=Mock();job=Warmup('unused',load);self.assertTrue(job.done.wait(1))
        for _ in range(3):job.wait(S(checkpoint=lambda:None))
        load.assert_called_once()


class SavedInventoryTests(unittest.TestCase):
    def frames(self):
        from PIL import Image
        import numpy as np
        folder=Path(__file__).parent/'retry_fixtures'
        return [np.asarray(Image.open(folder/n).convert('RGB')) for n in ('inventory-a.png','inventory-b.png')]

    def test_existing_native_icon_finds_moved_stack_in_both_actual_frames(self):
        from owner_energy_box_detail_candidate import box_candidates,stable_box_candidates
        a,b=self.frames();left,right=box_candidates(a),box_candidates(b)
        self.assertTrue(left);self.assertEqual(left,right)
        self.assertEqual(stable_box_candidates(a,b),left)
        self.assertLessEqual(len(left),5)

    def test_candidate_alone_cannot_authenticate_a_selection_or_claim(self):
        from owner_energy_box_detail_candidate import detail_screen
        from owner_energy_choice_reader_candidate import read_open_pair
        a,b=self.frames()
        self.assertFalse(detail_screen(a));self.assertFalse(detail_screen(b))
        self.assertIsNone(read_open_pair(a,b))

    def test_changed_frame_or_no_bag_cannot_reuse_old_candidate(self):
        import numpy as np
        from owner_energy_box_detail_candidate import stable_box_candidates,box_candidates
        a,b=self.frames();blank=np.zeros_like(a)
        self.assertIsNone(box_candidates(blank))
        self.assertIsNone(stable_box_candidates(a,blank))


class WiringTests(unittest.TestCase):
    def test_native_potion_does_not_chain_town_shopping(self):
        import owner_shop_runtime_candidate as shop
        calls=[]
        class Adapter:
            def run_potion_purchase(self,context,inputs):calls.append('potion');return True
        with patch.dict('sys.modules',{'project_adapter._entry':S(Adapter=Adapter)}), \
             patch.object(shop,'dispatch_configured',side_effect=AssertionError('startup town shopping')):
            shop.install()
            self.assertTrue(Adapter().run_potion_purchase(S(checkpoint=lambda:None),None))
        self.assertEqual(calls,['potion'])

    def test_readiness_is_outermost_before_original_input_runner(self):
        import owner_ocr_readiness as ready
        calls=[]
        class Adapter:
            def run(self,context,inputs):calls.append('input')
        job=S(wait=lambda context:(_ for _ in ()).throw(RuntimeError('not ready')))
        gui=S(project=S(root=Path('unused')))
        with patch.dict('sys.modules',{'project_adapter._entry':S(Adapter=Adapter)}),patch.object(ready,'Warmup',return_value=job):
            ready.install(gui)
            with self.assertRaisesRegex(RuntimeError,'not ready'):Adapter().run(None,None)
        self.assertEqual(calls,[])

    def test_native_merchant_deadline_is_checked_and_restored(self):
        import owner_shop_runtime_candidate as shop
        from owner_shop_transaction_candidate import Hold
        original=Mock();service=S(check=original)
        service.merchant=lambda:service.check()
        adapter=S(run_town_return=Mock(return_value=True))
        context=S(checkpoint=Mock())
        with patch('project_adapter.town_services.TownServices',return_value=service), \
             patch('owner_skill_ui.SkillUI',return_value=object()),patch.object(shop,'_paired',return_value=False), \
             patch.object(shop.time,'monotonic',side_effect=[0,9]):
            with self.assertRaisesRegex(Hold,'상인 탐색 시간 초과'):
                shop._open_town_shop(adapter,context,None)
        self.assertIs(service.check,original);original.assert_called_once()

    def test_failed_town_return_does_not_search_merchant(self):
        import owner_shop_runtime_candidate as shop
        from owner_shop_transaction_candidate import Hold
        adapter=S(run_town_return=Mock(return_value=False))
        with patch('project_adapter.town_services.TownServices') as service:
            with self.assertRaisesRegex(Hold,'마을 복귀 미확인'):
                shop._open_town_shop(adapter,S(checkpoint=lambda:None),None)
        service.assert_not_called()

    def test_new_schedule_status_does_not_claim_completion(self):
        from owner_schedule import events_for
        for phase in ('미완료 재확인 대기','후속 대기'):
            rows=events_for(datetime(2026,11,2,16,tzinfo=t.KST),'자동 기능 '+phase+' · 인벤토리 사용')
            self.assertTrue(rows)
            self.assertTrue(all(r[1]=='partial' for r in rows))


if __name__=='__main__':unittest.main()
