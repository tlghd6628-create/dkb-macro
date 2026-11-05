import json
import os
import tempfile
import unittest
import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from owner_shop_settings_candidate import ShopSettingsStore, ShopSettings, initial_rows, validate


class ShopSettingsTests(unittest.TestCase):
    def test_defaults_include_both_shops_are_disabled_and_mark_uncertain(self):
        rows = initial_rows()
        self.assertEqual(len(rows), 42)
        self.assertTrue(all(not row['enabled'] for row in rows))
        self.assertTrue(all('미확인' in row['verification'] for row in rows if row['shop'] == 'remote'))
        validate(rows)

    def test_roundtrip_and_character_isolation(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            store = ShopSettingsStore(directory, 'server/character')
            rows = store.read()
            rows[0].update(enabled=True, mode='max', quantity=3)
            rows.append(dict(shop='town', name='새 품목', enabled=True, mode='quantity', quantity=7,
                             source='사용자 입력', verification='사용자 추가·게임 확인 필요'))
            store.write(rows)
            self.assertEqual(store.read(), rows)
            self.assertIsNone(store.read_document()['coin_reserve'])
            store.write(rows, 150000)
            self.assertEqual(store.read_document()['coin_reserve'], 150000)
            with self.assertRaises(ValueError): store.write(rows, -1)
            self.assertFalse(ShopSettingsStore(directory, 'other').read()[0]['enabled'])
            self.assertNotIn('server', store.path.name)

    def test_rejects_duplicate_invalid_or_unknown_character(self):
        with self.assertRaises(ValueError): ShopSettingsStore('.', '')
        rows = initial_rows()
        with self.assertRaises(ValueError): validate(rows + [dict(rows[0])])
        rows[0]['quantity'] = 0
        with self.assertRaises(ValueError): validate(rows)

    def test_corrupt_and_future_format_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            store = ShopSettingsStore(directory, 'test')
            store.path.parent.mkdir(parents=True)
            store.path.write_text(json.dumps({'version': 2, 'items': []}), encoding='utf-8')
            with self.assertRaises(ValueError): store.read()
            self.assertEqual(json.loads(store.path.read_text(encoding='utf-8'))['version'], 2)

    def test_stale_window_cannot_erase_newer_settings_and_metadata_survives(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            store=ShopSettingsStore(directory,'test')
            initial,revision=store.snapshot()
            store.write(initial['items'],150000,expected_revision=revision)
            document=json.loads(store.path.read_text(encoding='utf-8'));document['custom_note']={'keep':True}
            store.path.write_text(json.dumps(document,ensure_ascii=False),encoding='utf-8')
            latest,revision=store.snapshot()
            latest['items'][0]['enabled']=True
            store.write(latest['items'],200000,expected_revision=revision)
            with self.assertRaises(ValueError):store.write(initial['items'],0,expected_revision=revision)
            saved=store.read_document()
            self.assertEqual(saved['custom_note'],{'keep':True})
            self.assertEqual(saved['coin_reserve'],200000)
            self.assertTrue(saved['items'][0]['enabled'])

    def test_unused_legacy_gold_metadata_preserved_without_new_field(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            store=ShopSettingsStore(directory,'test');doc,revision=store.snapshot()
            self.assertNotIn('gold_spend_limit',doc);self.assertFalse(hasattr(store,'gold_limit'))
            store.write(doc['items'],150000,expected_revision=revision)
            self.assertNotIn('gold_spend_limit',store.read_document())
            raw=json.loads(store.path.read_text(encoding='utf-8'));raw['gold_spend_limit']={'legacy':'preserve'}
            store.path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
            latest,revision=store.snapshot();store.write(latest['items'],200000,expected_revision=revision)
            self.assertEqual(store.read_document()['gold_spend_limit'],{'legacy':'preserve'})
            self.assertEqual(store.read_document()['coin_reserve'],200000)

    def test_no_gold_widget_and_stale_window_protected(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
            root=tk.Tk();root.withdraw()
            try:
                first=ShopSettings(root,directory,'test');second=ShopSettings(root,directory,'test')
                first.window.withdraw();second.window.withdraw()
                self.assertFalse(hasattr(first,'gold_limit'));self.assertFalse(hasattr(first,'reserve'))
                first.enabled.set(False);first.save()
                second.enabled.set(True)
                with patch('owner_shop_settings_candidate.messagebox.showerror') as error:second.save()
                self.assertEqual(error.call_count,1);self.assertTrue(second.window.winfo_exists())
                store=ShopSettingsStore(directory,'test');self.assertNotIn('gold_spend_limit',store.read_document())
                self.assertIs(store.read_document()['enabled'],False)
            finally:root.destroy()


if __name__ == '__main__':
    unittest.main()
