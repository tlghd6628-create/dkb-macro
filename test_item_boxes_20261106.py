"""Per-box switches under 아이템 사용, from level 30. Fake values; never a game test."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import owner_item_boxes as b
import owner_equipment_boxes as e


class Switches(unittest.TestCase):
    def test_each_box_by_its_own_switch(self):
        # User 11-07: the master switch is gone; each box decides, and the hidden master follows them.
        self.assertTrue(b.enabled({b.MASTER:False},'weapon'))
        self.assertFalse(b.enabled({b.MASTER:True,b.key('weapon'):False},'weapon'))
        self.assertTrue(b.sync_master({b.MASTER:False})[b.MASTER])
        self.assertIsNone(b.sync_master({b.MASTER:True}))
        off={b.key(code):False for code,_ in b.BOXES}
        self.assertFalse(b.sync_master(dict(off,**{b.MASTER:True}))[b.MASTER])
    def test_plan_from_level_30_by_switch(self):
        worn={'무기':False,'팔찌':False,'반지':True}
        self.assertEqual(e.plan(worn,29,None,{b.MASTER:True})[0],[])
        items=e.plan(worn,30,None,{b.MASTER:True})[0]
        self.assertIn(e.WEAPON,items);self.assertIn(e.ACCESSORY,items)
        items=e.plan(worn,30,None,{b.MASTER:True,b.key('weapon'):False,b.key('accessory'):False})[0]
        self.assertEqual(items,[])
    def test_fields_added_after_the_master(self):
        schema={'tabs':[{'groups':[{'fields':[{'id':b.MASTER,'label':'아이템 사용','default':False}]}]}]}
        b.add_fields(schema)
        ids=[f['id'] for f in schema['tabs'][0]['groups'][0]['fields']]
        self.assertEqual(ids,[b.MASTER]+[b.key(c) for c,_ in b.BOXES])


if __name__=='__main__':unittest.main()
