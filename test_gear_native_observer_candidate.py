"""Saved frames + fake selection/OCR/identity/resources. No real game input."""
import os,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import bootstrap
from roi_runtime import RoiDetector
import project_adapter.market_inventory as actual
from owner_gear_native_observer_candidate import Observer,Hold
from owner_gear_execution_candidate import run_configured_step
from owner_gear_settings_candidate import Store
from owner_gear_native_install_candidate import install,pending_readers_factory,native_readers_factory,_candidate_continuation,_candidate_cursor


class Clock:
    value=100.0
    def __call__(self):return self.value
class Context:
    def __init__(self,clock):self.clock=clock;self.stopped=False
    def checkpoint(self):
        if self.stopped:raise RuntimeError('cancelled')
    def wait(self,seconds):self.clock.value+=seconds
class NativeFake:
    GROWTH_EXEC_BUTTONS=actual.GROWTH_EXEC_BUTTONS
    GROWTH_EQUIPMENT_TAB=actual.GROWTH_EQUIPMENT_TAB
    inspect_growth_equipment=staticmethod(actual.inspect_growth_equipment)
    inspect_growth_materials=staticmethod(actual.inspect_growth_materials)
    _growth_selected_slot=staticmethod(actual._growth_selected_slot)
    def __init__(self,service):self.service=service;self.selected=[]
    def select_growth_equipment(self,service,row):self.selected.append(row['index']);service.phase='post'
    def read_growth_equipment_detail(self,service,frame,config,*,item,minimum_level=None):return {'enhancement':26,'materials':'재료 충분'}
class Service:
    def __init__(self,pre,post):
        from types import SimpleNamespace
        self.adapter=SimpleNamespace(project=SimpleNamespace(root=bootstrap.A));self.phase='pre';self.pre=pre;self.post=post;self.clicks=[]
        names=list(dict.fromkeys([*actual.GROWTH_DETAIL_NAMES,*actual.GROWTH_EQUIPMENT_NAMES,*actual.GROWTH_EXEC_BUTTONS,actual.GROWTH_EQUIPMENT_TAB,actual.GROWTH_MATERIAL_RANGE]))
        self.detector=RoiDetector(bootstrap.A/'profiles/DKB',names)
    def check(self):pass
    def capture(self):return (self.pre if self.phase=='pre' else self.post).copy()
    def click_hit(self,hit):self.clicks.append(hit)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=bootstrap.A/'logs/scene-corpus/20261101'
        cls.pre=np.asarray(Image.open(root/'20261101T162240-7afa44af/screen.png').convert('RGB')).copy()
        cls.post=np.asarray(Image.open(root/'20261101T162242-cdf1cd68/screen.png').convert('RGB')).copy()
    def setUp(self):
        self.clock=Clock();self.context=Context(self.clock);self.service=Service(self.pre,self.post);self.native=NativeFake(self.service)
        self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
        from owner_gear_hold_capture_candidate import _queue
        self.addCleanup(_queue.join)
        self.identity=lambda frame,index,selected:'synthetic-bracelet'
        self.resources=lambda frame:dict(verified=True,active=True,currency='엽전',cost=3000,balance=4416)
    def observer(self):return Observer(self.service,self.context,'server / character',self.native,self.identity,self.resources,clock=self.clock)
    def settings(self,level):
        store=Store(self.temp.name,'server / character');d=store.read();d['grades']['희귀'].update(enabled=True,enhance=level,breakthrough=0,awaken=0);store.write(d)
    def test_fake_reuses_native_detection_and_one_click(self):
        self.settings(30);observer=self.observer();observer.prepare_and_select(9)
        result=run_configured_step(self.service,self.context,self.temp.name,'server / character','enhance',observer.read_pair,observer.verify_final,clock=self.clock)
        self.assertEqual(result,'pending_confirmation');self.assertEqual(self.native.selected,[9]);self.assertEqual(len(self.service.clicks),1)
    def test_real_visual_defaults_with_fake_ocr_and_input(self):
        from owner_gear_intent_store_candidate import IntentStore
        import base64,hashlib
        self.settings(30)
        observer=Observer(self.service,self.context,'server / character',self.native,None,None,clock=self.clock)
        observer.prepare_and_select(9)
        result=run_configured_step(self.service,self.context,self.temp.name,'server / character','enhance',observer.read_pair,observer.verify_final,clock=self.clock)
        self.assertEqual(result,'pending_confirmation');self.assertEqual(len(self.service.clicks),1)
        p=Store(self.temp.name,'server / character').path
        saved=IntentStore(p.with_name(p.stem+'-intent.json')).pending()
        self.assertEqual('icon:'+hashlib.sha256(base64.b64decode(saved['item_icon'])).hexdigest(),saved['before'].item)
    def test_missing_identity_prevents_selection(self):
        self.identity=lambda *a:None;observer=self.observer()
        with self.assertRaises(Hold):observer.prepare_and_select(9)
        self.assertFalse(self.native.selected);self.assertFalse(self.service.clicks)
    def test_character_change_before_selection_preserves_state(self):
        observer=self.observer()
        with self.assertRaises(Hold):observer.prepare_and_select(9,selection_check=lambda:False)
        self.assertFalse(self.native.selected);self.assertFalse(self.service.clicks)
    def test_goal_already_reached_no_click(self):
        self.settings(26);observer=self.observer();observer.prepare_and_select(9)
        result=run_configured_step(self.service,self.context,self.temp.name,'server / character','enhance',observer.read_pair,observer.verify_final,clock=self.clock)
        self.assertEqual(result,'hold_policy');self.assertFalse(self.service.clicks)
    def test_unknown_resource_no_click(self):
        self.settings(30);self.resources=lambda frame:{'verified':False};observer=self.observer();observer.prepare_and_select(9)
        result=run_configured_step(self.service,self.context,self.temp.name,'server / character','enhance',observer.read_pair,observer.verify_final,clock=self.clock)
        self.assertEqual(result,'hold_screen_unverified');self.assertFalse(self.service.clicks)
    def test_paired_known_level_reported_even_when_resource_is_unknown(self):
        reported=[]
        observer=Observer(self.service,self.context,'server / character',self.native,self.identity,
                          lambda frame:{'verified':False},clock=self.clock,observation_sink=reported.append)
        observer.prepare_and_select(9)
        self.assertEqual(observer.read_pair(),{'screen_proof':False})
        self.assertEqual(len(reported),1)
        self.assertEqual((reported[0]['grade'],reported[0]['enhancement'],reported[0]['grid_index']),('희귀',26,9))
        self.assertIsNone(reported[0]['awakening']);self.assertFalse(self.service.clicks)
    def test_inconsistent_number_pair_is_held_with_diagnostic(self):
        values=iter((2,27))
        self.native.read_growth_equipment_detail=lambda *a,**kw:{'enhancement':next(values),'materials':'재료 충분'}
        observer=self.observer();observer.prepare_and_select(9)
        self.assertEqual(observer.read_pair(),{'screen_proof':False})
        self.assertEqual(observer.last_levels,[2,27]);self.assertEqual(observer.last_reason,'강화 수치 불일치')
        self.assertFalse(self.service.clicks)
    def test_raw_input_fallback_requires_new_agreeing_numbers_and_final_guard(self):
        from unittest.mock import patch
        observer=self.observer();observer.prepare_and_select(9);observer.use_raw_input_numbers=True
        self.native.read_growth_equipment_detail=lambda *a,**kw:self.fail('partial numeric route reused')
        with patch('tools.ocr_support.read_growth_number_mdt',side_effect=[{'value':26,'confidence':.99},{'value':2,'confidence':.99}]):
            self.assertFalse(observer.read_pair()['screen_proof'])
        with patch('tools.ocr_support.read_growth_number_mdt',return_value={'value':26,'confidence':.99}):
            out=observer.read_pair()
        self.assertTrue(out['screen_proof']);self.assertEqual(observer.last_levels,[26,26])
        self.assertTrue(observer.verify_final(self.post,out,'enhance'))
        changed=self.post.copy();x,y,w,h=observer._number_box(changed);changed[y:y+h,x:x+w]=0
        self.assertFalse(observer.verify_final(changed,out,'enhance'));self.assertFalse(self.service.clicks)
    def test_pending_level_lower_bound_rejects_partial_ocr_without_forcing_result(self):
        from unittest.mock import patch
        observer=self.observer();observer.prepare_and_select(9);observer.minimum_level=40
        with patch('tools.ocr_support.read_growth_number_mdt',return_value={'value':4,'confidence':.99}):
            self.assertEqual(observer.read_result_pair(),{'screen_proof':False})
        self.assertEqual(observer.last_reason,'이전 확인 수치보다 낮음');self.assertFalse(self.service.clicks)
    def test_result_only_two_reads_must_match_and_never_authorize_action(self):
        from unittest.mock import patch
        observer=self.observer();observer.prepare_and_select(9);observer.minimum_level=40
        with patch('tools.ocr_support.read_growth_number_mdt',side_effect=[{'value':40,'confidence':.99},{'value':41,'confidence':.99}]):
            self.assertEqual(observer.read_result_pair(),{'screen_proof':False})
        self.assertEqual(observer.last_reason,'결과 수치 불일치 또는 시간 초과')
        with patch('tools.ocr_support.read_growth_number_mdt',side_effect=[{'value':41,'confidence':.99},{'value':41,'confidence':.99}]):
            result=observer.read_result_pair()
        self.assertTrue(result['screen_proof']);self.assertEqual(result['source'],'native_mdt_result_only')
        self.assertIsNone(result['first'].enhance_available);self.assertFalse(self.service.clicks)
    def test_pending_rescan_matches_unique_saved_icon_without_input(self):
        from owner_gear_decision_candidate import Observation
        from owner_gear_identity_candidate import IconIdentity
        reader=IconIdentity(actual,self.service.detector);identity=reader(self.pre,9,False)
        self.assertIsNotNone(identity)
        old=Observation(400,100.,'server / character',identity,'growth-slot:9','희귀',25,None,None,True,None,None)
        # An unrelated selected cell hides its identity, so it cannot be
        # excluded from a uniqueness check safely.
        with self.assertRaises(Hold):pending_readers_factory(self.service,self.context,'server / character',{'kind':'enhance','before':old})
        self.assertFalse(self.service.clicks)
    def test_real_post_41_list_matches_legacy_40_excluding_digits(self):
        from owner_gear_intent_store_candidate import IntentStore
        from owner_gear_native_install_candidate import _same_stable_icon
        path=bootstrap.A/'settings/owner-gear-settings-2a6715f4a2d11f31df0c102a-intent.json'
        pending=IntentStore(path).pending()
        if not pending or pending['before'].enhancement!=40:self.skipTest('실제 이전 기록 보존 상태 아님')
        for n in (1,2):
            frame=np.asarray(Image.open(Path(__file__).parent/f'live_fixtures/gear_list_0241_native_{n}.png').convert('RGB')).copy()
            self.service.pre=frame;self.service.phase='pre'
            observer,index=pending_readers_factory(self.service,self.context,pending['before'].character,pending)
            self.assertEqual(index,2);self.assertEqual(observer.logical_identity,pending['before'].item)
        a=np.zeros((18,18,3),dtype=np.uint8);b=a.copy();b[10:,10:]=255
        self.assertTrue(_same_stable_icon(a,b));b[0,0]=1;self.assertFalse(_same_stable_icon(a,b))
        self.assertFalse(self.service.clicks)
    def test_actual_40_to_41_pending_can_reveal_selected_item_without_consumption(self):
        from unittest.mock import patch
        from owner_gear_decision_candidate import Observation
        import base64,hashlib,time
        root=bootstrap.A/'logs/scene-corpus'
        original=np.asarray(Image.open(Path(__file__).parent/'live_fixtures/gear_list_native_1.png').convert('RGB')).copy()
        selected=np.asarray(Image.open(root/'20261102/20261102T020105-ce715b40/screen.png').convert('RGB')).copy()
        decoy=np.asarray(Image.open(root/'20261101/20261101T162248-0042c2bf/screen.png').convert('RGB')).copy()
        rows=actual.inspect_growth_equipment(self.service.detector,original);s=next(r['slot'] for r in rows if r['index']==2)
        x,y=s['cell_x']+8,s['cell_y']+8;crop=original[y:y+18,x:x+18]
        token='icon:'+hashlib.sha256(crop.tobytes()).hexdigest()
        pending={'kind':'enhance','before':Observation(1,10.,'test-character',token,'growth-slot:2','일반',40,None,None,True,None,None),
                 'item_icon':base64.b64encode(crop.tobytes()).decode('ascii')}
        self.service.post=selected;self.service.phase='post';self.context.wait=lambda s:time.sleep(.02);choices=[]
        def choose(service,row):choices.append(row['index']);service.post=decoy
        with patch.object(actual,'select_growth_equipment',side_effect=choose):
            observer,index=pending_readers_factory(self.service,self.context,'test-character',pending)
        self.assertEqual(choices,[1]);self.assertEqual(index,2);self.assertEqual(observer.logical_identity,token)
        self.assertFalse(self.service.clicks)
    def test_corrupt_persisted_icon_cannot_authorize_identity(self):
        import base64
        from owner_gear_decision_candidate import Observation
        pending={'kind':'enhance','before':Observation(1,10.,'test-character','icon:'+'0'*64,'growth-slot:2','일반',40,None,None,True,None,None),
                 'item_icon':base64.b64encode(bytes(18*18*3)).decode('ascii')}
        with self.assertRaises(Hold):pending_readers_factory(self.service,self.context,'test-character',pending)
        self.assertFalse(self.service.clicks)
    def test_legacy_real_sent_record_reference_recovered_from_bounded_history(self):
        from owner_gear_native_install_candidate import _legacy_intent_icon
        from owner_gear_intent_store_candidate import IntentStore
        import hashlib
        path=bootstrap.A/'settings/owner-gear-settings-2a6715f4a2d11f31df0c102a-intent.json'
        pending=IntentStore(path).pending()
        if not pending or pending['before'].enhancement!=40:self.skipTest('실제 이전 기록 보존 상태 아님')
        ref=_legacy_intent_icon(self.service,actual,pending['before'],pending)
        self.assertIsNotNone(ref)
        self.assertEqual('icon:'+hashlib.sha256(ref.tobytes()).hexdigest(),pending['before'].item)
        self.assertFalse(self.service.clicks)
    def test_real_legacy_pending_can_reselect_with_original_historical_reference(self):
        from unittest.mock import patch
        from owner_gear_intent_store_candidate import IntentStore
        import time
        path=bootstrap.A/'settings/owner-gear-settings-2a6715f4a2d11f31df0c102a-intent.json'
        pending=IntentStore(path).pending()
        if not pending or pending['before'].enhancement!=40:self.skipTest('실제 이전 기록 보존 상태 아님')
        self.service.post=np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261102/20261102T020105-ce715b40/screen.png').convert('RGB')).copy()
        decoy=np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261101/20261101T162248-0042c2bf/screen.png').convert('RGB')).copy()
        self.service.phase='post';self.context.wait=lambda s:time.sleep(.02);choices=[]
        def choose(service,row):choices.append(row['index']);service.post=decoy
        with patch.object(actual,'select_growth_equipment',side_effect=choose):
            observer,index=pending_readers_factory(self.service,self.context,pending['before'].character,pending)
        self.assertEqual((choices,index),([1],2));self.assertEqual(observer.logical_identity,pending['before'].item)
        self.assertFalse(self.service.clicks)
    def test_legacy_reveal_prevents_selection_after_identity_change(self):
        from unittest.mock import patch
        from owner_gear_intent_store_candidate import IntentStore
        import time
        path=bootstrap.A/'settings/owner-gear-settings-2a6715f4a2d11f31df0c102a-intent.json'
        pending=IntentStore(path).pending()
        if not pending or pending['before'].enhancement!=40:self.skipTest('실제 이전 기록 보존 상태 아님')
        self.service.post=np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261102/20261102T020105-ce715b40/screen.png').convert('RGB')).copy()
        self.service.phase='post';self.context.wait=lambda s:time.sleep(.02)
        with patch.object(actual,'select_growth_equipment') as choose:
            with self.assertRaises(Hold):pending_readers_factory(self.service,self.context,pending['before'].character,pending,identity_check=lambda:False)
        choose.assert_not_called();self.assertFalse(self.service.clicks)
    def test_confirmed_progress_continues_same_visible_item_after_call_limit(self):
        from owner_gear_identity_candidate import IconIdentity
        identity='resume-priority';reader=IconIdentity(actual,self.service.detector);token=reader(self.pre,9,False)
        self.assertIsNotNone(token);revision=Store(bootstrap.A,identity).revision()
        _candidate_continuation[identity]=(9,token,revision);_candidate_cursor[identity]=9
        self.addCleanup(lambda:_candidate_continuation.pop(identity,None));self.addCleanup(lambda:_candidate_cursor.pop(identity,None))
        targets={'일반':{'enabled':True},'희귀':{'enabled':True},'영웅':{'enabled':True}}
        observer,index=native_readers_factory(self.service,self.context,identity,targets)
        self.assertEqual(index,9);self.assertFalse(self.service.clicks)
    def test_selected_continuation_rechecks_by_temporarily_selecting_other_worn_item(self):
        from unittest.mock import patch
        from owner_gear_identity_candidate import IconIdentity
        import time
        self.context.wait=lambda seconds:time.sleep(.02)
        identity='resume-selected';reader=IconIdentity(actual,self.service.detector);token=reader(self.pre,9,False)
        self.assertEqual(reader(self.post,9,True),token)
        previous=Observer(self.service,self.context,identity,actual,reader,lambda f:{'verified':False})
        previous.ticket={'index':9,'identity':token};self.service.adapter._owner_growth_observer=previous
        third=np.asarray(Image.open(bootstrap.A/'logs/scene-corpus/20261101/20261101T162248-0042c2bf/screen.png').convert('RGB')).copy()
        revision=Store(bootstrap.A,identity).revision();_candidate_continuation[identity]=(9,token,revision)
        self.addCleanup(lambda:_candidate_continuation.pop(identity,None));self.addCleanup(lambda:_candidate_cursor.pop(identity,None))
        self.service.phase='post';calls=[]
        def choose(service,row):calls.append(row['index']);service.post=third
        targets={'일반':{'enabled':True},'희귀':{'enabled':True},'영웅':{'enabled':True}}
        with patch.object(actual,'select_growth_equipment',side_effect=choose):
            observer,index=native_readers_factory(self.service,self.context,identity,targets)
        self.assertEqual(calls,[1]);self.assertEqual(index,9);self.assertFalse(self.service.clicks)
    def test_opt_in_native_wrapper_delegates_or_runs_one_fake_step(self):
        from types import SimpleNamespace
        root=Path(self.temp.name);config=root/'profiles/DKB/ocr_regions.json';config.parent.mkdir(parents=True)
        config.write_bytes((bootstrap.A/'profiles/DKB/ocr_regions.json').read_bytes())
        self.service.adapter.project.root=root;self.service.context=self.context
        calls=[]
        def original(service,*,blessing=False):calls.append(blessing);return 'original'
        module=SimpleNamespace(run_growth_equipment=original)
        def factory(service,context,identity,targets):
            return Observer(service,context,identity,self.native,self.identity,self.resources,clock=self.clock),9
        install(module,lambda service:'server / character',factory,clock=self.clock)
        self.assertEqual(module.run_growth_equipment(self.service),'original')
        self.settings(30)
        self.assertFalse(module.run_growth_equipment(self.service,blessing=True))
        self.assertFalse(module.run_growth_equipment(self.service))
        self.assertEqual(calls,[False]);self.assertEqual(len(self.service.clicks),1)
        # Current fake post-reading does not advance, so durable pending blocks retry.
        self.service.phase='pre'
        self.assertFalse(module.run_growth_equipment(self.service));self.assertEqual(len(self.service.clicks),1)
        self.assertEqual(self.native.selected,[9])
    def test_enabled_wrapper_without_readers_never_falls_back(self):
        from types import SimpleNamespace
        self.service.adapter.project.root=Path(self.temp.name);self.service.context=self.context
        self.settings(30);calls=[]
        module=SimpleNamespace(run_growth_equipment=lambda *a,**k:calls.append('original'))
        install(module,lambda service:'server / character',None,clock=self.clock)
        self.assertFalse(module.run_growth_equipment(self.service));self.assertEqual(calls,[]);self.assertFalse(self.service.clicks)

if __name__=='__main__':unittest.main()
