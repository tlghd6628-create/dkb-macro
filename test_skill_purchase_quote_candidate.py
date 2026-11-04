"""Saved real shop frames, simulated transaction; no game input."""
import sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap,numpy as np
from PIL import Image
from owner_skill_ui import SkillUI,catalog
from owner_skill_goal import Pending

FIX=bootstrap.R.parent.parent/'보관/개발이력_20261101_120213/owner/shop_skill_20261101/fixtures'
class Ledger:
 def __init__(self):self.item={'purchases':{}};self.begun=[];self.receipts=[]
 def begin_purchase(self,key,quote,**kwargs):self.begun.append((key,quote));return True
 def purchase_receipt(self,key,receipt):self.receipts.append((key,receipt))
class UI:
 def __init__(self,change=None,text='[저격] 쇠뇌 사격 도술 조각',cart_change=None):
  self.shop=np.asarray(Image.open(FIX/'skill-shop-partial-unlocked-client.png').convert('RGB')).copy()
  self.quote=np.asarray(Image.open(FIX/'skill-shop-quantity-client.png').convert('RGB')).copy()
  self.current=self.shop;self.public=catalog();self.change=change;self.cart_change=cart_change;self.text=text;self.actions=[]
 def frame(self):
  frame=self.current.copy()
  if self.current is self.quote and self.change:self.change(frame)
  if self.current is self.shop and self.cart_change and (490,302) in self.actions:self.cart_change(frame)
  return frame
 def click(self,x,y,proof):
  if not proof(self.frame()):raise Pending('guard')
  self.actions.append((x,y))
  if (x,y)==(110,123):self.current=self.quote
  elif (x,y)==(490,302):self.current=self.shop
 def wait(self,predicate):
  if not predicate(self.frame()):raise Pending('wait')
 def rows(self,*args,**kwargs):
  self.last_text_frame=self.quote.copy();self.last_text_tick=time.monotonic()
  return [{'text':self.text,'score':.99,'bounds':(410,190,517,203)}]
 def word(self,*args,**kwargs):
  self.last_text_frame=self.current.copy();self.last_text_tick=time.monotonic()
  return {'text':'verified','bounds':(448,390,480,405)}
 def click_word(self,text,box,proof,**kwargs):
  if not proof(self.frame()):raise Pending('cart guard')
  self.actions.append('buy')

class TestQuote(unittest.TestCase):
 def test_real_quote_and_simulated_purchase(self):
  ui=UI();ledger=Ledger()
  self.assertTrue(SkillUI.buy_one(ui,ledger,{'name':'쇠뇌 사격','id':39,'y':123},tutorial=True))
  self.assertEqual(ui.actions,[(110,123),(490,302),'buy']);self.assertEqual(len(ledger.receipts),1)
 def test_exact_item_required_even_when_name_is_substring(self):
  ui=UI(text='[저격] 쇠뇌 사격 다른 도술 조각');ledger=Ledger()
  with self.assertRaises(Pending):SkillUI.buy_one(ui,ledger,{'name':'쇠뇌 사격','id':39,'y':123},tutorial=True)
  self.assertEqual(ui.actions,[(110,123)]);self.assertEqual(ledger.begun,[])
 def test_changed_quote_title_price_or_quantity_never_commits(self):
  for box in ((410,190,517,203),(461,198,512,222),(432,239,453,259)):
   def change(frame,box=box):
    l,t,r,b=box;frame[t:b,l:r]=0
   ui=UI(change=change);ledger=Ledger()
   with self.assertRaises(Pending):SkillUI.buy_one(ui,ledger,{'name':'쇠뇌 사격','id':39,'y':123},tutorial=True)
   self.assertEqual(ui.actions,[(110,123)]);self.assertEqual(ledger.begun,[])
 def test_changed_cart_total_or_shop_blocks_final_buy(self):
  for box in ((448,390,480,405),(30,1,240,31)):
   def change(frame,box=box):
    l,t,r,b=box;frame[t:b,l:r]=0
   ui=UI(cart_change=change);ledger=Ledger()
   with self.assertRaises(Pending):SkillUI.buy_one(ui,ledger,{'name':'쇠뇌 사격','id':39,'y':123},tutorial=True)
   self.assertEqual(ui.actions,[(110,123),(490,302)]);self.assertEqual(ledger.receipts,[])
if __name__=='__main__':unittest.main(verbosity=2)
