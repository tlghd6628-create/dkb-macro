"""Common results, retries, identity and shared decisions. Fake input/saved state only."""
import bootstrap
import base64,hashlib,importlib,json,tempfile,threading,unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
import owner_timetable as t
import owner_outcome as o
import owner_character_binding as binding
import owner_growth_reading as reading
import owner_blessing_native_candidate as blessing
from owner_feature_check_status_candidate import assessment,verification,level_counts
from owner_gear_decision_candidate import Observation
from owner_gear_step_guard_candidate import Guard


def scratch(case):
    tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');case.addCleanup(tmp.cleanup)
    return Path(tmp.name)


class Base(unittest.TestCase):
    keys=('clan_request','tower','gear','growth')
    def setUp(self):
        self.root=scratch(self);self.at=t.now()
        self.values={t.BY_KEY[key].setting:True for key in self.keys}
        for p in (patch.object(t,'identity',return_value='fixture'),patch.object(t,'busy_windows',return_value=[])):
            p.start();self.addCleanup(p.stop)
        self.plan=t.Planner(self.root,self.values,self.at)
        for key in self.keys:self.plan.state[key].update(status='pending',at=(self.at-timedelta(minutes=1)).isoformat(),attempts=0)
    def begin(self,key):self.plan.begin(key,self.at);return self.plan.state[key]


class Results(unittest.TestCase):
    def test_combining_parts_never_hides_sent_input(self):
        rows=[o.Outcome(k) for k in (o.DONE,o.WAITING,o.SENT_UNCONFIRMED,o.FAILED)]
        self.assertEqual(o.worst(*rows).kind,o.SENT_UNCONFIRMED)
        self.assertRaises(ValueError,o.Outcome,'finished?')
    def test_report_take_clears(self):
        adapter=S();o.report(adapter,'gear',o.Outcome(o.DONE));o.report(adapter,'gear',o.Outcome(o.NOT_ATTEMPTED,'x'))
        self.assertEqual(o.take(adapter,'gear').kind,o.NOT_ATTEMPTED);self.assertIsNone(o.take(adapter,'gear'))
    def test_energy_hold_before_input_is_not_attempted(self):
        for value in ({'status':'held','reason':'캐릭터·레벨 재확인 필요'},'캐릭터 확인 필요','진입 버튼 확인 필요'):
            with patch.object(o,'growth_pending',return_value=None):
                self.assertEqual(o.classify('growth',S(_owner_energy_outcome=value),True).kind,o.NOT_ATTEMPTED)
        with patch.object(o,'growth_pending',return_value=None):
            self.assertIsNone(o.classify('growth',S(_owner_energy_outcome='처리 종료 · 완료 여부 미확인'),True))
    def test_sent_intent_overrides_every_other_result(self):
        adapter=S();o.report(adapter,'gear',o.Outcome(o.DONE))
        with patch.object(o,'growth_pending',return_value={'phase':'sent'}):
            self.assertEqual(o.classify('gear',adapter,True).kind,o.SENT_UNCONFIRMED)
    def test_prepared_intent_was_never_sent(self):
        with patch.object(o,'growth_pending',return_value={'phase':'prepared'}):
            self.assertIsNone(o.classify('gear',S(),True))
    def test_unreadable_ledger_is_not_clear(self):
        root=scratch(self);(root/'settings').mkdir()
        from owner_gear_settings_candidate import Store
        path=Store(root,'scope').path;path.parent.mkdir(exist_ok=True)
        path.with_name(path.stem+'-intent.json').write_text('{broken',encoding='utf-8')
        with patch('owner_hunt_rules_candidate.configured_identity',return_value='scope'):
            self.assertEqual(o.growth_pending(S(project=S(root=root))),{'phase':'unreadable'})


class Timetable(Base):
    def test_not_attempted_keeps_the_attempt_and_stays_due(self):
        row=self.begin('clan_request');self.plan.apply_outcome('clan_request',o.Outcome(o.NOT_ATTEMPTED,'메뉴 확인 필요'),self.at)
        self.assertEqual((row['status'],row['attempts']),('pending',0))
        self.assertEqual(t.parse_at(row['at']),self.at+timedelta(minutes=10))
        self.assertNotIn('clan_request',[j.key for j in self.plan.due(self.at+timedelta(minutes=9))])
        self.assertIn('clan_request',[j.key for j in self.plan.due(self.at+timedelta(minutes=10))])
        self.assertEqual(row['last_outcome'],o.NOT_ATTEMPTED)
    def test_not_attempted_backs_off_without_exhausting(self):
        gaps=[]
        for _ in range(5):
            self.begin('clan_request');self.plan.apply_outcome('clan_request',o.Outcome(o.NOT_ATTEMPTED),self.at)
            gaps.append(t.parse_at(self.plan.state['clan_request']['at'])-self.at)
        self.assertEqual([g.seconds//60 for g in gaps],[10,20,40,60,60])
        self.assertEqual(self.plan.state['clan_request']['attempts'],0)
    def test_success_resets_backoff(self):
        self.begin('clan_request');self.plan.apply_outcome('clan_request',o.Outcome(o.NOT_ATTEMPTED),self.at)
        self.begin('clan_request');self.plan.apply_outcome('clan_request',o.Outcome(o.DONE),self.at)
        self.assertNotIn('not_attempted_count',self.plan.state['clan_request'])
        self.assertEqual(self.plan.state['clan_request']['status'],'processed')
    def test_sent_unconfirmed_is_result_only_and_survives_restart(self):
        row=self.begin('gear');self.plan.apply_outcome('gear',o.Outcome(o.SENT_UNCONFIRMED,'결과 확인 필요'),self.at)
        self.assertEqual((row['status'],row['retry_mode'],row['attempts']),('pending','reconcile',0))
        self.assertTrue(row['result_unverified'])
        restarted=t.Planner(self.root,self.values,self.at+timedelta(minutes=1))
        self.assertIn('결과 확인만',restarted.reason('gear',self.at))
    def test_waiting_uses_the_user_growth_interval(self):
        row=self.begin('gear')
        with patch.object(self.plan,'recheck_minutes',return_value=35):
            self.plan.apply_outcome('gear',o.Outcome(o.WAITING,'재료 부족'),self.at)
        self.assertEqual(t.parse_at(row['at']),self.at+timedelta(minutes=35))
    def fail_job(self,key,count):
        for _ in range(count):
            self.begin(key);self.plan.apply_outcome(key,o.Outcome(o.FAILED,'실패'),self.at)
    def test_two_failures_do_not_lose_the_rest_of_the_week(self):
        with patch.object(t,'selected_days',return_value=None),patch.object(t,'period',return_value='fixed'):
            self.plan.state['tower']['period']='fixed'
            self.fail_job('tower',1);self.assertEqual(self.plan.state['tower']['attempts'],1)
            self.fail_job('tower',1)
            row=self.plan.state['tower']
            self.assertEqual((row['status'],row['attempts'],row['failed_cycles']),('failed',0,1))
            self.assertEqual(t.parse_at(row['at']),self.at+timedelta(minutes=t.FAILED_COOLDOWN_WEEK))
    def test_failure_cycles_are_finite(self):
        with patch.object(t,'selected_days',return_value=None),patch.object(t,'period',return_value='fixed'):
            self.plan.state['clan_request']['period']='fixed'
            self.fail_job('clan_request',2*t.FAILED_CYCLES+2)
            row=self.plan.state['clan_request']
            self.assertGreaterEqual(row['attempts'],2);self.assertEqual(row['failed_cycles'],t.FAILED_CYCLES)
            self.assertIn('재시도 2회',self.plan.reason('clan_request',self.at+timedelta(minutes=30)))
    def adapter(self):
        return S(project=S(root=self.root),values=self.values,mode='auto_mode',_owner_timetable=self.plan)
    def test_energy_identity_hold_is_not_marked_processed(self):
        adapter=self.adapter()
        def run():adapter._owner_energy_outcome={'status':'held','reason':'캐릭터·레벨 재확인 필요'};return True
        with patch.object(o,'growth_pending',return_value=None),patch.object(t.Planner,'reason',return_value=None):
            t.scheduled_call(run,'기운 발현',(),{},adapter,timed_dispatch=True)
        row=self.plan.state['growth']
        self.assertEqual((row['status'],row['attempts'],row['last_outcome']),('pending',0,o.NOT_ATTEMPTED))
    def test_gear_with_sent_intent_is_never_counted_as_failure(self):
        adapter=self.adapter()
        with patch.object(o,'growth_pending',return_value={'phase':'sent'}),patch.object(t.Planner,'reason',return_value=None):
            t.scheduled_call(lambda:False,'성장 장비·가호',(),{},adapter,timed_dispatch=True)
        row=self.plan.state['gear']
        self.assertEqual((row['status'],row['attempts'],row['retry_mode']),('pending',0,'reconcile'))
    def test_ordinary_success_path_is_unchanged(self):
        adapter=self.adapter()
        with patch.object(o,'growth_pending',return_value=None),patch.object(t.Planner,'reason',return_value=None):
            t.scheduled_call(lambda:True,'길라잡이',(),{},adapter,timed_dispatch=True)
        self.assertEqual(self.plan.state['clan_request']['status'],'processed')
    def test_mismatched_character_neither_runs_nor_consumes(self):
        adapter=self.adapter();adapter._owner_character_mismatch=True;called=[]
        before=dict(self.plan.state['clan_request'])
        t.scheduled_call(lambda:called.append(1),'길라잡이',(),{},adapter,timed_dispatch=True)
        self.assertEqual(called,[]);self.assertEqual(self.plan.state['clan_request'],before)


class Binding(unittest.TestCase):
    def setUp(self):self.root=scratch(self)
    def test_first_reading_binds_then_matches(self):
        self.assertEqual(binding.resolve(self.root,'p','a',30),('a',binding.BOUND))
        self.assertEqual(binding.resolve(self.root,'p','a',31),('a',binding.CROSSED))
        self.assertEqual(binding.resolve(self.root,'p','a',31),('a',binding.MATCHED))
    def test_other_character_is_a_mismatch(self):
        binding.resolve(self.root,'p','a',30)
        self.assertEqual(binding.resolve(self.root,'p','b',30),('b',binding.MISMATCH))
    def test_level_ten_crossing_keeps_the_same_key(self):
        import numpy as np
        own=np.random.RandomState(1).randint(0,255,(18,10)).tolist();other=np.random.RandomState(2).randint(0,255,(18,10)).tolist()
        binding.resolve(self.root,'p','low',9,own)
        self.assertEqual(binding.resolve(self.root,'p','high',10,own),('low',binding.CROSSED))
        self.assertEqual(binding.resolve(self.root,'p','high',10,own),('low',binding.MATCHED))
        self.assertEqual(binding.resolve(self.root,'p','other',12,other)[1],binding.MISMATCH)
    def test_later_level_is_known_by_its_first_glyph(self):
        import numpy as np
        frame=np.zeros((479,897,3),'uint8');frame[9:25,72:88]=200
        head=binding.name_head(frame);binding.resolve(self.root,'p','low',9,head)
        self.assertTrue(binding.shown_on(np.array(frame),'low'))
        self.assertFalse(binding.shown_on(np.zeros((479,897,3),'uint8'),'low'))
        self.assertFalse(binding.shown_on(frame,'unknown'))
    def test_lower_band_after_high_is_not_a_crossing(self):
        binding.resolve(self.root,'p','high',30)
        self.assertEqual(binding.resolve(self.root,'p','low',5)[1],binding.MISMATCH)
    def test_profiles_are_separate(self):
        binding.resolve(self.root,'p','a',30);self.assertEqual(binding.resolve(self.root,'q','b',30)[1],binding.BOUND)
    def test_unreadable_record_proves_nothing_and_is_kept(self):
        path=self.root/'settings/owner-character-binding.json';path.parent.mkdir();path.write_text('{bad',encoding='utf-8')
        self.assertEqual(binding.resolve(self.root,'p','a',30),('a',binding.UNAVAILABLE))
        self.assertEqual(path.read_text(encoding='utf-8'),'{bad')
    def test_observe_sets_and_clears_the_hold(self):
        adapter=S(project=S(root=self.root))
        with patch('owner_hunt_rules_candidate.configured_identity',return_value='p'):
            binding.observe(adapter,'a',30);self.assertFalse(binding.mismatch(adapter))
            binding.observe(adapter,'b',30);self.assertTrue(binding.mismatch(adapter))
            binding.observe(adapter,'a',30);self.assertFalse(binding.mismatch(adapter))
    def test_growth_identity_refuses_during_mismatch(self):
        import owner_program_runtime as runtime
        adapter=S(project=S(root=self.root),_owner_character_mismatch=True)
        progress=S(character='b',observed=__import__('time').monotonic())
        with patch('owner_progression.state',return_value=progress):
            self.assertIsNone(runtime.gear_identity(S(adapter=adapter)))


class Decisions(unittest.TestCase):
    def test_goal_states(self):
        self.assertEqual(reading.goal_state(None,1),'goal_missing')
        self.assertEqual(reading.goal_state({'enabled':False,'enhance':5},1),'goal_off')
        self.assertEqual(reading.goal_state({'enabled':True,'enhance':'5'},1),'goal_invalid')
        self.assertEqual(reading.goal_state({'enabled':True,'enhance':-1},1),'goal_invalid')
        self.assertEqual(reading.goal_state({'enabled':True,'enhance':1},1),'goal_reached')
        self.assertEqual(reading.goal_state({'enabled':True,'enhance':2},1),'below')
    def test_checker_ready_exactly_when_guard_would_act(self):
        ctx=S(checkpoint=lambda:None);guard=Guard(ctx,None,None,clock=lambda:100.1)
        def obs(sequence,at,level):return Observation(sequence,at,'c','i','s','g',level,None,None,True,None,None)
        for target in (None,{'enabled':False,'enhance':9},{'enabled':True,'enhance':'9'},{'enabled':True,'enhance':5},{'enabled':True,'enhance':9}):
            with self.subTest(target=target):
                acts=guard._enhance_plan(obs(1,100.,5),obs(2,100.05,5),target)
                self.assertEqual(bool(acts),reading.enhance_decision(target,5,ready=True,materials=None)==('action_ready','ready'))
    def test_material_and_extra_findings(self):
        goal={'enabled':True,'enhance':9,'awaken':2}
        self.assertEqual(reading.enhance_decision(goal,5,ready=False,materials='재료 부족'),('values','materials_short'))
        self.assertEqual(reading.enhance_decision(goal,5,ready=False,materials=None),('values','materials_unreadable'))
        self.assertEqual(reading.extra_decision(goal,1,field='awaken',maximum=True),('action_ready','game_limit'))
        self.assertEqual(reading.extra_decision(goal,2,field='awaken'),('action_ready','goal_reached'))
    def test_known_detail_needs_no_ocr(self):
        with patch('owner_growth_material_contract.inspect_materials',side_effect=AssertionError):
            self.assertEqual(reading.material_status(None,None,None,'root',{'materials':'재료 부족'}),'재료 부족')
    def test_blessing_gets_the_explicit_quantity_reader_too(self):
        with patch('owner_growth_material_contract.inspect_materials',return_value={'status':'재료 충분'}) as read:
            self.assertEqual(reading.material_status(None,None,None,'root',{'materials':'판별 불가'}),'재료 충분')
        read.assert_called_once()
    def test_button_needs_one_match_and_active_brightness(self):
        frame=np.full((20,20,3),100,np.uint8);template=np.full((10,10,3),100,np.uint8)
        hit=(5,5,(0,0,10,10))
        detector=S(find=lambda name,f,threshold:hit if name=='a' else None,templates={'a':template})
        self.assertEqual(reading.exec_button(detector,('a','b'),frame)['active'],True)
        dim=S(find=detector.find,templates={'a':np.full((10,10,3),200,np.uint8)})
        result=reading.exec_button(dim,('a','b'),frame);self.assertEqual((result['unique'],result['active']),(True,False))
        both=S(find=lambda name,f,threshold:hit,templates={})
        self.assertFalse(reading.exec_button(both,('a','b'),frame)['unique'])


class BlessingPath(unittest.TestCase):
    def observer(self,detail,*,find=lambda *a,**k:None):
        item=object.__new__(blessing.BlessingObserver)
        item.context=S(checkpoint=lambda:None,wait=lambda n:None)
        item.service=S(check=lambda:None,capture=lambda:np.zeros((479,897,3),np.uint8),detector=S(find=find,templates={}))
        item.native=S(read_growth_equipment_detail=lambda *a,**k:detail,GROWTH_BLESSING_EXEC_BUTTONS=('a','b'))
        item.row={'index':1,'slot':{'cell_x':10,'cell_y':10}};item.pre=np.zeros((479,897,3),np.uint8);item.rows=[]
        item.root='root';item.config={};item.slot_reader=lambda root,frame:3;item.identity='c';item.item='i';item.sequence=0
        item.last_reason='';item.last_state=None;item._fresh_read_view=None
        return item
    def test_known_shortage_survives_a_missing_button(self):
        item=self.observer({'enhancement':30,'materials':'재료 부족'})
        with patch.object(blessing,'selected_matches',return_value=True):
            state=item._state(np.zeros((479,897,3),np.uint8))
        self.assertEqual((state['materials'],state['active'],state['button']),('재료 부족',False,None))
    def test_material_flicker_does_not_fail_an_inactive_reading(self):
        item=self.observer({});item.clock=iter((0.,.1,.2,.3,.4,.5)).__next__
        states=iter(({'slot':3,'level':30,'active':False,'button':None,'opening':False,'materials':'재료 부족'},
                     {'slot':3,'level':30,'active':False,'button':None,'opening':False,'materials':None}))
        item._state=lambda frame:next(states)
        self.assertTrue(item.read_pair(False,publish=False)['screen_proof'])
    def test_active_change_still_fails(self):
        item=self.observer({});item.clock=iter((0.,.1,.2,.3,.4,.5)).__next__
        states=iter(({'slot':3,'level':30,'active':True,'button':'a','opening':False,'materials':'재료 충분'},
                     {'slot':3,'level':30,'active':False,'button':'a','opening':False,'materials':'재료 충분'}))
        item._state=lambda frame:next(states)
        self.assertFalse(item.read_pair(False)['screen_proof']);self.assertEqual(len(item.diagnostic_pair),2)
    def test_running_path_keeps_the_stage_and_both_frames(self):
        item=self.observer({});item.clock=iter([float(n)*2 for n in range(60)]).__next__
        item._state=lambda frame:{'slot':3,'level':30,'active':False,'button':None,'opening':False,'materials':None}
        def view(frame,source,state):item.last_view_reason='현재 강화 글자';return False
        item._same_read_view=view
        self.assertFalse(item.read_pair(False,publish=True)['screen_proof'])
        self.assertIn('현재 강화 글자',item.last_reason);self.assertEqual(len(item.diagnostic_pair),2)
    def test_shortage_counter_is_not_compared(self):
        item=self.observer({});item.config={'template_roi':'x','search_roi':'y','rel_x':0,'rel_y':0,'w':10,'h':10}
        item.service.detector=S(find=lambda *a,**k:(1,1,(0,0,5,5)),entries={'범위_성장_장비_재료수량':{'x':0,'y':0,'w':5,'h':5}})
        boxes=[]
        with patch.object(blessing,'selected_matches',return_value=True),patch.object(blessing,'same_white_text',side_effect=lambda a,b,box,*rest:boxes.append(box) or True):
            self.assertTrue(item._same_read_view(item.pre,item.pre,{'active':False,'opening':False,'materials':'재료 부족','button':None}))
        self.assertEqual(len(boxes),2)
    def test_identical_twin_requires_the_selected_mark(self):
        icon=(np.random.default_rng(1).random((18,18,3))*255).astype(np.uint8)
        pre=np.zeros((479,897,3),np.uint8);rows=[]
        for index,x in ((1,700),(2,740),(3,780)):
            rows.append({'index':index,'slot':{'cell_x':x,'cell_y':80}})
        pre[88:106,708:726]=icon;pre[88:106,748:766]=icon
        pre[88:106,788:806]=(np.random.default_rng(2).random((18,18,3))*255).astype(np.uint8)
        current=np.zeros((479,897,3),np.uint8);current[95:113,380:398]=icon
        self.assertFalse(blessing.selected_matches(S(_growth_selected_slot=lambda f,r:2),None,pre,rows,1,current))
        self.assertTrue(blessing.selected_matches(S(_growth_selected_slot=lambda f,r:1),None,pre,rows,1,current))
        self.assertFalse(blessing.selected_matches(S(),None,pre,rows,1,current))
    def native(self,selected):
        rows=[{'index':1,'slot':{'cell_x':10,'cell_y':10,'cell_w':30,'cell_h':30}},{'index':2,'slot':{'cell_x':50,'cell_y':10,'cell_w':30,'cell_h':30}}]
        return S(inspect_growth_equipment=lambda d,f,blessing=False:rows,_growth_selected_slot=lambda f,r:next(selected),_click_xy=lambda s:(s['cell_x']+5,s['cell_y']+5))
    def test_unselected_row_needs_no_input(self):
        clicks=[];service=S(detector=None,click_hit=clicks.append,capture=lambda:None)
        frame=object()
        self.assertIs(blessing.reveal_unselected(service,S(wait=lambda n:None),self.native(iter([2])),frame,{'index':1},lambda:None),frame)
        self.assertEqual(clicks,[])
    def test_selected_row_selects_another_tile_first(self):
        clicks=[];fresh=object();service=S(detector=None,click_hit=clicks.append,capture=lambda:fresh)
        result=blessing.reveal_unselected(service,S(wait=lambda n:None),self.native(iter([1,2])),object(),{'index':1},lambda:None)
        self.assertIs(result,fresh);self.assertEqual(clicks[0][:2],(55,15))
    def test_selection_that_will_not_move_is_a_hold(self):
        service=S(detector=None,click_hit=lambda hit:None,capture=lambda:object())
        self.assertIsNone(blessing.reveal_unselected(service,S(wait=lambda n:None),self.native(iter([1,1])),object(),{'index':1},lambda:None))
    def test_pending_item_found_by_saved_icon_after_its_level_badge_changed(self):
        icon=(np.random.default_rng(3).random((18,18,3))*255).astype(np.uint8);frame=np.zeros((479,897,3),np.uint8)
        changed=icon.copy();changed[17,17]=(0,0,0);frame[18:36,18:36]=changed
        before=S(item='blessing-icon:'+hashlib.sha256(icon.tobytes()).hexdigest())
        row={'index':1,'slot':{'cell_x':10,'cell_y':10}}
        pending={'before':before,'item_icon':base64.b64encode(icon.tobytes()).decode()}
        self.assertEqual(blessing._pending_matches(pending,[row],frame),[row])
        self.assertEqual(blessing._pending_matches({'before':before},[row],frame),[])
    def test_running_hold_reports_stage_and_queues_frames(self):
        from project_adapter import market_inventory as native
        root=scratch(self);frame=np.zeros((479,897,3),np.uint8);queued=[]
        adapter=S(project=S(root=root))
        service=S(adapter=adapter,check=lambda:None,capture=lambda:frame,detector=S(find=lambda *a,**k:None))
        context=S(checkpoint=lambda:None,wait=lambda n:None)
        lists=iter(([{'index':1,'slot':'a'}],[{'index':2,'slot':'b'}]))
        with patch.object(blessing,'worn_candidates',side_effect=lambda *a:next(lists)),patch('owner_native_contracts.pool_for',return_value=S(get=lambda role:S(find=lambda *a,**k:None))),patch('owner_gear_hold_capture_candidate.enqueue',side_effect=lambda *a:queued.append(a)):
            self.assertFalse(blessing.run_blessing(service,context,'scope',{'1번':{'enabled':True,'enhance':9}}))
        self.assertEqual(adapter._owner_blessing_growth_outcome['state'],'hold_worn_list')
        self.assertEqual(queued[0][1],'blessing-hold_worn_list');self.assertEqual(len(queued[0][3]),2)
        self.assertEqual(o.take(adapter,'gear').kind,o.NOT_ATTEMPTED)


class BreakthroughFailure(unittest.TestCase):
    def reconcile(self,kind,data_extra,*,complete=lambda:True):
        from owner_gear_intent_store_candidate import IntentStore
        store=IntentStore(scratch(self)/'intent.json')
        def obs(sequence,at,stage):return Observation(sequence,at,'c','i','s','g',None,stage,None,None,None,None)
        store.begin({'kind':kind,'before':obs(1,1.,2),'second':obs(2,1.1,2)});store.mark_sent()
        pair=dict({'screen_proof':True,'first':obs(3,100.,None),'second':obs(4,100.1,None)},**data_extra)
        guard=Guard(S(checkpoint=lambda:None),store,lambda:pair,clock=lambda:100.2)
        return guard.reconcile(before_complete=complete),store
    def test_explicit_failure_window_ends_the_input(self):
        result,store=self.reconcile('breakthrough',{'result_failed':True})
        self.assertEqual(result,'observed_failure');self.assertIsNone(store.pending())
        self.assertEqual(store._read()['last_result'],'observed_failure')
    def test_unchanged_stage_alone_is_a_failure(self):
        def same(sequence,at):return Observation(sequence,at,'c','i','s','g',None,2,None,None,None,None)
        result,store=self.reconcile('breakthrough',{'first':same(3,100.),'second':same(4,100.1)})
        self.assertEqual(result,'observed_failure');self.assertIsNone(store.pending())
    def test_higher_stage_is_success_and_lower_stays_held(self):
        def at(stage,sequence,when):return Observation(sequence,when,'c','i','s','g',None,stage,None,None,None,None)
        result,_=self.reconcile('breakthrough',{'first':at(3,3,100.),'second':at(3,4,100.1)})
        self.assertEqual(result,'observed_progress')
        result,store=self.reconcile('breakthrough',{'first':at(1,3,100.),'second':at(1,4,100.1)})
        self.assertEqual(result,'hold_result_unknown');self.assertIsNotNone(store.pending())
    def test_failure_flag_never_applies_to_other_actions(self):
        for kind in ('enhance','awaken'):
            result,store=self.reconcile(kind,{'result_failed':True})
            self.assertEqual(result,'hold_result_unknown');self.assertIsNotNone(store.pending())
    def test_changed_character_keeps_the_record(self):
        result,store=self.reconcile('breakthrough',{'result_failed':True},complete=lambda:False)
        self.assertEqual(result,'hold_identity_or_settings');self.assertIsNotNone(store.pending())
    def read(self,rows,close=.99):
        import sys,owner_gear_awaken_reader_candidate as reader
        page=[{'rec_texts':[r[0] for r in rows],'rec_scores':[r[1] for r in rows]}]
        engine=S(predict=lambda image:page)
        with patch.object(reader,'asset_score',return_value=close),patch.dict(sys.modules,{'tools.ocr_support':S(get_paddle_engine=lambda root,language:engine)}):
            return reader.read_failure_overlay('root',np.zeros((479,897,3),np.uint8))
    def test_failure_notice_needs_close_button_and_clear_text(self):
        self.assertTrue(self.read([('돌파 실패',.99)]))
        self.assertTrue(self.read([('돌파에 실패했습니다',.99)]))
        self.assertIsNone(self.read([('돌파 실패',.99)],close=.5))
        self.assertIsNone(self.read([('돌파 실패',.90)]))
        self.assertIsNone(self.read([('돌파 성공',.99)]))
        self.assertIsNone(self.read([('강화 실패',.99)]))
        self.assertIsNone(self.read([('돌파 실패',.99),('돌파 실패',.98)]))


class EnergyFailure(unittest.TestCase):
    def setUp(self):
        from owner_gear_intent_store_candidate import IntentStore
        self.store=IntentStore(scratch(self)/'intent.json');self.seq=0
        self.context=S(checkpoint=lambda:None,wait=lambda n:None)
        self.store.begin({'kind':'enhance','before':self.obs(5,3),'second':self.obs(5,3)});self.store.mark_sent()
    def obs(self,stage,level,item='i'):
        self.seq+=1;return Observation(self.seq,float(self.seq),'c',item,'s','생명',level,stage,None,True,None,None)
    def observer(self,stage=5,level=3,item='i'):
        return S(read_pair=lambda:{'screen_proof':True,'first':self.obs(stage,level,item),'second':self.obs(stage,level,item)})
    def settle(self,observer,**kw):
        import owner_energy_native_candidate as energy
        return energy.settle_pending(observer,self.store,self.context,**kw)
    def test_same_stage_and_level_is_a_finished_failure(self):
        self.assertTrue(self.settle(self.observer()));self.assertIsNone(self.store.pending())
        self.assertEqual(self.store._read()['last_result'],'observed_failure')
    def test_higher_stage_or_level_is_success(self):
        self.assertTrue(self.settle(self.observer(level=4)))
        self.assertEqual(self.store._read()['last_result'],'observed_progress')
    def test_lower_value_is_not_called_a_failure(self):
        self.assertFalse(self.settle(self.observer(level=1)));self.assertIsNotNone(self.store.pending())
    def test_other_item_stays_held(self):
        self.assertFalse(self.settle(self.observer(item='other')));self.assertIsNotNone(self.store.pending())
    def test_waits_through_the_animation(self):
        replies=iter([{'screen_proof':False},{'screen_proof':False}]);real=self.observer()
        self.assertTrue(self.settle(S(read_pair=lambda:next(replies,None) or real.read_pair()),attempts=6))
    def test_hidden_panel_keeps_the_record(self):
        self.assertFalse(self.settle(S(read_pair=lambda:{'screen_proof':False}),attempts=2))
        self.assertIsNotNone(self.store.pending())


class SkillBreakthroughFailure(unittest.TestCase):
    def upgrade(self,stages):
        import owner_skill_upgrade_candidate as upgrade
        readings=iter(stages);clicks=[];ledger=S(item={},event=lambda *a,**k:None)
        class Port:
            ui=S(context=S(checkpoint=lambda:None,wait=lambda n:None),frame=lambda:None)
            def observe(self,name,kind,*,need_quote=False):
                if not need_quote:self.last=next(readings)
                return dict(name=name,kind=kind,current=self.last,next=self.last+1,have=9,need=1,price=1,funds=9)
            def commit(self,quote,prepare):prepare();clicks.append(quote['current'])
        return upgrade.SkillUpgrade(Port(),ledger,lambda:True),clicks,ledger
    def test_failed_attempt_retries_until_the_goal(self):
        item,clicks,_=self.upgrade([2,2,2,3])
        self.assertEqual(item.run('절명','breakthrough',3)['status'],'target_reached');self.assertEqual(clicks,[2,2])
    def test_step_limit_still_bounds_failures(self):
        item,clicks,_=self.upgrade([2]*20)
        self.assertEqual(item.run('절명','breakthrough',3,max_steps=3)['status'],'partial');self.assertEqual(len(clicks),3)
    def test_result_check_never_sends_new_input(self):
        item,clicks,ledger=self.upgrade([2])
        ledger.item['skill_upgrade_intents']={'breakthrough:절명':{'status':'sent','name':'절명','kind':'breakthrough','before':2}}
        self.assertEqual(item.run('절명','breakthrough',3,max_steps=1,result_only=True)['status'],'observed_failure');self.assertEqual(clicks,[])
    def test_awakening_unchanged_stays_held(self):
        from owner_skill_goal import Pending
        item,clicks,_=self.upgrade([0,0])
        self.assertRaises(Pending,item.run,'절명','awaken',1);self.assertEqual(clicks,[0])


class BreakthroughOff(unittest.TestCase):
    def setUp(self):
        p=patch.object(reading,'BREAKTHROUGH_ENABLED',False);p.start();self.addCleanup(p.stop)
    def extras(self,pending=None):
        import owner_gear_native_install_candidate as gear
        root=scratch(self);asked=[];adapter=S(project=S(root=root))
        service=S(context=S(checkpoint=lambda:None,wait=lambda n:None),check=lambda:None,adapter=adapter,capture=lambda:None)
        def factory(service,context,identity,targets,kind):asked.append(kind);return None
        store=gear.Store(root,'scope');document=store.read();document['grades']['희귀'].update(enabled=True,breakthrough=3)
        store.write(document) if hasattr(store,'write') else None
        ran=[];batch=[]
        def native(original):
            def run(*a,**k):batch.append(1);return original(*a,**k)
            return run
        guarded=gear.wrap_extras_decorator(native,lambda s:'scope',factory)(lambda *a,**k:ran.append(1) or True)
        return guarded,service,asked,ran,batch,store
    def test_gear_never_asks_for_a_breakthrough_reader(self):
        guarded,service,asked,ran,batch,store=self.extras()
        with patch.object(store.__class__,'snapshot',return_value=({'grades':{'희귀':{'enabled':True,'breakthrough':3}}},'r1')):
            guarded(service)
        self.assertEqual(asked,['awaken']);self.assertEqual(ran,[1]);self.assertEqual(batch,[])
    def test_missing_settings_skip_the_native_batch(self):
        guarded,service,asked,ran,batch,store=self.extras()
        with patch.object(store.__class__,'snapshot',return_value=({},'missing')):guarded(service)
        self.assertEqual(batch,[]);self.assertEqual(ran,[1])
    def test_enabling_restores_the_breakthrough_path(self):
        guarded,service,asked,ran,batch,store=self.extras()
        with patch.object(reading,'BREAKTHROUGH_ENABLED',True),patch.object(store.__class__,'snapshot',return_value=({'grades':{'희귀':{'enabled':True,'breakthrough':3}}},'r1')):
            guarded(service)
        self.assertEqual(asked,['awaken','breakthrough'])
    def test_energy_breakthrough_button_is_never_active(self):
        import owner_energy_native_candidate as energy
        from project_adapter import achievement_rewards as native
        frame=np.zeros((479,897,3),np.uint8);template=np.full((10,10,3),0,np.uint8);template[0,0]=(90,90,90)
        def find(name,f,threshold):return (5,5,(0,0,10,10)) if name==self.button else None
        service=S(detector=S(find=find,templates={native.ENERGY_ACTIVE:np.full((10,10,3),1,np.uint8),native.ENERGY_BREAKTHROUGH:np.full((10,10,3),1,np.uint8)}),adapter=S(project=S(root='r')))
        frame[0:10,0:10]=1
        info=lambda root,f:{'name':'생명','stage':1,'level':10}
        observer=energy.EnergyObserver(service,S(),'c','생명',5,text_reader=info)
        self.button=native.ENERGY_ACTIVE;self.assertTrue(observer.state(frame)['active'])
        self.button=native.ENERGY_BREAKTHROUGH;self.assertFalse(observer.state(frame)['active'])
    def test_style_goal_does_not_push_past_its_own_enhance_or_open_upgrade(self):
        import owner_skill_growth_candidate as skill,owner_skill_upgrade_candidate as upgrade
        runs=[];ledger=S(item={})
        class Worker:
            def __init__(self,*a):pass
            def _guard(self):pass
            def run(self,name,target,max_steps=5,*,breakthrough_target=0):
                runs.append((name,target,breakthrough_target));return {'status':'ok','level':50}
        doc={'skills':{'절명':{'enabled':True,'enhance':30,'breakthrough':2}}}
        with patch.object(skill,'StyleGrowth',Worker),patch('owner_gear_settings_candidate.validate'),patch.object(upgrade,'has_pending',return_value=False),patch.object(upgrade,'SkillUpgrade',side_effect=AssertionError('no breakthrough')):
            skill.run_configured(None,ledger,doc,lambda:True)
        self.assertEqual(runs,[('절명',30,0)])
    def test_checker_lists_it_as_excluded(self):
        row=dict(stage='config',finding='breakthrough_disabled',contract_ok=True)
        self.assertEqual(assessment(row)['outcome'],'excluded');self.assertIn('돌파',assessment(row)['label'])


class Checker(unittest.TestCase):
    def test_verdict_shows_range_and_level(self):
        row=dict(id='gear_enhance',stage='action_ready',finding='ready',contract_ok=True,screen_verified=True,values_verified=True,
                 targets={'read':1,'total':6,'unit':'장비'})
        self.assertIn('장비 1/6',assessment(row)['label'])
        checked=verification(row);self.assertEqual((checked['level'],checked['gameplay_executed']),('L3',False))
    def test_levels_never_claim_gameplay(self):
        rows=[dict(contract_ok=True),dict(contract_ok=True,screen_verified=True),
              dict(contract_ok=True,screen_verified=True,values_verified=True),
              dict(contract_ok=True,screen_verified=True,decision_verified=True)]
        self.assertEqual([verification(r)['level'] for r in rows],['L0','L1','L2','L3'])
        self.assertFalse({'L4','L5'}&set(level_counts(rows)))
    def test_unverified_row_states_its_reason(self):
        row=dict(contract_ok=True,stage='action_ready',finding='runtime_connected')
        self.assertEqual(assessment(row)['outcome'],'unverified')
        self.assertIn('동작 미시험',verification(row)['unverified_reason'])
    def test_catalog_covers_requested_features_and_targets_resolve(self):
        from owner_feature_check_catalog_candidate import CHECKS
        ids={item['id'] for item in CHECKS}
        self.assertFalse({'shop','box_choice','gear_swap','skill_learn','work_resume','reconnect','user_controls','telegram','auto_update'}-ids)
        self.assertEqual(len(ids),len(CHECKS))
        for name,attr in ((m,a) for item in CHECKS for m,a in item.get('native',()) if m.startswith('owner_')):
            with self.subTest(name=name):self.assertTrue(callable(getattr(importlib.import_module(name),attr)))
    def test_runtime_only_rows_are_never_normal(self):
        from owner_feature_check_extra_candidate import diagnose,RUNTIME_ONLY
        for key in RUNTIME_ONLY:
            record=diagnose(key,root=bootstrap.A,values={})
            self.assertEqual(assessment(dict(contract_ok=True,stage=record['stage'],finding=record['finding']))['outcome'],'unverified')
    def test_exchange_shops_are_automatic_jobs_not_exclusions(self):
        from owner_feature_check_extra_candidate import diagnose
        root=scratch(self);(root/'profiles/DKB').mkdir(parents=True)
        with patch('owner_timetable.shop_selection_enabled',return_value=True) as selected:
            for key in ('daily_shop','weekly_shop'):
                record=diagnose(key,root=root,values={})
                self.assertEqual(record['id'],key);self.assertNotEqual(record['finding'],'manual_only')
                self.assertEqual(assessment(dict(stage=record['stage'],finding=record['finding']))['outcome'],'unverified')
        self.assertEqual(selected.call_count,2)
    def probe(self,fields):
        from owner_feature_check_live_candidate import MenuProbe
        root=scratch(self);frame=np.zeros((479,897,3),np.uint8)
        probe=MenuProbe(None,S(project=S(root=root)),threading.Event())
        probe.context=S(checkpoint=lambda:None,wait=lambda n:None);probe.normalized=True
        probe.service=S(check=lambda:None,capture=lambda:frame,detector=S(find=lambda *a,**k:None),adapter=S(project=S(root=root)))
        probe.inputs=object();seen=iter(fields);probe.field=lambda f:next(seen)
        return probe
    def test_one_missing_button_does_not_stop_later_items(self):
        result=self.probe([True,True,True,True])({'id':'clan_request'},threading.Event())
        self.assertEqual(result['finding'],'probe_error');self.assertFalse(result['stop_navigation'])
    def test_unproven_recovery_still_stops_navigation(self):
        result=self.probe([True,True,False,False])({'id':'clan_request'},threading.Event())
        self.assertTrue(result['stop_navigation'])
    def test_guide_target_is_at_one_place_and_absent_from_other_screens(self):
        from PIL import Image
        from roi_runtime import RoiDetector
        from owner_native_contracts import menu_candidates,menu_regions,find_menu_target
        screens=bootstrap.A/'logs/feature-checks/screens'
        names=menu_candidates('버튼_길라잡이');d=RoiDetector(bootstrap.A/'profiles/DKB',list(names)+list(menu_regions()))
        def load(name):return np.asarray(Image.open(screens/name).convert('RGB'))
        hits=[find_menu_target(d,names[0],load(n)) for n in ('20261102_205449_570690-guide.png','20261102_210428_942009-guide.png')]
        self.assertTrue(all(hits));self.assertEqual(hits[0][2],hits[1][2])
        self.assertIsNone(find_menu_target(d,names[0],load('20261102_210412_584228-blessing_growth.png')))


if __name__=='__main__':unittest.main()
