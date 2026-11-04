"""Shop editor cells and shop route choice, with fakes only. Never a game test."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import bootstrap,tempfile,unittest,tkinter as tk
from types import SimpleNamespace as S
from unittest.mock import patch
import owner_shop_runtime_candidate as runtime
from owner_shop_settings_candidate import ShopSettings,target_text


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
  tree=self.view.trees['town']
  self.assertEqual(tuple(tree['columns']),('name','enabled','target'))
  index=self.row('max');self.assertEqual(target_text(self.view.rows[index]),'최대')


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
