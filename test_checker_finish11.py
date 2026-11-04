"""Checker verdicts under injected faults. Fake probes only; no game input."""
import bootstrap
import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
import owner_feature_check_gear_candidate as gear
import owner_feature_checks_candidate as checks
from owner_feature_check_status_candidate import assessment,verification
from owner_growth_reading import worst_row


def item(key,**extra):return {'id':key,'name':key,'group':'g','settings':[],'native':[],'templates':[],**extra}


class Faults(unittest.TestCase):
    def run_with(self,items,probe):
        tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch');self.addCleanup(tmp.cleanup)
        root=Path(tmp.name);(root/'profiles/DKB/templates').mkdir(parents=True);(root/'settings').mkdir()
        (root/'settings/auto-settings.json').write_text(json.dumps({'values':{}}),encoding='utf-8')
        rows={}
        with patch('owner_feature_check_catalog_candidate.CHECKS',items):
            report=checks.run_checks(root,[i['id'] for i in items],lambda row:rows.__setitem__(row['id'],row),threading.Event(),probe=probe)
        return report,rows
    def test_missing_image_is_an_error(self):
        report,rows=self.run_with([item('a',templates=['없는이미지.png'])],lambda *a:self.fail('no probe on a wiring error'))
        self.assertEqual(rows['a']['assessment']['outcome'],'error');self.assertIn('next_step',rows['a']['verification'])
    def test_missing_function_is_an_error(self):
        report,rows=self.run_with([item('a',native=[('owner_outcome','no_such_function')])],lambda *a:self.fail('no probe'))
        self.assertEqual(rows['a']['assessment']['outcome'],'error')
    def test_reading_failure_is_an_error_with_next_step(self):
        probe=lambda i,c:dict(verified=True,stage='values',finding='values_unreadable',detail='판독 실패',steps=[])
        _,rows=self.run_with([item('a')],probe)
        self.assertEqual(rows['a']['assessment']['outcome'],'error');self.assertIn('판독',rows['a']['verification']['next_step'])
    def test_recovered_menu_failure_does_not_stop_later_items(self):
        seen=[]
        def probe(i,c):
            seen.append(i['id'])
            if i['id']=='a':return dict(verified=False,stage='menu',finding='probe_error',detail='버튼',steps=[],stop_navigation=False)
            return dict(verified=True,stage='action_ready',finding='decision_not_probed',detail='메뉴',steps=[])
        report,rows=self.run_with([item('a'),item('b')],probe)
        self.assertEqual(seen,['a','b']);self.assertEqual(rows['a']['assessment']['outcome'],'error')
        self.assertEqual(rows['b']['assessment']['outcome'],'unverified');self.assertIsNone(report['stopped_after'])
    def test_unrecovered_menu_failure_marks_the_rest_unverified_with_a_reason(self):
        probe=lambda i,c:dict(verified=False,stage='menu',finding='probe_error',detail='버튼',steps=[],stop_navigation=True)
        report,rows=self.run_with([item('a'),item('b')],probe)
        self.assertEqual(rows['b']['finding'],'navigation_stopped');self.assertEqual(rows['b']['assessment']['outcome'],'unverified')
        self.assertTrue(rows['b']['verification']['next_step'])
    def test_every_row_carries_verification_and_no_gameplay_claim(self):
        probe=lambda i,c:dict(verified=True,stage='action_ready',finding='ready',values_verified=True,detail='준비',steps=[])
        report,rows=self.run_with([item('a'),item('off',settings=['없는설정'])],probe)
        self.assertFalse(report['gameplay_execution_tested'])
        for row in rows.values():
            self.assertIn('verification',row);self.assertFalse(row['verification']['gameplay_executed'])
        self.assertTrue(report['verification_levels'])
    def test_catalog_has_a_next_step_for_each_unverified_finding_used(self):
        for finding in ('decision_not_probed','projection_only','config_only','scheduled','runtime_connected','anchor_unverified','navigation_stopped'):
            self.assertNotEqual(verification(dict(stage='action_ready',finding=finding,contract_ok=True))['next_step'],'저장된 화면과 로그로 원인 확인')


class AllTargets(unittest.TestCase):
    def reading(self,index,level,**kw):
        return dict(verified=True,index=index,grade='희귀',enhancement=level,native_ready=False,materials='재료 부족',targets={'read':1,'total':3,'unit':'장비'},**kw)
    def diagnose(self,readings,goal=50):
        seq=iter(readings)
        with patch('owner_feature_check_growth_candidate.read_enhancement',side_effect=lambda s,c,done=():next(seq)),patch.object(gear,'goals',return_value={'grades':{'희귀':{'enabled':True,'enhance':goal}}}):
            return gear.diagnose(None,None,None,'c')
    def test_reads_every_worn_item_and_reports_the_range(self):
        result=self.diagnose([self.reading(1,50),self.reading(2,50),self.reading(3,50),{'verified':False,'exhausted':True}])
        self.assertEqual(result['finding'],'goal_reached');self.assertEqual(result['targets'],{'read':3,'total':3,'unit':'장비'})
    def test_one_item_not_at_goal_decides_the_feature(self):
        result=self.diagnose([self.reading(1,50),self.reading(2,41),self.reading(3,50),{'verified':False,'exhausted':True}])
        self.assertEqual(result['finding'],'materials_short');self.assertIn('41',result['detail'])
    def test_a_read_failure_stops_and_is_not_hidden(self):
        result=self.diagnose([self.reading(1,50),{'verified':False,'detail':'판독 실패'}])
        self.assertEqual(result['finding'],'values_unreadable');self.assertEqual(result['targets']['read'],2)
    def test_order_prefers_problems(self):
        self.assertEqual(worst_row([{'finding':'goal_reached'},{'finding':'ready'},{'finding':'values_unreadable'}])['finding'],'values_unreadable')
    def test_range_appears_in_the_verdict(self):
        row=dict(stage='action_ready',finding='goal_reached',screen_verified=True,values_verified=True,targets={'read':2,'total':3,'unit':'가호'})
        self.assertIn('가호 2/3',assessment(row)['label'])


class CloseWindow(unittest.TestCase):
    def test_close_buttons_exist_in_the_real_profile(self):
        from roi_runtime import RoiDetector
        from owner_feature_check_live_candidate import CLOSE,NAV
        detector=RoiDetector(bootstrap.A/'profiles/DKB',list(CLOSE.values()))
        for name in CLOSE.values():self.assertIn(name,detector.entries);self.assertIn(name,NAV)
    def probe(self,*,visible,fields):
        from owner_feature_check_live_candidate import MenuProbe
        clicks=[];frame=np.zeros((479,897,3),np.uint8);seen=iter(fields)
        probe=MenuProbe(None,S(),threading.Event());probe.context=S(checkpoint=lambda:None,wait=lambda n:None)
        detector=S(find=lambda name,f,**kw:(5,5,(1,1,9,9)) if name in visible else None)
        probe.service=S(check=lambda:None,capture=lambda:frame,detector=detector,click_hit=clicks.append)
        probe.field=lambda f:next(seen,False)
        return probe,clicks
    def test_open_window_is_closed_by_its_own_button_during_recovery(self):
        probe,clicks=self.probe(visible={'버튼_X_창'},fields=[False,False,True,True])
        self.assertTrue(probe.recover());self.assertEqual(len(clicks),1)
    def test_no_known_window_never_presses_anything(self):
        probe,clicks=self.probe(visible=set(),fields=[False,False])
        self.assertFalse(probe.recover());self.assertEqual(clicks,[])
    def test_known_guide_closes_through_its_button(self):
        probe,clicks=self.probe(visible={'버튼_X_창','체크_길라잡이'},fields=[False,False,True,True])
        probe.known='guide';self.assertTrue(probe.close_menu());self.assertEqual(len(clicks),1)


if __name__=='__main__':unittest.main()
