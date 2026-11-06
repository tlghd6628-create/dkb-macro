"""The native coupon record follows the character on one PC. Temporary files only; never a game test."""
from pathlib import Path
import sys,json,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_startup_receipts as r


class Scope(unittest.TestCase):
    def test_swap_keeps_each_characters_record(self):
        with tempfile.TemporaryDirectory() as root:
            s=Path(root)/'settings';s.mkdir();main=s/'coupon_results.json'
            main.write_text(json.dumps({'characters':{'{"pc_alias": "1"}':{'A':{'completed':True}}}}),encoding='utf-8')
            (s/'owner-coupon-owner.json').write_text(json.dumps({'owner':'무이2|홍짱군'}),encoding='utf-8')
            r.coupon_scope(root,{'server_name':'무이2','character_name':'짱군네'})
            self.assertFalse(main.exists())
            main.write_text(json.dumps({'new':1}),encoding='utf-8')
            r.coupon_scope(root,{'server_name':'무이2','character_name':'홍짱군'})
            self.assertIn('pc_alias',main.read_text(encoding='utf-8'))
            r.coupon_scope(root,{'server_name':'무이2','character_name':'짱군네'})
            self.assertEqual(json.loads(main.read_text(encoding='utf-8')),{'new':1})
    def test_same_character_touches_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            s=Path(root)/'settings';s.mkdir();main=s/'coupon_results.json';main.write_text('{}',encoding='utf-8')
            (s/'owner-coupon-owner.json').write_text(json.dumps({'owner':'무이2|홍짱군'}),encoding='utf-8')
            r.coupon_scope(root,{'server_name':'무이2','character_name':'홍짱군'});self.assertTrue(main.exists())


if __name__=='__main__':unittest.main()
