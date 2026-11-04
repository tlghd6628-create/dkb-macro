"""Offline data provenance/consistency only; no game purchase or input."""
import hashlib, json, unittest, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
ROOT=Path(r'C:\Users\홍이\Downloads\FC_프로그램\도깨비의세계\테스트\DKB_로컬개발용_v0.9.3.1_20261031')
DATA=HERE/'skill_assets_candidate'

class DesiredAOE(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((DATA/'desired_aoe.json').read_text(encoding='utf-8'))
        self.old=json.loads((ROOT/'owner/skill_catalog.json').read_text(encoding='utf-8'))

    def test_user_cast_sequence_and_separate_equipment_slots(self):
        self.assertEqual(set(self.plan['presets']),{'aoe'})
        row=self.plan['presets']['aoe']; order=[x['id'] for x in row['order']]
        order.insert(row['ultimate_at'],row['ultimate']['id'])
        self.assertEqual(order,[68,84,65,89,59,25,55,63,64])
        self.assertEqual([x['id'] for x in row['slots']],[68,84,59,55,63,89,25,64])
        self.assertEqual(sum(x['style']=='파멸' for x in row['slots'][:5]),3)
        self.assertEqual({x['id'] for x in row['slots']},{x['id'] for x in row['order']})

    def test_names_and_styles_agree_with_frozen_catalog(self):
        row=self.plan['presets']['aoe']
        for item in row['slots']+[row['ultimate']]:
            original=self.old['all_skill_names'][item['name']]
            self.assertEqual((item['id'],item['style']),(original['id'],original['style']))

    def test_restored_original_assets_hashes(self):
        for sid,record in self.old['skills'].items():
            data=(DATA/'icons'/Path(record['icon']).name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),record['icon_sha256'])

    def test_new_icon_source_and_hash_are_not_game_match_proof(self):
        icon=self.plan['new_icon'];data=(DATA/icon['path']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),icon['sha256'])
        self.assertEqual(data[:4],b'RIFF');self.assertEqual(data[8:12],b'WEBP')
        self.assertFalse(icon['game_match_verified']);self.assertFalse(self.plan['game_ui_verified'])

    def test_candidate_catalog_preserves_original_and_does_not_authorize_single(self):
        from prepare_skill_catalog_candidate import create
        source=ROOT/'owner/skill_catalog.json';before=hashlib.sha256(source.read_bytes()).hexdigest()
        path=create();out=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
        self.assertEqual(out['presets']['single'],self.old['presets']['single'])
        self.assertFalse(out['candidate_notes']['single_auto_application_authorized'])
        self.assertFalse(out['candidate_notes']['icon_59_game_match_verified'])
        self.assertEqual(out['presets']['aoe'],self.plan['presets']['aoe'])
        self.assertEqual(set(out['skills']),set(self.old['skills'])|{'59'})
        for entry in out['skills'].values():
            self.assertEqual(hashlib.sha256((HERE/entry['icon']).read_bytes()).hexdigest(),entry['icon_sha256'])

if __name__=='__main__':unittest.main()
