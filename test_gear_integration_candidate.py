"""Fake worker tests; no installed program or game input."""
import os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
from owner_gear_decision_candidate import Observation
from owner_gear_step_guard_candidate import Guard
from owner_gear_settings_candidate import Store
from owner_gear_native_install_candidate import wrap_extras_decorator,wrap,install

class Context:
    def checkpoint(self):pass
    def wait(self,n):pass
class StoreFake:
    def pending(self):return None
class Service:
    def __init__(self,root):self.context=Context();self.adapter=SimpleNamespace(project=SimpleNamespace(root=root))
    def check(self):pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.getcwd());self.addCleanup(self.temp.cleanup)
        self.service=Service(self.temp.name);self.ident='서버 / 캐릭터'
        self.target={'enabled':True,'enhance':50,'breakthrough':3,'awaken':1}
        self.base=Observation(1,100.,self.ident,'item','slot','희귀',None,None,0,None,None,True)
        self.guard=Guard(self.service.context,StoreFake(),lambda:None,clock=lambda:100.3)
    def test_numeric_mismatch_gets_only_one_fresh_preinput_retry(self):
        from unittest.mock import patch,Mock
        document=Store(self.temp.name,self.ident).read();document['grades']['희귀']['enabled']=True;Store(self.temp.name,self.ident).write(document)
        observer=SimpleNamespace(prepare_and_select=Mock(),ticket={'grade':'희귀','identity':'same'},
          last_reason='강화 수치 불일치',last_levels=[1,16],last_frames=(),read_pair=Mock(),verify_final=Mock())
        with patch('owner_gear_native_install_candidate.run_configured_step',return_value='hold_screen_unverified') as action,patch('owner_gear_hold_capture_candidate.enqueue'):
            wrap(lambda *a,**kw:self.fail('native bulk'),lambda s:self.ident,lambda *a:(observer,1))(self.service)
        self.assertEqual(action.call_count,2)
    def test_icon_mismatch_is_not_retried_as_a_numeric_animation(self):
        from unittest.mock import patch,Mock
        document=Store(self.temp.name,self.ident).read();document['grades']['희귀']['enabled']=True;Store(self.temp.name,self.ident).write(document)
        observer=SimpleNamespace(prepare_and_select=Mock(),ticket={'grade':'희귀','identity':'same'},
          last_reason='장비 아이콘 불일치',last_levels=[],last_frames=(),read_pair=Mock(),verify_final=Mock())
        with patch('owner_gear_native_install_candidate.run_configured_step',return_value='hold_screen_unverified') as action,patch('owner_gear_hold_capture_candidate.enqueue'):
            wrap(lambda *a,**kw:self.fail('native bulk'),lambda s:self.ident,lambda *a:(observer,1))(self.service)
        self.assertEqual(action.call_count,1)
    def test_awakening_is_independent_of_enhancement_and_breakthrough(self):
        b=replace(self.base,sequence=2,captured_at=100.2)
        self.assertTrue(self.guard._eligible(self.base,b,self.target,'awaken'))
        self.assertFalse(self.guard._eligible(self.base,replace(b,awakening=1),self.target,'awaken'))
        self.assertFalse(self.guard._eligible(self.base,replace(b,awaken_available=None),self.target,'awaken'))
    def test_breakthrough_needs_paired_50_and_known_current_step(self):
        a=replace(self.base,enhancement=50,breakthrough=0,breakthrough_available=True)
        b=replace(a,sequence=2,captured_at=100.2)
        self.assertTrue(self.guard._eligible(a,b,self.target,'breakthrough'))
        self.assertFalse(self.guard._eligible(a,replace(b,enhancement=49),self.target,'breakthrough'))
        self.assertFalse(self.guard._eligible(a,replace(b,breakthrough=2),self.target,'breakthrough'))
        later=replace(a,enhancement=12,breakthrough=2)
        self.assertTrue(self.guard._eligible(later,replace(later,sequence=2,captured_at=100.2),self.target,'breakthrough'))
    def test_custom_settings_never_run_unbounded_extras(self):
        calls=[]
        def original(service):calls.append('enhance');return 'done'
        def decorate(original):
            def batch(service):calls.append('batch');return original(service)
            return batch
        document=Store(self.temp.name,self.ident).read()
        document['grades']['희귀']['enabled']=True
        Store(self.temp.name,self.ident).write(document)
        fn=wrap_extras_decorator(decorate,lambda service:self.ident)(original)
        self.assertEqual(fn(self.service),'done');self.assertEqual(calls,['enhance'])
    def test_awakening_without_result_reader_cannot_issue_input(self):
        from unittest.mock import patch
        document=Store(self.temp.name,self.ident).read();document['grades']['희귀']['enabled']=True;Store(self.temp.name,self.ident).write(document)
        def original(service):return True
        def decorate(inner):return inner
        factory=lambda service,context,identity,targets,kind:(lambda:None,lambda *a:True,lambda:None)
        with patch('owner_gear_native_install_candidate.run_configured_step') as action:
            wrap_extras_decorator(decorate,lambda s:self.ident,factory)(original)(self.service)
        action.assert_not_called()
    def test_awakening_separate_result_reader_and_cleanup_are_used(self):
        from unittest.mock import patch
        document=Store(self.temp.name,self.ident).read();document['grades']['희귀']['enabled']=True;Store(self.temp.name,self.ident).write(document)
        cleanup=[];post=lambda:None
        def original(service):return True
        def decorate(inner):return inner
        factory=lambda service,context,identity,targets,kind:(lambda:None,lambda *a:True,lambda:cleanup.append(True),post) if kind=='awaken' else None
        with patch('owner_gear_native_install_candidate.run_configured_step',return_value='pending_confirmation') as action,patch('owner_gear_native_install_candidate.reconcile_configured_step',return_value='observed_progress') as after:
            wrap_extras_decorator(decorate,lambda s:self.ident,factory)(original)(self.service)
        action.assert_called_once();self.assertIs(after.call_args.args[3],post);self.assertEqual(cleanup,[True])
    @__import__('unittest.mock',fromlist=['patch']).patch('owner_growth_reading.BREAKTHROUGH_ENABLED',True)
    def test_no_saved_settings_keeps_existing_native_route(self):
        calls=[]
        def original(service):calls.append('enhance');return 'done'
        def decorate(original):
            def batch(service):calls.append('batch');return original(service)
            return batch
        fn=wrap_extras_decorator(decorate,lambda service:self.ident)(original)
        self.assertEqual(fn(self.service),'done');self.assertEqual(calls,['batch','enhance'])
    def test_all_explicitly_disabled_does_not_run_original(self):
        Store(self.temp.name,self.ident).write(Store(self.temp.name,self.ident).read())
        calls=[]
        def original(service,*,blessing=False):calls.append(1);return True
        fn=wrap(original,lambda service:self.ident,None)
        self.assertFalse(fn(self.service));self.assertEqual(calls,[])
    def test_reconcile_only_without_pending_never_runs_growth_or_extras(self):
        Store(self.temp.name,self.ident).write(Store(self.temp.name,self.ident).read())
        self.service.adapter._owner_growth_reconcile_only=True;calls=[]
        def original(service,*,blessing=False):calls.append('unsafe');return True
        fn=wrap(original,lambda service:self.ident,None)
        self.assertTrue(fn(self.service));self.assertEqual(calls,[])
        def decorate(inner):
            def batch(service):calls.append('extras');return inner(service)
            return batch
        combined=wrap_extras_decorator(decorate,lambda service:self.ident)(fn)
        self.assertTrue(combined(self.service));self.assertEqual(calls,[])
    def test_reconcile_only_retries_unknown_without_new_growth(self):
        from unittest.mock import patch
        from owner_gear_intent_store_candidate import IntentStore
        self.service.adapter._owner_growth_reconcile_only=True
        store=Store(self.temp.name,self.ident);document=store.read();store.write(document)
        path=store.path;intent=IntentStore(path.with_name(path.stem+'-intent.json'))
        previous=replace(self.base,character=self.ident,item='saved',slot='growth-slot:2',enhancement=40)
        intent.begin({'kind':'enhance','before':previous,'second':previous});intent.mark_sent()
        class Observer:
            last_reason='미확인';last_frames=()
            def prepare_and_select(self,index,**kwargs):return {'grade':'희귀'}
            def read_result_pair(self):return None
        calls=[]
        def recover(*args,**kwargs):
            calls.append('read')
            if len(calls)==1:return 'hold_result_unknown'
            intent.complete('observed_progress');return 'observed_progress'
        with patch('owner_gear_native_install_candidate.pending_readers_factory',return_value=(Observer(),2)),patch('owner_gear_native_install_candidate.reconcile_configured_step',side_effect=recover):
            self.assertTrue(wrap(lambda *a,**kw:self.fail('unexpected original'),lambda s:self.ident,None)(self.service))
        self.assertEqual(calls,['read','read']);self.assertIsNone(intent.pending())
    def test_direct_aliases_are_rebound_and_extras_install_is_idempotent(self):
        def growth(service,*,blessing=False):return True
        def decorate(original):return original
        native=SimpleNamespace(run_growth_equipment=growth)
        extras=SimpleNamespace(run_equipment_extras=decorate)
        alias=SimpleNamespace(run_growth_equipment=growth,run_equipment_extras=decorate)
        install(native,lambda s:self.ident,extra_module=extras,alias_modules=(alias,))
        self.assertIs(alias.run_growth_equipment,native.run_growth_equipment)
        self.assertIs(alias.run_equipment_extras,extras.run_equipment_extras)
        first=native.run_growth_equipment;second=extras.run_equipment_extras
        install(native,lambda s:self.ident,extra_module=extras,alias_modules=(alias,))
        self.assertIs(native.run_growth_equipment,first);self.assertIs(extras.run_equipment_extras,second)

if __name__=='__main__':unittest.main()
