"""Shop editor cells and shop route choice, with fakes only. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,tempfile,unittest,tkinter as tk
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_shop_runtime_candidate as runtime
from owner_shop_settings_candidate import ShopSettings,target_text,one_list,SCREEN_GUESS


class Target(unittest.TestCase):
 def setUp(self):
  self.tk=tk.Tk();self.tk.withdraw();self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup);self.addCleanup(self.tk.destroy)
  self.view=ShopSettings(self.tk,Path(self.dir.name),'p',embedded=True)
 def row(self,mode):
  self.view.rows[0]['mode']=mode;return 0
 def test_number_sets_quantity(self):
  index=self.row('max');self.view.set_target(index,'7')
  self.assertEqual((self.view.rows[index]['mode'],self.view.rows[index]['quantity']),('quantity',7))
 def test_word_sets_max(self):
  index=self.row('quantity');self.view.set_target(index,'최대')
  self.assertEqual(self.view.rows[index]['mode'],'max')
 def test_bad_text_leaves_the_row(self):
  index=self.row('quantity');before=dict(self.view.rows[index])
  for text in ('','0','-1','abc','1.5'):self.view.set_target(index,text)
  self.assertEqual(self.view.rows[index],before)
 def test_list_shows_only_what_can_be_changed(self):
  self.assertEqual(tuple(self.view.tree['columns']),('order','name','enabled','target'))
  index=self.row('max');self.assertEqual(target_text(self.view.rows[index]),'최대')


class OneList(unittest.TestCase):
 def setUp(self):
  self.tk=tk.Tk();self.tk.withdraw();self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup);self.addCleanup(self.tk.destroy)
  self.view=ShopSettings(self.tk,Path(self.dir.name),'p',embedded=True)
 def names(self):return [row['name'] for row in self.view.rows]
 def test_no_potions_and_one_row_per_item(self):
  names=self.names();self.assertFalse([n for n in names if '물약' in n]);self.assertEqual(len(names),len(set(names)))
 def test_misread_row_goes_but_a_chosen_one_stays(self):
  row=dict(shop='remote',name='영음 장비',enabled=False,mode='quantity',quantity=1,verification='',source=SCREEN_GUESS)
  kept=dict(row,name='선녀 상자',enabled=True)
  self.assertEqual([r['name'] for r in one_list([row,kept])],['선녀 상자'])
 def test_either_shop_checked_counts(self):
  base=dict(name='천요석',mode='max',quantity=1,verification='',source='')
  rows=one_list([dict(base,shop='town',enabled=False),dict(base,shop='remote',enabled=True)])
  self.assertEqual(len(rows),1);self.assertTrue(rows[0]['enabled'])
 def test_move_changes_priority_and_save_keeps_it_for_both_shops(self):
  first,second=self.names()[:2]
  self.view.tree.selection_set('1');self.view.move(-1)
  self.assertEqual(self.names()[:2],[second,first]);self.assertEqual(self.view.tree.selection(),('0',))
  self.view.move(-1);self.assertEqual(self.names()[:2],[second,first])
  self.assertTrue(self.view.save())
  items=self.view.store.read_document()['items']
  for shop in ('town','remote'):
   self.assertEqual([r['name'] for r in items if r['shop']==shop][:2],[second,first])


class Route(unittest.TestCase):
 def run_with(self,member,rows):
  bought=[]
  class Store:
   def __init__(self,*_):self.path=S(exists=lambda:True)
   def read_document(self):return {'enabled':True,'items':rows}
  def buy(_a,_c,_i,name,shop):
   bought.append((shop,name));return {'status':'quota_empty'}
  adapter=S(project=S(root=Path('.')))
  with patch.object(runtime,'ShopSettingsStore',Store),patch.object(runtime,'configured_identity',lambda _:'p'),\
       patch.object(runtime,'buy_one',buy),patch('owner_membership.paid',lambda _:member),\
       patch('owner_schedule_priority.hold_reason',lambda _:None):
   runtime.dispatch_configured(adapter,S(checkpoint=lambda:None),None)
  return bought
 ROWS=[{'shop':'town','name':'천요석','enabled':True},{'shop':'remote','name':'천요석','enabled':True},
       {'shop':'town','name':'물약','enabled':True}]
 def test_member_uses_remote_for_a_doubled_item(self):
  self.assertEqual(self.run_with(True,self.ROWS),[('remote','천요석'),('town','물약')])
 def test_non_member_uses_town_for_a_doubled_item(self):
  self.assertEqual(self.run_with(False,self.ROWS),[('town','천요석'),('town','물약')])


if __name__=='__main__':unittest.main()
