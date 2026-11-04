exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import hashlib, json, tempfile, unittest
from pathlib import Path
import numpy as np
from PIL import Image
import owner_feature_check_extra_candidate as extra

LIVE = Path(r"C:\Users\홍이\Downloads\도깨비의 세계\owner\current_checks\live")
SERVER, NAME = '테스트서버', '테스트캐릭터'


def frame(name):
    return np.asarray(Image.open(LIVE/name).convert('RGB'))


def identity():
    payload = json.dumps([SERVER, NAME], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'configured-v1:' + hashlib.sha256(payload).hexdigest()


def make_root(values=None, timetable=None, hunt=None, profile=True):
    base = Path(tempfile.mkdtemp(prefix='dkb-extra-'))
    if profile:
        (base/'profiles/DKB').mkdir(parents=True)
    (base/'settings').mkdir()
    (base/'settings/auto-settings.json').write_text(
        json.dumps({'version': 1, 'values': values or {}}, ensure_ascii=False), encoding='utf-8')
    if timetable is not None:
        (base/'settings/owner-timetable-state.json').write_text(
            json.dumps(timetable, ensure_ascii=False), encoding='utf-8')
    (base/'settings/manager_identity.json').write_text(json.dumps({'server_name':SERVER,'character_name':NAME},ensure_ascii=False),encoding='utf-8')
    if hunt is not None:
        (base/'settings/owner-hunt-rules.json').write_text(json.dumps(hunt, ensure_ascii=False), encoding='utf-8')
        (base/'settings/manager_identity.json').write_text(
            json.dumps({'server_name': SERVER, 'character_name': NAME}, ensure_ascii=False), encoding='utf-8')
    return base


class Unsupported(unittest.TestCase):
    def test_product_absent_is_not_a_checker_gap(self):
        record = extra.diagnose('mangwi', root=make_root())
        self.assertEqual((record['stage'], record['finding']), ('unsupported', 'manual_only'))
        self.assertEqual(record['navigate'], [])
        self.assertFalse(record['committed'])

    def test_unknown_family_is_reported_as_missing_diagnostic(self):
        record = extra.diagnose('not_a_feature', root=make_root())
        self.assertEqual((record['stage'], record['finding']), ('unsupported', 'no_documented_diagnostic'))


class TimetableJob(unittest.TestCase):
    def test_off_is_config(self):
        record = extra.diagnose('tower', root=make_root({'auto_challenge.ascension_tower.enabled': False}))
        self.assertEqual((record['stage'], record['finding']), ('config', 'settings_off'))
        self.assertEqual(record['steps'][0], {'stage': 'settings', 'status': 'off'})

    def test_scheduled_job_reports_saved_state_without_claiming_execution(self):
        state = {'version': 1, 'characters': {SERVER+' / '+NAME: {
            'tower': {'at': '2026-11-02T15:00:00', 'status': 'pending', 'attempts': 0}}}}
        record = extra.diagnose('tower', root=make_root({'auto_challenge.ascension_tower.enabled': True}, timetable=state))
        self.assertEqual((record['stage'], record['finding']), ('action_ready', 'scheduled'))
        self.assertEqual(record['observed']['state']['status'], 'pending')
        self.assertIn('실제 실행 결과', record['unknown'])
        self.assertFalse(record['committed'])

    def test_other_character_record_is_never_reused(self):
        state={'version':1,'characters':{'다른서버 / 다른캐릭터':{'tower':{'at':'2099-01-01','status':'done'}}}}
        record=extra.diagnose('tower',root=make_root({'auto_challenge.ascension_tower.enabled':True},timetable=state))
        self.assertIsNone(record['observed']['state']);self.assertEqual(record['finding'],'schedule_unproven')

    def test_missing_enable_key_is_not_reported_as_off(self):
        record=extra.diagnose('tower',root=make_root())
        self.assertEqual(record['finding'],'settings_missing')


class Hunt(unittest.TestCase):
    def test_enabled_rules_project_without_choosing_a_route(self):
        rules = {'version': 1, 'characters': {identity(): [{'power': 100000, 'slot': 1}, {'power': 200000, 'slot': 2}]},
                 'stationary': {identity(): 3}}
        values = {'common.potion_and_favorite.enabled': True,
                  'common.potion_and_favorite.source': '저장위치',
                  'common.potion_and_favorite.slot': '1번'}
        record = extra.diagnose('hunt', root=make_root(values, hunt=rules))
        self.assertEqual((record['stage'], record['finding']), ('action_ready', 'projection_only'))
        self.assertEqual(record['observed']['rules'], 2)
        self.assertEqual(record['observed']['stationary'], 3)
        self.assertIn('runtime_route_unknown', [step['status'] for step in record['steps']])

    def test_off_is_config(self):
        record = extra.diagnose('hunt', root=make_root({'common.potion_and_favorite.enabled': False}))
        self.assertEqual((record['stage'], record['finding']), ('config', 'settings_off'))


class NavigationRequests(unittest.TestCase):
    def test_potion_settings_are_independent_of_weekly_purchase_goals(self):
        values={'common.potion_and_favorite.enabled':True,'common.potion_and_favorite.potion_tier':'1단물약'}
        root=make_root(values)
        record=extra.diagnose('potion',root=root)
        self.assertEqual(record['finding'],'projection_only');self.assertEqual(record['observed']['tier'],'1단물약')
    def test_unverified_anchor_returns_navigation_request_only(self):
        record = extra.diagnose('coupon', root=make_root({'main_quest.first_coupon.enabled': True}))
        self.assertEqual((record['stage'], record['finding']), ('action_ready', 'anchor_unverified'))
        self.assertEqual([step['name'] for step in record['navigate']],
                         ['버튼_전체매뉴', '버튼_전체매뉴_설정', '버튼_전체매뉴_설정_쿠폰등록'])
        self.assertIsNone(record['anchor'])
        self.assertFalse(record['committed'])

    def test_off_feature_requests_no_navigation(self):
        record = extra.diagnose('coupon', root=make_root({'main_quest.first_coupon.enabled': False}))
        self.assertEqual(record['navigate'], [])


class Readiness(unittest.TestCase):
    def test_quest_tab_from_real_frames_never_claims_acceptance(self):
        record = extra.readiness('main', (frame('mission-main.png'), frame('mission-story-groups.png')))
        self.assertEqual((record['stage'], record['finding']), ('action_ready', 'quest_tab_ready'))
        self.assertEqual(record['steps'][0], {'stage': 'menu', 'status': 'opened'})

    def test_non_quest_frame_is_not_ready(self):
        field = frame('b-move-field.png')
        record = extra.readiness('main', (field, field))
        self.assertEqual((record['stage'], record['finding']), ('menu', 'quest_tab_not_proved'))

    def test_inventory_panels_from_real_frame(self):
        inv = frame('inventory-member-icons.png')
        record = extra.readiness('inventory', (inv, inv))
        self.assertEqual((record['stage'], record['finding']), ('action_ready', 'inventory_ready'))
        field = frame('b-move-field.png')
        self.assertEqual(extra.readiness('inventory', (field, field))['finding'], 'inventory_not_proved')

    def test_single_frame_is_refused(self):
        record = extra.readiness('main', (frame('mission-main.png'),))
        self.assertEqual((record['stage'], record['finding']), ('menu', 'frame_missing'))


class PureProjection(unittest.TestCase):
    def test_diagnose_does_not_touch_the_filesystem(self):
        root = make_root({'auto_challenge.ascension_tower.enabled': True})
        before = sorted((p.name, p.stat().st_size) for p in root.rglob('*') if p.is_file())
        extra.diagnose('tower', root=root)
        extra.diagnose('hunt', root=root)
        extra.diagnose('potion', root=root, character='테스트캐릭터')
        after = sorted((p.name, p.stat().st_size) for p in root.rglob('*') if p.is_file())
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main(verbosity=2)
