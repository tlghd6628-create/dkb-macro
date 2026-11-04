exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import json, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
import owner_feature_checks_candidate as checks
from owner_feature_check_status_candidate import status, stage_label


def root_with(values, extra=None):
    folder = Path(tempfile.mkdtemp(prefix='dkb-check-'))
    (folder/'profiles/DKB/templates').mkdir(parents=True)
    (folder/'profiles/DKB/config').mkdir(parents=True)
    (folder/'settings').mkdir(parents=True)
    (folder/'settings/auto-settings.json').write_text(
        json.dumps({'version': 1, 'values': values}, ensure_ascii=False), encoding='utf-8')
    return folder


class ContractStage(unittest.TestCase):
    def test_settings_off_is_a_config_stage_not_a_recognition_hold(self):
        root = root_with({'auto_growth.equipment.enabled': False})
        item = {'id': 'gear', 'name': '장비 성장', 'settings': ['auto_growth.equipment.enabled']}
        row = checks.inspect_contract(root, item, checks.load_values(root))
        self.assertEqual((row['stage'], row['finding']), ('config', 'settings_off'))
        self.assertEqual(row['settings'], '꺼짐')
        self.assertEqual(status(row), '설정 꺼짐')

    def test_missing_setting_key_is_reported_separately(self):
        root = root_with({})
        item = {'id': 'gear', 'name': '장비 성장', 'settings': ['auto_growth.equipment.enabled']}
        row = checks.inspect_contract(root, item, checks.load_values(root))
        self.assertEqual((row['stage'], row['finding']), ('config', 'settings_missing'))
        self.assertEqual(status(row), '설정 누락')

    def test_missing_template_is_a_contract_error(self):
        root = root_with({'auto_growth.equipment.enabled': True})
        item = {'id': 'gear', 'name': '장비 성장', 'settings': ['auto_growth.equipment.enabled'],
                'templates': ['없는이미지.png']}
        row = checks.inspect_contract(root, item, checks.load_values(root))
        self.assertEqual((row['stage'], row['finding']), ('contract', 'contract_error'))
        self.assertEqual(row['result'], '오류')

    def test_disabled_feature_is_unsupported_not_a_failure(self):
        root = root_with({'auto_rewards.album.enabled': True})
        item = {'id': 'album', 'name': '화첩', 'settings': ['auto_rewards.album.enabled'], 'disabled_by_user': True}
        row = checks.inspect_contract(root, item, checks.load_values(root))
        self.assertEqual((row['stage'], row['finding']), ('unsupported', 'disabled'))
        self.assertEqual(status(row), '사용 불가')


class ObservationStage(unittest.TestCase):
    def test_menu_failure_keeps_its_stage(self):
        stage, finding = checks._observation_stage(
            {'verified': False, 'detail': '메뉴 화면 두 번 확인 실패 · 실행 없음'}, False, False)
        self.assertEqual((stage, finding), ('menu', 'menu_unrecognized'))

    def test_probe_without_decision_is_action_ready_not_passed(self):
        stage, finding = checks._observation_stage({'verified': True}, True, False)
        self.assertEqual((stage, finding), ('action_ready', 'decision_not_probed'))
        self.assertEqual(stage_label({'stage': stage, 'finding': finding}), '실행 판정 미연결')
        self.assertEqual(status({'result': '확인 필요', 'stage': stage, 'finding': finding}), '실행 판정 미연결')


class StopNavigation(unittest.TestCase):
    def catalog(self):
        return [
            {'id': 'a', 'name': '첫 항목', 'settings': ['a.on']},
            {'id': 'b', 'name': '둘째 항목', 'settings': ['b.on']},
        ]

    def test_unknown_screen_stops_further_navigation_and_keeps_evidence(self):
        root = root_with({'a.on': True, 'b.on': True})
        rows = []

        def probe(item, cancel):
            return {'verified': False, 'screen': '현재 화면 확인 필요', 'detail': '현재 화면을 유지합니다',
                    'stage': 'menu', 'finding': 'field_not_proven', 'stop_navigation': True,
                    'evidence_file': 'logs/feature-checks/screens/x.png'}

        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()):
            report = checks.run_checks(root, ['a', 'b'], rows.append, threading.Event(), probe=probe)
        self.assertEqual(report['rows'][0]['stage'], 'menu')
        self.assertEqual(report['rows'][1]['result'], '확인 필요')
        self.assertEqual((report['rows'][1]['stage'], report['rows'][1]['finding']), ('skipped', 'navigation_stopped'))
        self.assertEqual(report['stopped_after']['id'], 'a')
        self.assertEqual(report['rows'][1]['evidence_file'], 'logs/feature-checks/screens/x.png')
        self.assertFalse(report['gameplay_execution_tested'])

    def test_verified_menu_probe_never_reports_success(self):
        root = root_with({'a.on': True})
        rows = []
        probe = lambda item, cancel: {'verified': True, 'decision_verified': False, 'screen': '성장 메뉴',
                                      'detail': '메뉴 인식 확인 · 실행 없음', 'stage': 'action_ready',
                                      'finding': 'decision_not_probed', 'values_verified': True}
        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()):
            report = checks.run_checks(root, ['a'], rows.append, threading.Event(), probe=probe)
        row = report['rows'][0]
        self.assertEqual(row['result'], '확인 필요')
        self.assertNotEqual(row['display_status'], '정상')
        self.assertTrue(row['values_verified'])


class ConfigOff(unittest.TestCase):
    def catalog(self):
        return [{'id': 'a', 'name': 'A', 'settings': ['a.on']}]

    def test_off_is_not_probed_and_keeps_its_outcome(self):
        root = root_with({'a.on': False})
        calls = []
        probe = lambda item, cancel: calls.append(item['id']) or {'verified': True, 'decision_verified': True}
        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()):
            report = checks.run_checks(root, ['a'], lambda row: None, threading.Event(), probe=probe)
        self.assertEqual(calls, [], 'a settings-off feature must not open menus')
        row = report['rows'][0]
        self.assertEqual((row['stage'], row['finding']), ('config', 'settings_off'))
        self.assertEqual(row['steps'][-1], {'stage': 'menu', 'status': 'not_probed'})

    def test_probe_off_opt_in_runs_the_probe(self):
        root = root_with({'a.on': False})
        calls = []
        probe = lambda item, cancel: calls.append(item['id']) or {'verified': True, 'stage': 'action_ready', 'finding': 'decision_not_probed'}
        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()):
            checks.run_checks(root, ['a'], lambda row: None, threading.Event(), probe=probe, probe_off=True)
        self.assertEqual(calls, ['a'])


class AfterStop(unittest.TestCase):
    def catalog(self):
        return [{'id': 'a', 'name': 'A', 'settings': ['a.on']},
                {'id': 'b', 'name': 'B', 'settings': ['b.on'], 'templates': ['없는이미지.png']},
                {'id': 'c', 'name': 'C', 'settings': ['c.on']}]

    def test_remaining_items_keep_offline_contract_evidence(self):
        root = root_with({'a.on': True, 'b.on': True, 'c.on': True})
        probe = lambda item, cancel: {'verified': False, 'screen': '인식 실패', 'detail': '메뉴 화면 두 번 확인 실패',
                                      'stage': 'menu', 'finding': 'menu_unrecognized', 'stop_navigation': True,
                                      'steps': [{'stage': 'menu', 'status': 'unrecognized'}]}
        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()):
            report = checks.run_checks(root, ['a', 'b', 'c'], lambda row: None, threading.Event(), probe=probe)
        rows = {row['id']: row for row in report['rows']}
        self.assertEqual((rows['b']['stage'], rows['b']['finding']), ('contract', 'contract_error'))
        self.assertEqual(rows['b']['result'], '오류')
        self.assertEqual((rows['c']['stage'], rows['c']['finding']), ('skipped', 'navigation_stopped'))
        self.assertTrue(rows['c']['contract_ok'], 'a later item must keep its wiring result')
        self.assertEqual(rows['c']['settings'], '켜짐')
        self.assertIn({'stage': 'menu', 'status': 'skipped'}, rows['c']['steps'])

    def test_steps_are_ordered_settings_wiring_then_live(self):
        root = root_with({'a.on': True})
        probe = lambda item, cancel: {'verified': True, 'decision_verified': False, 'stage': 'action_ready',
                                      'finding': 'decision_not_probed', 'values_verified': True,
                                      'steps': [{'stage': 'menu', 'status': 'opened'},
                                                {'stage': 'values', 'status': 'read'},
                                                {'stage': 'decision', 'status': 'not_connected'}]}
        with patch('owner_feature_check_catalog_candidate.CHECKS', self.catalog()[:1]):
            report = checks.run_checks(root, ['a'], lambda row: None, threading.Event(), probe=probe)
        stages = [step['stage'] for step in report['rows'][0]['steps']]
        self.assertEqual(stages, ['settings', 'wiring', 'menu', 'values', 'decision'])


class Coverage(unittest.TestCase):
    def test_coverage_is_reported_and_names_the_unprobed_features(self):
        cov = checks.coverage()
        from owner_feature_check_catalog_candidate import CHECKS
        self.assertEqual(cov['total'], len(CHECKS))
        self.assertGreater(cov['menu_probe'], 20)
        self.assertIn('hunt', cov['unprobed'])
        self.assertEqual(cov['disabled'], 1)
        self.assertEqual(cov['schedule_preview'], 1)
        self.assertEqual(cov['unprobed_reasons']['raid'], 'admission_prohibited')
        self.assertEqual(cov['unprobed_reasons']['hunt'], 'config_only')
        self.assertEqual(cov['unprobed_reasons']['coupon'], 'no_nav_anchor')


if __name__ == '__main__':
    unittest.main(verbosity=2)
